"""Fast upscaling and retouch pipeline used by the Enhance Studio.

The design goal is 'real time feel': cheap operations run before upscaling,
the API returns a small preview immediately, and every stage reports progress.
Face-aware retouch is enabled automatically when OpenCV is installed; the
NumPy/Pillow fallback works everywhere (including Vercel's default runtime).
"""

from functools import lru_cache

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    CV2_AVAILABLE = False

TARGET_2K = 2048
TARGET_4K = 3840

PRESETS = {
    "auto_retouch": {
        "label": "Auto Retouch (Remini-style)",
        "description": (
            "One click: auto clear and adjust, detect faces, smooth skin, reduce noise, "
            "sharpen and upscale. The sliders are filled in automatically from your image "
            "and you can still override any of them."
        ),
        "settings": {"sharpen": 45, "denoise": 25, "skin": 70, "clarity": 35, "vibrance": 30, "warmth": 0},
        "auto": True,
    },
    "auto": {
        "label": "Auto Clear & Adjust",
        "description": (
            "Automatically stretches contrast and balances colour, then adapts denoise, "
            "clarity and sharpening to the image. Used by the classic 2K and 4K buttons."
        ),
        "settings": {"sharpen": 45, "denoise": 25, "skin": 15, "clarity": 35, "vibrance": 30, "warmth": 5},
        "auto": True,
    },
    "portrait": {
        "label": "Portrait Retouch",
        "description": "Skin smoothing with edge preservation, gentle clarity and warm skin tones. Face-aware when OpenCV is available.",
        "settings": {"sharpen": 25, "denoise": 20, "skin": 70, "clarity": 20, "vibrance": 25, "warmth": 8},
    },
    "restore": {
        "label": "Old Photo Restore",
        "description": "Stronger denoise, scratch-style noise cleanup and clarity for scanned or damaged photos.",
        "settings": {"sharpen": 40, "denoise": 70, "skin": 0, "clarity": 45, "vibrance": 20, "warmth": 5},
    },
    "clarity": {
        "label": "Clarity Boost",
        "description": "Local contrast and crisp edges for landscapes, architecture and product shots.",
        "settings": {"sharpen": 65, "denoise": 15, "skin": 0, "clarity": 70, "vibrance": 35, "warmth": 0},
    },
}


def to_rgb(img):
    if img.mode in ("RGBA", "LA", "P") or "transparency" in img.info:
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return img.convert("RGB")


def clamp(value, low, high):
    return max(low, min(high, value))


def _report(progress, percent, message):
    if progress:
        progress(percent, message)


def auto_levels(img, strength=0.65):
    """Auto clear + colour balance: percentile stretch and grey-world gain."""
    array = np.asarray(img, dtype=np.float32)
    means = array.reshape(-1, 3).mean(axis=0)
    grey = float(means.mean())
    gains = np.clip(grey / np.maximum(means, 1.0), 0.88, 1.12)
    balanced = array * gains

    luminance = (balanced[:, :, 0] * 0.2126 + balanced[:, :, 1] * 0.7152 +
                 balanced[:, :, 2] * 0.0722)
    low, high = np.percentile(luminance, (2, 98))
    if high - low < 12:
        return Image.fromarray(np.clip(balanced, 0, 255).astype(np.uint8), "RGB")

    stretched = np.clip((balanced - low) * (255.0 / (high - low)), 0, 255)
    result = array * (1 - strength) + stretched * strength
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8), "RGB")


def measure_quality(img):
    """Cheap statistics used to choose adaptive auto settings."""
    gray = np.asarray(img.convert("L"), dtype=np.float32)
    low, high = np.percentile(gray, (5, 95))
    blurred = np.asarray(img.filter(ImageFilter.GaussianBlur(1.2)), dtype=np.float32)
    noise = float(np.mean(np.abs(np.asarray(img, dtype=np.float32) - blurred)))
    saturation = float(np.asarray(img.convert("HSV"), dtype=np.float32)[:, :, 1].mean()) / 255.0
    return {
        "contrast": float((high - low) / 255.0),
        "noise": noise,
        "saturation": saturation,
        "faces": len(detect_faces(img)),
    }


def auto_settings(img, settings):
    """Fill in adaptive values for keys the user did not explicitly override."""
    quality = measure_quality(img)
    values = dict(settings)
    explicit = set(settings.get("_explicit", ()))

    def set_auto(key, value, low, high):
        if key not in explicit:
            values[key] = int(clamp(round(value), low, high))

    set_auto("denoise", 8 + quality["noise"] * 3.5, 0, 70)
    set_auto("clarity", 72 - quality["contrast"] * 50, 15, 85)
    set_auto("sharpen", 32 + (1 - quality["contrast"]) * 30, 20, 75)
    set_auto("vibrance", 20 + (1 - quality["saturation"]) * 30, 5, 50)

    if quality["faces"] and "skin" not in explicit:
        values["skin"] = max(values.get("skin", 0), 60)
    if settings.get("preset") == "auto_retouch" and not quality["faces"] and "skin" not in explicit:
        values["skin"] = 0

    values["_quality"] = quality
    values["_face_only"] = bool(quality["faces"])
    return values


def upscale(img, long_edge, fast=False):
    """Upscale on the longest side, preserving aspect ratio."""
    width, height = img.size
    if max(width, height) >= long_edge:
        return img.copy()
    scale = long_edge / max(width, height)
    target = (max(1, round(width * scale)), max(1, round(height * scale)))
    if fast or scale <= 2:
        return img.resize(target, Image.Resampling.BICUBIC)
    mid = (max(1, round(width * scale ** 0.5)), max(1, round(height * scale ** 0.5)))
    return img.resize(mid, Image.Resampling.LANCZOS).resize(target, Image.Resampling.LANCZOS)


