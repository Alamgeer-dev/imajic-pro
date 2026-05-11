# app.py - Fixed for Vercel Deployment (no OpenCV)
from flask import Flask, render_template, request, flash, redirect, url_for, send_from_directory
from werkzeug.utils import secure_filename
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageDraw
import os
import uuid
import numpy as np

app = Flask(__name__)
app.secret_key = 'super_secret_key_123_change_me'

# ==================== CONFIG ====================
# Vercel only allows writing to /tmp
UPLOAD_FOLDER = '/tmp/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'tiff'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ==================== ENHANCE 2K ====================
def enhance_to_2k(img):
    img = img.convert("RGB")
    width, height = img.size
    target_max_dim = 2048

    if max(width, height) < target_max_dim:
        if width > height:
            new_width = target_max_dim
            new_height = int(height * (target_max_dim / width))
        else:
            new_height = target_max_dim
            new_width = int(width * (target_max_dim / height))
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
    img = img.filter(ImageFilter.MedianFilter(size=3))
    img = ImageEnhance.Sharpness(img).enhance(1.5)
    img = ImageEnhance.Color(img).enhance(1.15)
    img = ImageEnhance.Contrast(img).enhance(1.1)
    return img


# ==================== ENHANCE 4K ====================
def enhance_to_4k(img):
    img = img.convert("RGB")
    width, height = img.size
    target_max_dim = 3840

    if max(width, height) < target_max_dim:
        scale_factor = min(target_max_dim / width, target_max_dim / height)
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)

        intermediate_factor = scale_factor ** 0.5
        intermediate_width = int(width * intermediate_factor)
        intermediate_height = int(height * intermediate_factor)

        intermediate_img = img.resize((intermediate_width, intermediate_height), Image.Resampling.LANCZOS)
        img = intermediate_img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=2))
    img = ImageEnhance.Sharpness(img).enhance(1.3)
    img = ImageEnhance.Color(img).enhance(1.1)
    img = ImageEnhance.Contrast(img).enhance(1.05)
    return img


# ==================== CINEMATIC DARK ====================
def apply_cinematic_dark(img, strength=1.0):
    img = img.convert("RGB")
    width, height = img.size

    lab = img.convert("LAB")
    l, a, b = lab.split()

    l_np = np.array(l)
    a_np = np.array(a)
    b_np = np.array(b)

    shadow_mask = l_np < 90
    a_np[shadow_mask] = np.clip(a_np[shadow_mask] - 25, 0, 255)
    b_np[shadow_mask] = np.clip(b_np[shadow_mask] + 30, 0, 255)

    skin_mask = (l_np > 100) & (a_np > 125) & (a_np < 140) & (b_np > 120)
    a_np[skin_mask] = np.clip(a_np[skin_mask] + 25, 0, 255)
    b_np[skin_mask] = np.clip(b_np[skin_mask] - 15, 0, 255)

    lab_array = np.stack([l_np, a_np, b_np], axis=2).astype(np.uint8)
    img = Image.fromarray(lab_array, "LAB").convert("RGB")

    img = ImageEnhance.Contrast(img).enhance(1.6 * strength)
    img = ImageEnhance.Brightness(img).enhance(0.85 * strength)

    img_np = np.array(img)
    noise = np.random.normal(0, 12 * strength, img_np.shape)
    img_np = np.clip(img_np + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(img_np)

    mask = Image.new("L", img.size, 255)
    overlay = Image.new("L", img.size, 0)
    draw_overlay = ImageDraw.Draw(overlay)
    draw_overlay.ellipse([-200, -200, width + 200, height + 200], fill=180)
    mask = Image.composite(mask, overlay, overlay)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=120))

    img_np = np.array(img)
    mask_np = np.array(mask) / 255.0
    img_np = (img_np * mask_np[:, :, None]).astype(np.uint8)
    img = Image.fromarray(img_np)

    return img


# ==================== 4K PRO LOOK ====================
def apply_4k_pro(img, strength=1.0):
    img = img.convert("RGB")
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
    img = ImageEnhance.Contrast(img).enhance(1.3 * strength)
    img = ImageEnhance.Color(img).enhance(1.35 * strength)

    r, g, b = img.split()
    r = r.point(lambda i: min(255, i * 1.05))
    g = g.point(lambda i: min(255, i * 0.98))
    img = Image.merge("RGB", (r, g, b))
    img = img.filter(ImageFilter.SHARPEN)
    return img


# ==================== PORTRAIT MODE (PIL only) ====================
def apply_portrait_mode(img_path, blur_strength=15, edge_smoothness=7):
    try:
        img = Image.open(img_path).convert("RGB")
        w, h = img.size

        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)
        padding_x = w * 0.15
        padding_y = h * 0.15
        draw.ellipse((padding_x, padding_y, w - padding_x, h - padding_y), fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(radius=edge_smoothness * 3))

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
            return ImageOps.grayscale(img).convert("RGB")
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
            temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{uuid.uuid4().hex[:8]}.jpg")
            img.save(temp_path, "JPEG", quality=95)
            blur_val = int(form_data.get('portrait_blur', 15))
            smooth_val = int(form_data.get('portrait_smooth', 7))
            result = apply_portrait_mode(temp_path, blur_strength=blur_val, edge_smoothness=smooth_val)
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
    original_image = None
    processed_image = None

    if request.method == 'POST':
        if 'image' not in request.files:
            flash('No file selected')
            return redirect(url_for('index'))

        file = request.files['image']
        if file.filename == '':
            flash('No file selected')
            return redirect(url_for('index'))

        if not allowed_file(file.filename):
            flash('Invalid file type')
            return redirect(url_for('index'))

        filename = secure_filename(file.filename)
        unique_id = uuid.uuid4().hex[:8]
        original_image = f"orig_{unique_id}_{filename}"
        processed_image = f"proc_{unique_id}_{filename}"

        original_path = os.path.join(app.config['UPLOAD_FOLDER'], original_image)
        file.save(original_path)

        feature = request.form.get('feature')
        if not feature:
            flash('Please select a processing feature')
            return redirect(url_for('index'))

        try:
            img = Image.open(original_path).convert("RGB")
            result_img = process_image(img, feature, request.form)

            if result_img:
                result_path = os.path.join(app.config['UPLOAD_FOLDER'], processed_image)
                if filename.lower().endswith('.png'):
                    result_img.save(result_path, 'PNG', optimize=True)
                else:
                    result_img.save(result_path, 'JPEG', quality=95, optimize=True)
                flash('Image processed successfully!')
            else:
                flash('Processing failed')
                processed_image = None

        except Exception as e:
            flash(f'Error processing image: {str(e)}')
            print(f"Route error: {e}")
            processed_image = None

        return render_template('index.html',
                               original_image=original_image,
                               processed_image=processed_image)

    return render_template('index.html')


@app.route('/download/<filename>')
def download(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    except Exception:
        flash('File not found')
        return redirect(url_for('index'))


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
