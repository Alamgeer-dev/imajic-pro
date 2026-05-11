# app.py - Clean & Fixed Version with Working Portrait Mode
from flask import Flask, render_template, request, flash, redirect, url_for, send_from_directory
from werkzeug.utils import secure_filename
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageDraw
import os
import uuid
import numpy as np
import base64
from io import BytesIO

# FIX 1: cv2 made optional so Vercel doesn't crash if not installed
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# FIX 2: Absolute paths so Vercel finds templates/static folders
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, 'templates'),
            static_folder=os.path.join(BASE_DIR, 'static'))
app.secret_key = 'super_secret_key_123_change_me'

# ==================== CONFIG ====================
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'tiff'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Function to convert PIL image to base64 for display
def pil_to_base64(img):
    buffered = BytesIO()
    # Convert to RGB if necessary
    if img.mode in ('RGBA', 'LA', 'P'):
        img = img.convert('RGBA')
        img.save(buffered, format="PNG")
    else:
        img = img.convert('RGB')
        img.save(buffered, format="JPEG", quality=95)
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/{'png' if img.mode == 'RGBA' else 'jpeg'};base64,{img_str}"

# ========== Enhancement Function 2k and 4k ===========

def enhance_to_2k(img):
    """Enhance image to 2K quality (2048x2048 or similar)"""
    # Get current dimensions
    width, height = img.size
    
    # Calculate target size (maintaining aspect ratio)
    target_max_dim = 2048
    
    # Only upscale if image is smaller than target
    if max(width, height) < target_max_dim:
        # Calculate new dimensions maintaining aspect ratio
        if width > height:
            new_width = target_max_dim
            new_height = int(height * (target_max_dim / width))
        else:
            new_height = target_max_dim
            new_width = int(width * (target_max_dim / height))
        
        # High-quality upscaling using LANCZOS (best for enlargement)
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Apply enhancement filters
    # 1. Smart sharpening
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
    
    # 2. Gentle noise reduction
    img = img.filter(ImageFilter.MedianFilter(size=3))
    
    # 3. Enhance details
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(1.5)
    
    # 4. Boost colors slightly
    enhancer = ImageEnhance.Color(img)
    img = enhancer.enhance(1.15)
    
    # 5. Enhance contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.1)
    
    return img

def enhance_to_4k(img):
    """Enhance image to 4K quality (3840x2160 or similar)"""
    # Get current dimensions
    width, height = img.size
    
    # Calculate target size (maintaining aspect ratio)
    target_max_dim = 3840
    
    # Only upscale if image is smaller than target
    if max(width, height) < target_max_dim:
        # Calculate scale factor
        scale_factor = min(target_max_dim / width, target_max_dim / height)
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        
        # Multi-step upscaling for better quality
        intermediate_factor = scale_factor ** 0.5
        intermediate_width = int(width * intermediate_factor)
        intermediate_height = int(height * intermediate_factor)
        
        # First upscale step
        intermediate_img = img.resize(
            (intermediate_width, intermediate_height), 
            Image.Resampling.LANCZOS
        )
        
        # Second upscale step to final size
        img = intermediate_img.resize(
            (new_width, new_height), 
            Image.Resampling.LANCZOS
        )
    
    # Advanced enhancement pipeline
    img_array = np.array(img)
    
    if CV2_AVAILABLE and len(img_array.shape) == 3:
        img_array = cv2.bilateralFilter(img_array, 9, 75, 75)
    
    img = Image.fromarray(img_array)
    
    # Smart sharpening
    img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=2))
    
    # Apply CLAHE for local contrast enhancement
    if CV2_AVAILABLE and len(img_array.shape) == 3:
        try:
            lab = cv2.cvtColor(img_array, cv2.COLOR_RGB2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)
            
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l_channel = clahe.apply(l_channel)
            
            lab = cv2.merge((l_channel, a_channel, b_channel))
            enhanced_array = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
            img = Image.fromarray(enhanced_array)
        except Exception as e:
            print(f"CLAHE processing skipped: {e}")
    
    # Final touch-ups
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(1.3)
    
    enhancer = ImageEnhance.Color(img)
    img = enhancer.enhance(1.1)
    
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.05)
    
    return img