def denoise(img, amount):
    if amount <= 0:
        return img
    array = np.asarray(img)
    if CV2_AVAILABLE:
        sigma = 8 + amount * 0.5
        return Image.fromarray(cv2.bilateralFilter(array, 7, sigma, sigma))
    return img.filter(ImageFilter.MedianFilter(3 if amount < 60 else 5))


@lru_cache(maxsize=1)
def _face_cascade():
    if not CV2_AVAILABLE or not hasattr(cv2, "data"):
        return None
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    return cascade if not cascade.empty() else None


def detect_faces(img):
    """Return face boxes as (x, y, w, h), or [] if OpenCV/cascade is missing."""
    cascade = _face_cascade()
    if cascade is None:
        return []
    try:
        gray = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
        return [tuple(int(v) for v in face) for face in faces]
    except Exception:
        return []


def smooth_skin(img, amount, face_only=False):
    """Edge-preserving skin smoothing, optionally restricted to detected faces."""
    if amount <= 0:
        return img

    array = np.asarray(img, dtype=np.float32)
    weight = amount / 100.0 * 0.85

    if CV2_AVAILABLE:
        sigma = 8 + amount * 0.45
        smoothed = cv2.bilateralFilter(np.asarray(img), 9, sigma, sigma).astype(np.float32)
        blend = np.full(array.shape[:2], weight, dtype=np.float32)
    else:
        radius = 1.5 + amount / 100.0 * 7
        blurred = np.asarray(img.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32)
        edges = np.asarray(img.convert("L").filter(ImageFilter.FIND_EDGES), dtype=np.float32)
        edge_guard = np.clip(1.0 - edges / 45.0, 0, 1)
        blend = np.full(array.shape[:2], weight, dtype=np.float32) * edge_guard
        smoothed = blurred

    if face_only:
        faces = detect_faces(img)
        if faces:
            mask = np.zeros(array.shape[:2], dtype=np.float32)
            for x, y, w, h in faces:
                # Feather the rectangle so the retouch does not create a visible box.
                pad_x, pad_y = int(w * 0.15), int(h * 0.15)
                x0, y0 = max(0, x - pad_x), max(0, y - pad_y)
                x1, y1 = min(mask.shape[1], x + w + pad_x), min(mask.shape[0], y + h + pad_y)
                mask[y0:y1, x0:x1] = 1.0
            mask = np.asarray(
                Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(12)),
                dtype=np.float32,
            ) / 255.0
            blend = blend * mask

    blend = blend[:, :, None]
    result = array * (1 - blend) + smoothed * blend
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8), "RGB")


def clarity(img, amount):
    if amount <= 0:
        return img
    return img.filter(ImageFilter.UnsharpMask(radius=2, percent=int(amount * 1.6), threshold=2))


def vibrance(img, amount):
    if amount <= 0:
        return img
    hsv = np.asarray(img.convert("HSV"), dtype=np.float32)
    saturation = hsv[:, :, 1]
    room = 1.0 - saturation / 255.0
    hsv[:, :, 1] = np.clip(saturation + (amount / 100.0) * 110 * room, 0, 255)
    return Image.fromarray(hsv.astype(np.uint8), "HSV").convert("RGB")


def warmth(img, amount):
    if not amount:
        return img
    array = np.asarray(img, dtype=np.float32)
    shift = amount * 0.55
    array[:, :, 0] += shift
    array[:, :, 2] -= shift
    return Image.fromarray(np.clip(array, 0, 255).astype(np.uint8), "RGB")


def sharpen(img, amount):
    if amount <= 0:
        return img
    img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=int(amount * 1.5), threshold=2))
    return ImageEnhance.Sharpness(img).enhance(1 + amount / 100.0 * 0.25)


def enhance_image(img, settings, progress=None, fast_preview=False):
    """Run the full pipeline. `settings` keys: mode, preset, sharpen, denoise,
    skin, clarity, vibrance, warmth.
    """
    img = to_rgb(img)
    auto = bool(settings.get("auto"))
    quality = None
    if auto:
        settings = auto_settings(img, settings)
        quality = settings["_quality"]

    values = {key: clamp(int(settings.get(key, 0)), 0, 100) for key in
              ("sharpen", "denoise", "skin", "clarity", "vibrance")}
    warmth_value = clamp(int(settings.get("warmth", 0)), -50, 50)
    mode = settings.get("mode", "2k")
    target = TARGET_2K if mode == "2k" else TARGET_4K

    _report(progress, 5, "Preparing image")
    if auto:
        img = auto_levels(img, 0.65)
        _report(progress, 12, "Auto clear & adjust")
        _report(progress, 17,
                f"Detected {quality['faces']} face(s) — adaptive retouch" if quality["faces"]
                else "Adaptive adjustments ready")
    img = denoise(img, values["denoise"])
    _report(progress, 20, "Reducing noise")

    if values["skin"]:
        face_only = (settings.get("preset") in ("portrait", "auto_retouch")
                     or bool(settings.get("_face_only")))
        img = smooth_skin(img, values["skin"], face_only=face_only)
    _report(progress, 38, "Retouching skin" if values["skin"] else "Keeping natural texture")

    img = upscale(img, min(target, 4096), fast=fast_preview)
    _report(progress, 62, f"Upscaling to {target}")

    img = clarity(img, values["clarity"])
    _report(progress, 74, "Adding clarity")

    img = vibrance(img, values["vibrance"])
    img = warmth(img, warmth_value)
    _report(progress, 86, "Balancing colour")

    img = sharpen(img, values["sharpen"])
    _report(progress, 100, "Final sharpening complete")
    return img
