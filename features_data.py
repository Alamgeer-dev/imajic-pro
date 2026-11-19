"""Feature catalogue used by both the UI and the SEO routes.

Keeping this data in one place means the dropdown, the /features pages and the
sitemap can never drift apart.
"""

FEATURES = [
    {
        "slug": "enhance_2k",
        "name": "Enhance to 2K",
        "category": "Enhance",
        "short": "Upscale smaller photos to 2048px with sharpening and colour cleanup.",
        "description": (
            "The 2K enhancement tool enlarges small or low-resolution photos to a "
            "maximum of 2048 pixels on the longest side while keeping the original "
            "aspect ratio. It uses high-quality Lanczos resampling, then applies an "
            "unsharp mask, gentle median noise reduction, sharper details, a small "
            "colour boost and a light contrast lift. It is the best choice for old "
            "phone photos, profile pictures and images that need to look crisp on "
            "social media without becoming huge files."
        ),
        "uses": ["Old photos", "Profile pictures", "Social media posts", "Listing images"],
        "how": [
            "Upload a JPG, PNG, WebP or other supported image.",
            "Choose ‘Enhance to 2K’ from the feature list.",
            "Click Process Image and compare the side-by-side preview.",
            "Download the enhanced result.",
        ],
        "params": "No extra settings — the enhancement profile is automatic.",
    },
    {
        "slug": "enhance_4k",
        "name": "Enhance to 4K",
        "category": "Enhance",
        "short": "Two-step upscaling to 3840px with optional OpenCV detail filters.",
        "description": (
            "The 4K enhancement tool enlarges images up to 3840 pixels on the longest "
            "side. It upscales in two passes so edges stay smoother than a single "
            "large jump. When OpenCV is available it also applies bilateral filtering "
            "to reduce noise while keeping edges, and CLAHE to lift local contrast in "
            "shadows. A final sharpening and colour pass keeps the result natural. "
            "Very large files are resized for web preview, with the full-size result "
            "available from the download link."
        ),
        "uses": ["Wallpapers", "Large prints", "Product photos", "Restoration projects"],
        "how": [
            "Upload a reasonably clean source image — upscaling cannot invent real detail.",
            "Choose ‘Enhance to 4K’.",
            "Process the image and review the preview.",
            "Use the download button to save the full-resolution file.",
        ],
        "params": "No extra settings — the enhancement profile is automatic.",
    },
    {
        "slug": "grayscale",
        "name": "Grayscale",
        "category": "Basic edits",
        "short": "Convert any photo to clean black and white.",
        "description": (
            "Grayscale removes colour information and keeps the luminance of every "
            "pixel. It is useful for portraits, documents, scanned text and shots "
            "where colour distracts from the subject. The conversion is performed "
            "server-side with Pillow, so the result is consistent across all browsers "
            "and devices."
        ),
        "uses": ["Portraits", "Scanned documents", "Editorial photos", "Graphic design"],
        "how": ["Upload an image.", "Select Grayscale.", "Process and download."],
        "params": "No extra settings.",
    },
    {
        "slug": "resize",
        "name": "Resize Image",
        "category": "Basic edits",
        "short": "Set an exact width and height in pixels.",
        "description": (
            "Resize changes the pixel dimensions of your image. Enter the width and "
            "height you need and the app resamples with Lanczos filtering for sharp, "
            "clean results. Dimensions are capped to protect the server and keep page "
            "loads fast, which is also important when the app runs on serverless "
            "hosting."
        ),
        "uses": ["Website assets", "Passport photos", "Thumbnails", "Email attachments"],
        "how": [
            "Upload an image.",
            "Select Resize Image and enter width and height.",
            "Process and download the resized file.",
        ],
        "params": "Width and height in pixels (1–4096).",
    },
    {
        "slug": "brightness",
        "name": "Adjust Brightness",
        "category": "Basic edits",
        "short": "Make an image lighter or darker from -100 to +100.",
        "description": (
            "Brightness adjustment multiplies the intensity of every pixel by a factor "
            "derived from your slider value. Negative values darken the image and "
            "positive values lighten it. A live value display shows the exact setting "
            "before you submit the form."
        ),
        "uses": ["Underexposed photos", "Overexposed photos", "Uniform corrections"],
        "how": ["Upload an image.", "Choose Adjust Brightness.", "Move the slider, process and download."],
        "params": "Brightness from -100 to +100.",
    },
    {
        "slug": "contrast",
        "name": "Enhance Contrast",
        "category": "Basic edits",
        "short": "Increase or reduce the difference between light and dark areas.",
        "description": (
            "Contrast controls how far pixel values are pushed away from mid-grey. "
            "Higher values make darks darker and lights lighter, which can restore "
            "punch to flat photos. Values below 1.0 soften the image. The server "
            "clamps the value to a safe range so a malformed request cannot produce "
            "an unusable result."
        ),
        "uses": ["Flat photos", "Scanned images", "Graphic design", "Before/after edits"],
        "how": ["Upload an image.", "Select Enhance Contrast.", "Set the factor, process and download."],
        "params": "Contrast factor from 0.5 to 3.0.",
    },
    {
        "slug": "rotate",
        "name": "Rotate Image",
        "category": "Basic edits",
        "short": "Rotate by any angle from -360 to +360 degrees.",
        "description": (
            "Rotate turns the image around its centre by the angle you choose. The "
            "canvas expands automatically so no part of the picture is cut off. Use a "
            "negative value for counter-clockwise rotation. This is useful for photos "
            "taken with a tilted camera and for creative compositions."
        ),
        "uses": ["Tilted photos", "Creative layouts", "Scanned pages", "Social posts"],
        "how": ["Upload an image.", "Choose Rotate Image.", "Enter an angle, process and download."],
        "params": "Angle in degrees from -360 to +360.",
    },
    {
        "slug": "edge",
        "name": "Edge Detection",
        "category": "Effects",
        "short": "Highlight outlines and boundaries in white on black.",
        "description": (
            "Edge detection converts the image to greyscale and applies a find-edges "
            "filter, which emphasises rapid changes in brightness. The result is a "
            "graphic line drawing that can be used for art, sketches or as a first "
            "step in computer-vision experiments."
        ),
        "uses": ["Line art", "Sketch effects", "Computer vision", "Graphic design"],
        "how": ["Upload an image.", "Select Edge Detection.", "Process and download the outline."],
        "params": "No extra settings.",
    },
    {
        "slug": "blur",
        "name": "Blur Image",
        "category": "Effects",
        "short": "Apply a soft Gaussian blur with an adjustable radius.",
        "description": (
            "Gaussian blur smooths the image by averaging neighbouring pixels. A small "
            "radius removes noise, while a larger radius creates a soft background or "
            "a dreamy effect. The slider is capped at 20 so the tool stays responsive "
            "even on large uploads."
        ),
        "uses": ["Background softening", "Privacy masks", "Dreamy effects", "Noise reduction"],
        "how": ["Upload an image.", "Choose Blur Image.", "Pick a radius, process and download."],
        "params": "Blur radius from 1 to 20.",
    },
    {
        "slug": "sharpen",
        "name": "Sharpen Image",
        "category": "Effects",
        "short": "Increase local detail with a standard sharpening filter.",
        "description": (
            "Sharpening boosts the contrast between adjacent pixels so edges appear "
            "more defined. It works well on slightly soft photos, but overuse can "
            "amplify noise. For a stronger, more controlled result try the 2K or 4K "
            "enhancement tools instead."
        ),
        "uses": ["Soft photos", "Text scans", "Product shots", "Quick fixes"],
        "how": ["Upload an image.", "Select Sharpen Image.", "Process and download."],
        "params": "No extra settings.",
    },
    {
        "slug": "filter",
        "name": "Color Filters",
        "category": "Effects",
        "short": "Sepia, Warm, Cool or Vintage looks in one click.",
        "description": (
            "The filter tool offers four ready-made colour grades. Sepia produces a "
            "classic brown-toned photograph. Warm boosts colour and brightness for a "
            "sunny feel. Cool reduces saturation and brightness for a calm look. "
            "Vintage combines greyscale with high contrast for a timeless finish."
        ),
        "uses": ["Social media", "Photo albums", "Posters", "Quick styling"],
        "how": ["Upload an image.", "Choose Color Filters.", "Pick a filter, process and download."],
        "params": "Filter type: Sepia, Warm, Cool or Vintage.",
    },
    {
        "slug": "portrait",
        "name": "Portrait Mode",
        "category": "Pro looks",
        "short": "Blur the background so the subject stands out.",
        "description": (
            "Portrait mode separates the subject from the background and blurs only "
            "the background. When MediaPipe is installed, a selfie-segmentation model "
            "builds an accurate person mask; otherwise the app falls back to a smooth "
            "oval mask. Both paths run on the server, and the amount of blur and edge "
            "softness can be tuned with the sliders."
        ),
        "uses": ["Selfies", "Profile photos", "Portraits", "Avatars"],
        "how": [
            "Upload a portrait photo.",
            "Select Portrait Mode.",
            "Adjust background blur and edge smoothness.",
            "Process and download.",
        ],
        "params": "Background blur (1–30) and edge smoothness (1–10).",
    },
    {
        "slug": "cinematic_dark",
        "name": "Cinematic Dark",
        "category": "Pro looks",
        "short": "Teal-and-orange grade with crushed blacks, grain and vignette.",
        "description": (
            "Cinematic Dark imitates the popular teal-and-orange film look. It maps "
            "shadows towards teal and warm skin tones towards orange, increases "
            "contrast, lowers brightness and adds subtle film grain. A radial vignette "
            "darkens the corners. The strength slider scales the effect so you can "
            "keep it subtle or go full Hollywood."
        ),
        "uses": ["Portraits", "Movie posters", "Night photos", "Creative edits"],
        "how": ["Upload an image.", "Choose Cinematic Dark.", "Set effect strength, process and download."],
        "params": "Effect strength from 50% to 150%.",
    },
    {
        "slug": "4k_pro",
        "name": "4K Pro Look",
        "category": "Pro looks",
        "short": "Ultra-sharp, high-clarity colour grade with a subtle warm tone.",
        "description": (
            "4K Pro Look is a punchy finishing filter: an unsharp mask for crisp "
            "edges, stronger contrast and colour, a gentle warm shift, and one final "
            "sharpening pass. It is designed for images that will be viewed at large "
            "sizes, such as wallpapers and portfolio pieces. Effect strength controls "
            "how aggressive the grade is."
        ),
        "uses": ["Wallpapers", "Portfolios", "Landscapes", "Product galleries"],
        "how": ["Upload an image.", "Choose 4K Pro Look.", "Set effect strength, process and download."],
        "params": "Effect strength from 50% to 150%.",
    },
]

