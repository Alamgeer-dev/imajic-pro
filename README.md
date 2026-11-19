# ImageMagic Pro

Server-rendered Flask image editor with 16 editing tools, a real-time 2K/4K Enhance Studio with Remini-style retouch, an editable/non-editable check, and a heuristic AI-image check. Designed to be indexable by Google and deployable on Vercel.

## Project structure

| File | Purpose |
|---|---|
| `app.py` | Flask routes, image processing, `/api/enhance`, SEO endpoints (`/robots.txt`, `/sitemap.xml`) |
| `enhancement.py` | 2K/4K upscaling pipeline + retouch presets (denoise, skin, clarity, vibrance) |
| `features_data.py` | The 16 editing features + 2 analysis checks (single source of truth) |
| `analysis.py` | Editability report and AI-indicator heuristics |
| `templates/base.html` | Shared SSR layout, meta tags, JSON-LD, navigation, footer |
| `templates/index.html` | Classic editor, preview, FAQ, feature grid |
| `templates/enhance.html` | Real-time Enhance Studio with live preview and before/after slider |
| `templates/features.html` | Full feature list page |
| `templates/feature.html` | Indexable detail page for every feature |
| `public/static/` | CSS, logo and background assets served by Vercel and Flask |
| `tests/test_app.py` | Smoke tests for pages, SEO endpoints, processing and the enhance API |
| `vercel.json` | Vercel project configuration |
| `.vercelignore` | Keeps venv/uploads/tests out of the deployment |

---

## Step 1 — Run locally

```bash
# Windows PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open <http://localhost:5000>.

Optional environment variables:

```powershell
$env:SECRET_KEY = "a-long-random-string"
$env:SITE_URL = "http://localhost:5000"
$env:FLASK_DEBUG = "1"   # local only
```

## Step 2 — Run the tests

```bash
python -m unittest discover -s tests -v
```

All 20 smoke tests should pass.

## Step 2b — Real-Time Enhancement Studio

Open <http://localhost:5000/enhance>.

- **One-click Auto Retouch** is the default preset: it auto-clears the image, measures noise/contrast/saturation to pick the slider values, detects faces for retouch, and sends only your manual overrides to the server.
- **Auto clear & adjust:** a percentile contrast stretch plus grey-world colour balance runs before any other step.
- **Live preview:** Canvas filters update instantly (via `requestAnimationFrame`) as you drag Sharpen, Denoise, Skin, Clarity, Vibrance and Warmth.
- **Staged server pipeline:** auto clear/adjust → adaptive denoise → skin retouch (face-aware when OpenCV is installed) → Lanczos upscale → clarity → colour → sharpen, with progress feedback.
- **Classic 2K/4K buttons now use the same auto pipeline** — choosing "Enhance to 2K" or "Enhance to 4K" in the main editor auto-clears, auto-adjusts and retouches too.
- **Before/after slider** for the final result, plus full-resolution `/result/<token>` view and `/download/<token>` attachment.
- **Presets:** Auto Retouch (default, one click), Auto Clear & Adjust, Portrait Retouch, Old Photo Restore, Clarity Boost.

Measured locally on an 800×600 source (worst-case synthetic noise):

| Mode | Output | Time |
|---|---|---|
| 2K | 2048 × 1536 | ~2–3 s |
| 4K | 3840 × 2880 | ~7 s |

`POST /api/enhance` accepts `image`, `mode` (`2k`/`4k`), `preset` and the six slider values, and returns JSON with a small preview data URI, `result_url`, `download_url`, dimensions, elapsed time and progress stages.

**Honest limitation:** this is fast classical image processing, not a generative AI super-resolution model. It restores perceived sharpness, smooths skin and removes noise, but it cannot invent brand-new facial detail the way Remini's neural models can. A heavy super-resolution model would exceed Vercel's function size limit; to add one, call an external API (Replicate, ModelScope, etc.) from `enhancement.py`.

## Step 3 — Commit cleanly to GitHub

The oversized `venv/` and 60 uploaded test photos have already been **untracked** (they stay on your disk). Confirm:

```bash
git ls-files venv        # should print nothing
git ls-files static/uploads   # should print nothing
git add .
git commit -m "SSR, SEO pages, analysis features and review fixes"
git push
```

> Optional but recommended for a public repo: purge the old files from git history with `git filter-repo` (`git filter-repo --path venv --path static/uploads --invert-paths`). Do this only after telling collaborators, because it rewrites history.

## Step 4 — Deploy to Vercel

1. Go to <https://vercel.com/new> → **Import** your GitHub repository.
2. Let Vercel auto-detect the Flask app in `app.py`. Leave the build command and output directory empty; assets in `public/` are served by Vercel's CDN.
3. Add environment variables **before** deploying:

   | Variable | Example | Why |
   |---|---|---|
   | `SITE_URL` | `https://your-app.vercel.app` | Canonical URL, sitemap, Open Graph links |
   | `SECRET_KEY` | long random string | Flash/session signing |
   | `GOOGLE_SITE_VERIFICATION` | `abc123...` | Google Search Console HTML-tag verification |
   | `GOOGLE_ANALYTICS_ID` | `G-XXXXXXX` | Optional Analytics |
   | `MAX_UPLOAD_BYTES` | `12582912` | Optional upload cap (12 MB default) |