# ==================== CINEMATIC DARK (CapCut Style) ====================
def apply_cinematic_dark(img, strength=1.0):
    img = img.convert("RGB")
    width, height = img.size

    # 1. Teal & Orange (CapCut/Hollywood Look)
    lab = img.convert("LAB")
    l, a, b = lab.split()
    
    l_np = np.array(l)
    a_np = np.array(a)
    b_np = np.array(b)

    # Teal shadows
    shadow_mask = l_np < 90
    a_np[shadow_mask] -= 25
    b_np[shadow_mask] += 30

    # Orange skin tones
    skin_mask = (l_np > 100) & (a_np > 125) & (a_np < 140) & (b_np > 120)
    a_np[skin_mask] += 25
    b_np[skin_mask] -= 15

    a_np = np.clip(a_np, 0, 255)
    b_np = np.clip(b_np, 0, 255)

    lab_array = np.stack([l_np, a_np, b_np], axis=2).astype(np.uint8)
    img = Image.fromarray(lab_array, "LAB").convert("RGB")

    # 2. Boost contrast, crush blacks
    img = ImageEnhance.Contrast(img).enhance(1.6 * strength)
    img = ImageEnhance.Brightness(img).enhance(0.85 * strength)

    # 3. Film grain
    img_np = np.array(img)
    noise = np.random.normal(0, 12 * strength, img_np.shape)
    img_np = np.clip(img_np + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(img_np)

    # 4. Smooth vignette
    mask = Image.new("L", img.size, 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.rectangle([0, 0, width, height], fill=255)
    
    overlay = Image.new("L", img.size, 0)
    draw_overlay = ImageDraw.Draw(overlay)
    draw_overlay.ellipse([-200, -200, width+200, height+200], fill=180)
    mask = Image.composite(mask, overlay, overlay)

    mask = mask.filter(ImageFilter.GaussianBlur(radius=120))

    img_np = np.array(img)
    mask_np = np.array(mask) / 255.0
    img_np = (img_np * mask_np[:, :, None]).astype(np.uint8)
    img = Image.fromarray(img_np)

    return img

# ==================== 4K PRO LOOK (Ultra Sharp + Cinematic) ====================
def apply_4k_pro(img, strength=1.0):
    img = img.convert("RGB")

    # 1. Ultra Sharpen
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))

    # 2. Clarity & Local Contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.3 * strength)

    # 3. Vibrance + Color Pop
    enhancer = ImageEnhance.Color(img)
    img = enhancer.enhance(1.35 * strength)

    # 4. Slight Warm Tone
    r, g, b = img.split()
    r = r.point(lambda i: min(255, i * 1.05))
    g = g.point(lambda i: min(255, i * 0.98))
    img = Image.merge("RGB", (r, g, b))

    # 5. Final Sharpen Pass
    img = img.filter(ImageFilter.SHARPEN)

    return img


# ==================== PORTRAIT MODE (AI + Fallback) ====================
def apply_portrait_mode(img_path, blur_strength=15, edge_smoothness=7):
    try:
        if CV2_AVAILABLE:
            image = cv2.imread(img_path)
            if image is None:
                raise Exception("OpenCV failed to load image")

            try:
                import mediapipe as mp
                
                rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                mp_selfie = mp.solutions.selfie_segmentation
                with mp_selfie.SelfieSegmentation(model_selection=1) as selfie_seg:
                    results = selfie_seg.process(rgb_image)
                    mask = results.segmentation_mask

                    mask = (mask > 0.6).astype(np.uint8) * 255
                    mask = cv2.GaussianBlur(mask, (edge_smoothness * 2 + 1, edge_smoothness * 2 + 1), 0)

                    blurred_bg = cv2.GaussianBlur(image, (101, 101), blur_strength)

                    mask_3d = mask[:, :, np.newaxis]
                    result = np.where(mask_3d == 255, image, blurred_bg)

                    result_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
                    return Image.fromarray(result_rgb)
                    
            except ImportError:
                pass

        # Use simple oval if MediaPipe/cv2 not installed
        print("cv2/MediaPipe not available → using simple oval portrait mode")
        img = Image.open(img_path).convert("RGB")
        w, h = img.size
        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)
        padding_x = w * 0.15
        padding_y = h * 0.15
        draw.ellipse((padding_x, padding_y, w - padding_x, h - padding_y), fill=255)

        blurred = img.filter(ImageFilter.GaussianBlur(blur_strength * 1.8))
        return Image.composite(img, blurred, mask)

    except Exception as e:
        print(f"Portrait mode error: {e}")
        return Image.open(img_path)


