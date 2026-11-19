"""ImageMagic Pro — Flask image editor with server-rendered, indexable pages."""

import base64
import logging
import os
import secrets
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from io import BytesIO
from xml.sax.saxutils import escape

import numpy as np
from flask import (
    Flask, Response, abort, flash, jsonify, redirect, render_template,
    request, url_for,
)
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    CV2_AVAILABLE = False

from analysis import analyze_editability, detect_ai_indicators
from features_data import (
    ANALYSIS_BY_SLUG, ANALYSIS_FEATURES, ALL_SLUGS, CATEGORIES,
    FEATURE_BY_SLUG, FEATURES,
)

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("imajic")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, "templates"),
            static_folder=os.path.join(BASE_DIR, "public", "static"),
            static_url_path="/static")

# ---------- Configuration (all secrets/limits come from the environment) ----------
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
SITE_URL = os.environ.get("SITE_URL", "http://localhost:5000").rstrip("/")
GOOGLE_VERIFICATION = os.environ.get("GOOGLE_SITE_VERIFICATION", "")
GOOGLE_ANALYTICS_ID = os.environ.get("GOOGLE_ANALYTICS_ID", "")
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", 12 * 1024 * 1024))
MAX_IMAGE_PIXELS = 40_000_000
MAX_OUTPUT_DIM = 4096
PREVIEW_DIM = 900

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
app.config["SITE_URL"] = SITE_URL

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "webp", "tiff"}

# In-memory store for generated results. On a multi-instance host, replace this
# with object storage (S3/GCS) so download tokens work on every instance.
RESULT_STORE = {}
STORE_LOCK = threading.Lock()
STORE_TTL = 30 * 60
STORE_MAX = 60


@app.context_processor
def inject_site_context():
    return {
        "site_url": SITE_URL,
        "google_verification": GOOGLE_VERIFICATION,
        "google_analytics_id": GOOGLE_ANALYTICS_ID,
        "all_features": FEATURES,
        "analysis_features": ANALYSIS_FEATURES,
        "categories": CATEGORIES,
        "current_year": datetime.now(timezone.utc).year,
    }


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def clamp(value, low, high):
    return max(low, min(high, value))


def number(form, key, default, low, high, cast=float):
    try:
        return clamp(cast(form.get(key, default)), low, high)
    except (TypeError, ValueError):
        return default


def to_rgb(img):
    """Flatten transparency onto white so every filter receives an RGB image."""
    if img.mode in ("RGBA", "LA", "P") or "transparency" in img.info:
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return img.convert("RGB")


def pil_to_base64(img, max_dim=PREVIEW_DIM, quality=82):
    """Small JPEG data URI for fast, index-friendly previews."""
    preview = to_rgb(img)
    if max(preview.size) > max_dim:
        preview.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    buffered = BytesIO()
    preview.save(buffered, format="JPEG", quality=quality, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buffered.getvalue()).decode()


def prune_store():
    now = time.time()
    with STORE_LOCK:
        for token in [t for t, item in RESULT_STORE.items()
                      if now - item["ts"] > STORE_TTL]:
            RESULT_STORE.pop(token, None)
        while len(RESULT_STORE) > STORE_MAX:
            RESULT_STORE.pop(next(iter(RESULT_STORE)), None)


def store_result(img):
    result = to_rgb(img)
    if max(result.size) > MAX_OUTPUT_DIM:
        result.thumbnail((MAX_OUTPUT_DIM, MAX_OUTPUT_DIM), Image.Resampling.LANCZOS)
    buffered = BytesIO()
    result.save(buffered, format="JPEG", quality=90, optimize=True)
    token = uuid.uuid4().hex
    with STORE_LOCK:
        RESULT_STORE[token] = {
            "data": buffered.getvalue(),
            "mime": "image/jpeg",
            "ts": time.time(),
            "dimensions": result.size,
        }
    prune_store()
    return token, result.size


# ==================== Enhancement and effect functions ====================

def enhance_to_2k(img):
    img = to_rgb(img)
    width, height = img.size
    target = 2048
    if max(width, height) < target:
        if width > height:
            new_height = max(1, int(height * (target / width)))
            new_size = (target, new_height)
        else:
            new_width = max(1, int(width * (target / height)))
            new_size = (new_width, target)
        img = img.resize(new_size, Image.Resampling.LANCZOS)

    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
    img = img.filter(ImageFilter.MedianFilter(size=3))
    img = ImageEnhance.Sharpness(img).enhance(1.5)
    img = ImageEnhance.Color(img).enhance(1.15)
    return ImageEnhance.Contrast(img).enhance(1.1)