ANALYSIS_FEATURES = [
    {
        "slug": "check_editable",
        "name": "Editable / Non-editable Check",
        "category": "Image analysis",
        "short": "Report format, layers, frames, alpha channel and editability.",
        "description": (
            "This check inspects the file you uploaded and explains how editable it "
            "is. It reports the detected format, pixel dimensions, colour mode, alpha "
            "transparency, animation frames, embedded colour profiles and EXIF data. "
            "It then tells you whether the file is a flattened raster image, a "
            "multi-frame animation or a layered source. This helps you understand what "
            "can be changed before you start editing."
        ),
        "uses": ["Client hand-offs", "Print work", "Asset review", "Design QA"],
        "how": ["Upload an image.", "Choose Editable / Non-editable Check.", "Process and read the report."],
        "params": "No extra settings.",
    },
    {
        "slug": "detect_ai",
        "name": "AI Image Check",
        "category": "Image analysis",
        "short": "Look for AI-generation markers in image metadata and texture.",
        "description": (
            "The AI Image Check scans EXIF, comments and embedded text for markers "
            "left by common generative tools, and reports an experimental texture "
            "signal. It is a heuristic aid, not proof: both AI-generated and ordinary "
            "photos can have missing metadata, and reliable detection needs a trained "
            "model. The result is always shown with a clear confidence label."
        ),
        "uses": ["Content review", "Curiosity", "Education", "Asset intake"],
        "how": ["Upload an image.", "Choose AI Image Check.", "Process and read the indicators."],
        "params": "No extra settings.",
    },
]

FEATURE_BY_SLUG = {item["slug"]: item for item in FEATURES}
ANALYSIS_BY_SLUG = {item["slug"]: item for item in ANALYSIS_FEATURES}
ALL_SLUGS = set(FEATURE_BY_SLUG) | set(ANALYSIS_BY_SLUG)
CATEGORIES = []
for _item in FEATURES + ANALYSIS_FEATURES:
    if _item["category"] not in CATEGORIES:
        CATEGORIES.append(_item["category"])