4. Click **Deploy**. After deployment, check:
   - `https://your-app.vercel.app/healthz` → `{"status":"ok",...}`
   - `https://your-app.vercel.app/robots.txt`
   - `https://your-app.vercel.app/sitemap.xml`

Set `SITE_URL` to your **custom domain** if you add one later, then redeploy.

## Step 5 — Verify with Google Search Console

1. Open <https://search.google.com/search-console> → **Add property**.
2. Choose **Domain property** (DNS TXT record) or **URL-prefix property** (HTML tag).
   - If using the HTML tag, paste the value into `GOOGLE_SITE_VERIFICATION` and redeploy. Flask will render `<meta name="google-site-verification" ...>` on every page.
3. Click **Verify**.
4. Open **Sitemaps** → enter `sitemap.xml` → **Submit**.
5. Use **URL Inspection** on `/`, `/enhance`, `/features`, and a few `/features/<slug>` pages → **Request indexing**.

## Step 6 — Confirm real SSR (no client-only rendering)

```bash
curl https://your-app.vercel.app/ | Select-String "WebApplication"
curl https://your-app.vercel.app/features/portrait | Select-String "How to use it"
```

If the text is in the raw HTML response, Googlebot sees it without running JavaScript — that is server-side rendering. View source in the browser to check the same thing.

## Step 7 — Google indexing checklist

- [x] Unique `<title>` and meta description on every page
- [x] Canonical URLs
- [x] `robots.txt` and `sitemap.xml`
- [x] Internal links from home → features → detail pages → home
- [x] JSON-LD `WebApplication`, `HowTo` and `FAQPage` structured data
- [x] Semantic HTML (`<main>`, `<nav>`, `<article>`, `<h1>`–`<h3>`), descriptive `alt` text
- [x] Fast, small HTML (compressed thumbnails instead of full base64 images)
- [ ] Search Console verification and sitemap submission (Step 5)
- [ ] Optional: add a custom domain with HTTPS for stronger trust

New pages usually appear within a few days; feature pages can take longer. Keep content unique and avoid thin/duplicate pages.

---

## Notes and limitations

- **Result storage is in-memory.** Download tokens live in the server process for 30 minutes. It works on a single Vercel instance but may 404 if the next request lands on a different instance. For production, store results in Vercel Blob / S3 / GCS and put the URL in the token record.
- **AI Image Check is a heuristic** based on metadata markers and an experimental texture signal. It cannot prove AI authorship — the UI and structured data both say so.
- **Portrait mode** uses MediaPipe when installed; otherwise an oval mask fallback is used.
- **Face-aware retouch** in the Enhance Studio uses OpenCV Haar cascades when OpenCV is installed (the UI badge reports `face-aware retouch active`); without it, a NumPy edge-guard fallback smooths the whole image. OpenCV is optional and guarded by `CV2_AVAILABLE`.
- **Animated images** are processed from the first frame only.
- Uploads are capped at 12 MB, images at 40 megapixels, output at 4096px, and all numeric form values are clamped server-side.