def enhance_to_4k(img):
    img = to_rgb(img)
    width, height = img.size
    target = 3840
    if max(width, height) < target:
        scale = min(target / width, target / height)
        mid = (max(1, int(width * scale ** 0.5)), max(1, int(height * scale ** 0.5)))
        final = (max(1, int(width * scale)), max(1, int(height * scale)))
        img = img.resize(mid, Image.Resampling.LANCZOS).resize(final, Image.Resampling.LANCZOS)

    if CV2_AVAILABLE:
        try:
            array = np.array(img)
            array = cv2.bilateralFilter(array, 9, 75, 75)
            lab = cv2.cvtColor(array, cv2.COLOR_RGB2LAB)
            l_ch, a_ch, b_ch = cv2.split(lab)
            l_ch = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l_ch)
            img = Image.fromarray(cv2.cvtColor(cv2.merge((l_ch, a_ch, b_ch)), cv2.COLOR_LAB2RGB))
        except Exception as exc:
            logger.warning("OpenCV enhancement skipped: %s", exc)

    img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=2))
    img = ImageEnhance.Sharpness(img).enhance(1.3)
    img = ImageEnhance.Color(img).enhance(1.1)
    return ImageEnhance.Contrast(img).enhance(1.05)


def apply_cinematic_dark(img, strength=1.0):
    img = to_rgb(img)
    width, height = img.size
    lab = img.convert("LAB")

    # int16 prevents uint8 wrap-around when shadows are pushed towards teal.
    l_np = np.array(lab.getchannel("L"), dtype=np.int16)
    a_np = np.array(lab.getchannel("A"), dtype=np.int16)
    b_np = np.array(lab.getchannel("B"), dtype=np.int16)

    shadow = l_np < 90
    a_np[shadow] -= 25
    b_np[shadow] += 30

    skin = (l_np > 100) & (a_np > 125) & (a_np < 140) & (b_np > 120)
    a_np[skin] += 25
    b_np[skin] -= 15

    graded = np.stack([
        np.clip(l_np, 0, 255).astype(np.uint8),
        np.clip(a_np, 0, 255).astype(np.uint8),
        np.clip(b_np, 0, 255).astype(np.uint8),
    ], axis=2)
    img = Image.fromarray(graded, "LAB").convert("RGB")

    img = ImageEnhance.Contrast(img).enhance(clamp(1.6 * strength, 0.1, 3.0))
    img = ImageEnhance.Brightness(img).enhance(clamp(0.85 * strength, 0.1, 2.0))

    array = np.array(img, dtype=np.int16)
    noise = np.random.normal(0, 12 * strength, array.shape)
    img = Image.fromarray(np.clip(array + noise, 0, 255).astype(np.uint8))

    yy = np.linspace(-1, 1, height, dtype=np.float32)[:, None]
    xx = np.linspace(-1, 1, width, dtype=np.float32)[None, :]
    distance = np.sqrt(xx * xx + yy * yy) / np.sqrt(2)
    vignette = np.clip(1.0 - 0.55 * np.clip((distance - 0.25) / 0.75, 0, 1), 0.45, 1.0)
    array = np.array(img, dtype=np.float32)
    return Image.fromarray((array * vignette[:, :, None]).astype(np.uint8))