# ==================== MAIN IMAGE PROCESSING ====================
def process_image(img, feature, form_data):
    try:
        strength = float(form_data.get('effect_strength', 100)) / 100

        if feature == 'enhance_2k':
            return enhance_to_2k(img)
            
        elif feature == 'enhance_4k':
            return enhance_to_4k(img)
            
        elif feature == 'grayscale':
            return ImageOps.grayscale(img)

        elif feature == 'cinematic_dark':
            return apply_cinematic_dark(img, strength)

        elif feature == '4k_pro':
            return apply_4k_pro(img, strength)

        elif feature == 'resize':
            w = int(form_data.get('width', 800))
            h = int(form_data.get('height', 600))
            return img.resize((w, h), Image.Resampling.LANCZOS)

        elif feature == 'brightness':
            factor = 1 + float(form_data.get('brightness_value', 0)) / 100
            return ImageEnhance.Brightness(img).enhance(factor)

        elif feature == 'contrast':
            factor = float(form_data.get('contrast_value', 1.0))
            return ImageEnhance.Contrast(img).enhance(factor)

        elif feature == 'rotate':
            angle = int(form_data.get('angle', 90))
            return img.rotate(-angle, expand=True, resample=Image.BICUBIC)

        elif feature == 'edge':
            return img.convert("L").filter(ImageFilter.FIND_EDGES).convert("RGB")

        elif feature == 'blur':
            radius = int(form_data.get('blur_radius', 3))
            return img.filter(ImageFilter.GaussianBlur(radius))

        elif feature == 'sharpen':
            return img.filter(ImageFilter.SHARPEN)

        elif feature == 'filter':
            filter_type = form_data.get('filter_type', 'sepia')
            if filter_type == 'sepia':
                gray = ImageOps.grayscale(img)
                sepia = gray.convert('RGB')
                pixels = sepia.load()
                for x in range(sepia.width):
                    for y in range(sepia.height):
                        r = pixels[x, y][0]
                        pixels[x, y] = (
                            min(255, int(r * 1.2)),
                            min(255, int(r * 1.0)),
                            min(255, int(r * 0.8))
                        )
                return sepia

            elif filter_type == 'warm':
                img = ImageEnhance.Color(img).enhance(1.5)
                return ImageEnhance.Brightness(img).enhance(1.1)

            elif filter_type == 'cool':
                img = ImageEnhance.Color(img).enhance(0.7)
                return ImageEnhance.Brightness(img).enhance(0.95)

            elif filter_type == 'vintage':
                gray = ImageOps.grayscale(img).convert('RGB')
                return ImageEnhance.Contrast(gray).enhance(1.8)

        elif feature == 'portrait':
            # Save temporary file for OpenCV/MediaPipe
            temp_path = os.path.join('/tmp', f"temp_{uuid.uuid4().hex[:8]}.jpg")
            img.save(temp_path, "JPEG", quality=95)
            blur_val = int(form_data.get('portrait_blur', 15))
            smooth_val = int(form_data.get('portrait_smooth', 7))
            result = apply_portrait_mode(temp_path, blur_strength=blur_val, edge_smoothness=smooth_val)
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return result

        else:
            return img

    except Exception as e:
        print(f"Processing error for feature '{feature}': {e}")
        return None


# ==================== ROUTES ====================
@app.route('/', methods=['GET', 'POST'])
def index():
    # Initialize variables
    original_image_data = None
    processed_image_data = None

    print(f"Request method: {request.method}")  # Debug log

    if request.method == 'POST':
        print("Processing POST request")  # Debug log
        
        if 'image' not in request.files:
            print("No image in request.files")  # Debug log
            flash('No file selected')
            return redirect(url_for('index'))

        file = request.files['image']
        if file.filename == '':
            print("Empty filename")  # Debug log
            flash('No file selected')
            return redirect(url_for('index'))

        if not allowed_file(file.filename):
            print(f"Invalid file type: {file.filename}")  # Debug log
            flash('Invalid file type')
            return redirect(url_for('index'))

        # Read file data
        file_data = file.read()
        print(f"File read, size: {len(file_data)} bytes")  # Debug log
        
        # Convert original to base64 for display
        original_image_data = base64.b64encode(file_data).decode()
        # Detect image type from filename
        ext = file.filename.rsplit('.', 1)[1].lower()
        mime_type = 'jpeg' if ext in ['jpg', 'jpeg'] else ext
        original_image_data = f"data:image/{mime_type};base64,{original_image_data}"
        print(f"Original image base64 created: {original_image_data[:50]}...")  # Debug log

        feature = request.form.get('feature')
        print(f"Feature selected: {feature}")  # Debug log
        
        if not feature:
            print("No feature selected")  # Debug log
            flash('Please select a processing feature')
            return redirect(url_for('index'))

        try:
            # Open image from bytes
            img = Image.open(BytesIO(file_data))
            print(f"Image opened: {img.size}, mode: {img.mode}")  # Debug log
            
            # Process the image
            result_img = process_image(img, feature, request.form)
            print(f"Image processed, result: {result_img is not None}")  # Debug log

            if result_img:
                # Convert processed image to base64
                processed_image_data = pil_to_base64(result_img)
                print(f"Processed image base64 created: {processed_image_data[:50]}...")  # Debug log
                flash('Image processed successfully!')
            else:
                print("Processing returned None")  # Debug log
                flash('Processing failed')
                
        except Exception as e:
            print(f"Error in route: {e}")  # Debug log
            import traceback
            traceback.print_exc()  # Print full error
            flash(f'Error processing image: {str(e)}')

        print(f"Rendering template with original={bool(original_image_data)}, processed={bool(processed_image_data)}")  # Debug log
        return render_template('index.html',
                               original_image=original_image_data,
                               processed_image=processed_image_data)

    return render_template('index.html',
                           original_image=None,
                           processed_image=None)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)