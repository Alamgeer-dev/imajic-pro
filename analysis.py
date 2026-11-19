"""Lightweight, offline image analysis helpers.

These checks are deliberately honest: they report what can be observed in the
file itself and never claim certainty about AI authorship.
"""

import numpy as np
from PIL import Image, ExifTags

AI_MARKERS = (
    "midjourney", "stable diffusion", "stablediffusion", "dall-e", "dalle",
    "openai", "chatgpt", "sora", "firefly", "adobe firefly", "leonardo.ai",
    "leonardo ai", "runway", "pixai", "novelai", "dreamstudio", "comfyui",
    "automatic1111", "negative prompt", "prompt:", "seed:", "steps:", "cfg scale",
)

VECTOR_OR_LAYERED = {"PSD", "AI", "SVG", "PDF", "EPS", "XCF", "KRA"}


def _to_rgb(img):
    """Flatten transparency onto white so every downstream filter gets RGB."""
    if img.mode in ("RGBA", "LA", "P") or "transparency" in img.info:
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return img.convert("RGB")


def analyze_editability(img, filename):
    """Return a plain dict describing how editable the uploaded file is."""
    fmt = (getattr(img, "format", None) or "unknown").upper()
    width, height = img.size
    frames = int(getattr(img, "n_frames", 1) or 1)
    layers = len(getattr(img, "layer", []) or [])
    has_alpha = img.mode in ("RGBA", "LA") or "transparency" in img.info
    has_exif = bool(img.info.get("exif"))
    has_icc = bool(img.info.get("icc_profile"))
    dpi = img.info.get("dpi")

    details = [
        f"Detected format: {fmt}.",
        f"Dimensions: {width} × {height} pixels.",
        f"Colour mode: {img.mode}.",
        f"Transparency: {'yes' if has_alpha else 'no'}.",
        f"Animation frames: {frames}.",
        f"EXIF metadata: {'present' if has_exif else 'not present'}.",
        f"ICC colour profile: {'present' if has_icc else 'not present'}.",
    ]
    if dpi:
        details.append(f"Stored DPI: {dpi}.")

    if fmt in VECTOR_OR_LAYERED:
        verdict = "Layered / vector source — highly editable"
        note = "Keep the original file: this format keeps separate layers or paths."
    elif frames > 1:
        verdict = "Multi-frame raster — partly editable"
        note = "This file contains animation frames. The editor processes only the first frame."
    elif layers > 1:
        verdict = "Multi-layer raster — partly editable"
        note = "Layers are preserved in the source file, but the editor works on a flattened view."
    elif has_alpha:
        verdict = "Flattened raster with transparency — editable"
        note = "You can edit pixels and the alpha channel, but there are no separate layers."
    else:
        verdict = "Flattened raster — editable"
        note = "You can edit pixels freely, but the file has no separate layers or paths."

    return {
        "verdict": verdict,
        "note": note,
        "details": details,
        "filename": filename,
    }


def detect_ai_indicators(img, filename):
    """Return heuristic indicators of AI generation, with explicit uncertainty."""
    fmt = (getattr(img, "format", None) or "unknown").upper()
    text_parts = []

    exif_bytes = img.info.get("exif")
    if exif_bytes:
        try:
            exif = Image.Exif()
            exif.load(exif_bytes)
            for tag_id, value in exif.items():
                tag = ExifTags.TAGS.get(tag_id, tag_id)
                text_parts.append(f"{tag}: {value}")
        except Exception:
            pass

    for key, value in img.info.items():
        if isinstance(value, bytes):
            try:
                value = value.decode("utf-8", errors="ignore")
            except Exception:
                value = str(value)
        if isinstance(value, (str, int, float)):
            text_parts.append(f"{key}: {value}")

    haystack = " ".join(text_parts).lower()
    markers = sorted({marker for marker in AI_MARKERS if marker in haystack})

    # Experimental, low-weight texture signal. It never decides the verdict.
    small = _to_rgb(img).convert("L")
    small.thumbnail((384, 384), Image.Resampling.LANCZOS)
    array = np.asarray(small, dtype=np.float32)
    if array.ndim == 2 and array.size > 4:
        grad_x = float(np.mean(np.abs(np.diff(array, axis=1))))
        grad_y = float(np.mean(np.abs(np.diff(array, axis=0))))
        energy = (grad_x + grad_y) / 2
    else:
        energy = 0.0

    if energy < 2.0:
        texture = "Very smooth texture (sometimes seen in generated images)"
    elif energy > 8.0:
        texture = "High-detail texture (common in natural photographs)"
    else:
        texture = "Mixed texture (not diagnostic)"

    if markers:
        likelihood = "Possible AI origin — markers found in file metadata"
        summary = "The file contains text associated with generative tools: " + ", ".join(markers) + "."
    elif not text_parts:
        likelihood = "Inconclusive — no metadata available"
        summary = "The file has little or no embedded metadata, which is normal for both AI and camera images."
    else:
        likelihood = "No AI markers found in metadata"
        summary = "No known generative-tool markers were found in the readable metadata."

    return {
        "likelihood": likelihood,
        "summary": summary,
        "markers": markers,
        "texture": texture,
        "texture_note": "Experimental signal only — it is not evidence of AI authorship.",
        "disclaimer": (
            "This check is a heuristic based on metadata and simple texture statistics. "
            "It cannot prove whether an image was generated by AI. A reliable answer "
            "requires a trained detection model and even those can be wrong."
        ),
        "filename": filename,
        "format": fmt,
    }