def apply_4k_pro(img, strength=1.0):
    img = to_rgb(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
    img = ImageEnhance.Contrast(img).enhance(clamp(1.3 * strength, 0.1, 3.0))
    img = ImageEnhance.Color(img).enhance(clamp(1.35 * strength, 0.0, 3.0))

    r, g, b = img.split()
    r = r.point(lambda i: min(255, int(i * 1.05)))
    g = g.point(lambda i: min(255, int(i * 0.98)))
    return Image.merge("RGB", (r, g, b)).filter(ImageFilter.SHARPEN)


def apply_portrait_mode(img_path, blur_strength=15, edge_smoothness=7):
    try:
        if CV2_AVAILABLE:
            image = cv2.imread(img_path)
            if image is None:
                raise RuntimeError("OpenCV could not load the image")
            try:
                import mediapipe as mp

                rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                with mp.solutions.selfie_segmentation.SelfieSegmentation(
                    model_selection=1
                ) as segmenter:
                    mask = segmenter.process(rgb_image).segmentation_mask
                mask = (mask > 0.6).astype(np.uint8) * 255
                kernel = max(3, int(edge_smoothness) * 2 + 1)
                mask = cv2.GaussianBlur(mask, (kernel, kernel), 0)
                bg_kernel = max(3, int(blur_strength) * 2 + 1)
                blurred_bg = cv2.GaussianBlur(image, (bg_kernel, bg_kernel), 0)
                alpha = (mask.astype(np.float32) / 255.0)[:, :, None]
                result = image * alpha + blurred_bg * (1 - alpha)
                return Image.fromarray(cv2.cvtColor(result.astype(np.uint8), cv2.COLOR_BGR2RGB))
            except ImportError:
                logger.info("MediaPipe not installed — using oval portrait mask")
    except Exception as exc:
        logger.warning("Portrait segmentation failed: %s", exc)

    img = to_rgb(Image.open(img_path))
    width, height = img.size
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    pad_x, pad_y = width * 0.15, height * 0.15
    draw.ellipse((pad_x, pad_y, width - pad_x, height - pad_y), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(max(1, edge_smoothness)))
    return Image.composite(img, img.filter(ImageFilter.GaussianBlur(blur_strength)), mask)


def apply_sepia(img):
    gray = np.asarray(ImageOps.grayscale(to_rgb(img)), dtype=np.float32)
    channels = [
        np.clip(gray * 1.2, 0, 255).astype(np.uint8),
        np.clip(gray * 1.0, 0, 255).astype(np.uint8),
        np.clip(gray * 0.8, 0, 255).astype(np.uint8),
    ]
    return Image.fromarray(np.stack(channels, axis=2), "RGB")


def process_image(img, feature, form):
    try:
        if feature == "enhance_2k":
            return enhance_to_2k(img)
        if feature == "enhance_4k":
            return enhance_to_4k(img)
        if feature == "grayscale":
            return ImageOps.grayscale(to_rgb(img))
        if feature == "cinematic_dark":
            return apply_cinematic_dark(img, number(form, "effect_strength", 100, 50, 150, int) / 100)
        if feature == "4k_pro":
            return apply_4k_pro(img, number(form, "effect_strength", 100, 50, 150, int) / 100)
        if feature == "resize":
            width = number(form, "width", 800, 1, 4096, int)
            height = number(form, "height", 600, 1, 4096, int)
            return to_rgb(img).resize((int(width), int(height)), Image.Resampling.LANCZOS)
        if feature == "brightness":
            factor = 1 + number(form, "brightness_value", 0, -100, 100, int) / 100
            return ImageEnhance.Brightness(to_rgb(img)).enhance(factor)
        if feature == "contrast":
            return ImageEnhance.Contrast(to_rgb(img)).enhance(number(form, "contrast_value", 1.0, 0.5, 3.0))
        if feature == "rotate":
            angle = number(form, "angle", 90, -360, 360, int)
            return to_rgb(img).rotate(-angle, expand=True, resample=Image.Resampling.BICUBIC)
        if feature == "edge":
            return ImageOps.grayscale(to_rgb(img)).filter(ImageFilter.FIND_EDGES).convert("RGB")
        if feature == "blur":
            return to_rgb(img).filter(ImageFilter.GaussianBlur(number(form, "blur_radius", 3, 0, 20, int)))
        if feature == "sharpen":
            return to_rgb(img).filter(ImageFilter.SHARPEN)
        if feature == "filter":
            kind = form.get("filter_type", "sepia")
            if kind == "sepia":
                return apply_sepia(img)
            if kind == "warm":
                return ImageEnhance.Brightness(
                    ImageEnhance.Color(to_rgb(img)).enhance(1.5)).enhance(1.1)
            if kind == "cool":
                return ImageEnhance.Brightness(
                    ImageEnhance.Color(to_rgb(img)).enhance(0.7)).enhance(0.95)
            if kind == "vintage":
                return ImageEnhance.Contrast(
                    ImageOps.grayscale(to_rgb(img)).convert("RGB")).enhance(1.8)
        if feature == "portrait":
            blur = number(form, "portrait_blur", 15, 1, 30, int)
            smooth = number(form, "portrait_smooth", 7, 1, 10, int)
            handle, temp_path = tempfile.mkstemp(prefix="imajic_", suffix=".jpg")
            os.close(handle)
            try:
                to_rgb(img).save(temp_path, "JPEG", quality=95)
                return apply_portrait_mode(temp_path, blur, smooth)
            finally:
                if os.path.isfile(temp_path):
                    os.remove(temp_path)
        return to_rgb(img)
    except Exception as exc:
        logger.exception("Processing failed for '%s': %s", feature, exc)
        return None


# ==================== Routes ====================

@app.route("/", methods=["GET", "POST"])
def index():
    selected = request.form.get("feature", "") if request.method == "POST" else request.args.get("feature", "")
    context = {
        "original_image": None,
        "processed_image": None,
        "result_url": None,
        "download_url": None,
        "analysis_result": None,
        "analysis_feature": None,
        "selected_feature": selected,
        "result_dimensions": None,
    }

    if request.method == "POST":
        if "image" not in request.files or not request.files["image"].filename:
            flash("Please choose an image first.")
            return redirect(url_for("index", feature=selected))

        file = request.files["image"]
        if not allowed_file(file.filename):
            flash("That file type is not supported. Use PNG, JPG, GIF, BMP, WebP or TIFF.")
            return redirect(url_for("index", feature=selected))

        if selected not in ALL_SLUGS:
            flash("Please select a valid feature.")
            return redirect(url_for("index"))

        try:
            file_data = file.read()
            img = Image.open(BytesIO(file_data))
            img.load()
        except Exception as exc:
            logger.warning("Could not open upload: %s", exc)
            flash("That file could not be read as an image.")
            return redirect(url_for("index", feature=selected))

        context["original_image"] = pil_to_base64(img)

        if selected in ANALYSIS_BY_SLUG:
            context["analysis_feature"] = ANALYSIS_BY_SLUG[selected]
            context["analysis_result"] = (
                analyze_editability(img, file.filename) if selected == "check_editable"
                else detect_ai_indicators(img, file.filename)
            )
            flash("Analysis complete.")
        else:
            result = process_image(img, selected, request.form)
            if result is None:
                flash("Processing failed. Please try a smaller image or another feature.")
            else:
                token, dimensions = store_result(result)
                context["processed_image"] = pil_to_base64(result)
                context["result_url"] = url_for("result_image", token=token)
                context["download_url"] = url_for("download_image", token=token)
                context["result_dimensions"] = dimensions
                flash("Image processed successfully!")

        return render_template("index.html", **context)

    return render_template("index.html", **context)


@app.route("/features")
def features():
    return render_template("features.html",
                           features=FEATURES,
                           analysis_features=ANALYSIS_FEATURES,
                           categories=CATEGORIES)


@app.route("/features/<slug>")
def feature_detail(slug):
    feature = FEATURE_BY_SLUG.get(slug) or ANALYSIS_BY_SLUG.get(slug)
    if feature is None:
        abort(404)
    related = [item for item in FEATURES
               if item["category"] == feature["category"] and item["slug"] != slug][:3]
    return render_template("feature.html", feature=feature, related=related)


@app.route("/result/<token>")
def result_image(token):
    item = RESULT_STORE.get(token)
    if not item:
        abort(404)
    response = Response(item["data"], mimetype=item["mime"])
    response.headers["Cache-Control"] = "private, max-age=3600"
    return response


@app.route("/download/<token>")
def download_image(token):
    item = RESULT_STORE.get(token)
    if not item:
        abort(404)
    response = Response(item["data"], mimetype=item["mime"])
    response.headers["Content-Disposition"] = f'attachment; filename="processed-{token[:8]}.jpg"'
    return response


@app.route("/robots.txt")
def robots():
    body = f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n"
    return Response(body, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap():
    today = datetime.now(timezone.utc).date().isoformat()
    paths = ["/", "/features"] + [
        f"/features/{slug}" for slug in list(FEATURE_BY_SLUG) + list(ANALYSIS_BY_SLUG)
    ]
    urls = "".join(
        f"<url><loc>{escape(SITE_URL + path)}</loc>"
        f"<lastmod>{today}</lastmod><changefreq>weekly</changefreq>"
        f"<priority>{'1.0' if path == '/' else '0.7'}</priority></url>"
        for path in paths
    )
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
    return Response(xml, mimetype="application/xml")


@app.route("/healthz")
def healthz():
    return jsonify(status="ok", cv2=CV2_AVAILABLE)


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404,
                           title="Page not found",
                           message="The page you were looking for does not exist."), 404


@app.errorhandler(413)
def too_large(_error):
    flash("That image is too large. Please upload a file under the size limit.")
    return redirect(url_for("index"))


@app.errorhandler(500)
def server_error(error):
    logger.exception("Server error: %s", error)
    return render_template("error.html", code=500,
                           title="Something went wrong",
                           message="Please try again with a smaller image."), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", host="0.0.0.0", port=port)
