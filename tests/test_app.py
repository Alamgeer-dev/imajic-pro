"""Smoke tests for the SSR pages, SEO endpoints and image processing."""

import io
import re
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

import enhancement
from app import app


def image_file(mode="RGB", size=(24, 24), fmt="PNG"):
    buffer = io.BytesIO()
    Image.new(mode, size, (120, 140, 160) if mode == "RGB" else 128).save(buffer, fmt)
    buffer.seek(0)
    return buffer, "test." + fmt.lower()


class PublicPagesTest(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_home_is_server_rendered_and_indexable(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('<html lang="en">', html)
        self.assertIn('name="description"', html)
        self.assertIn('rel="canonical"', html)
        self.assertIn("application/ld+json", html)
        self.assertIn("WebApplication", html)
        self.assertIn("FAQPage", html)
        self.assertIn("/features/enhance_4k", html)

    def test_feature_pages(self):
        self.assertEqual(self.client.get("/features").status_code, 200)
        detail = self.client.get("/features/portrait")
        self.assertEqual(detail.status_code, 200)
        self.assertIn("Portrait Mode", detail.get_data(as_text=True))
        self.assertEqual(self.client.get("/features/not-a-feature").status_code, 404)

    def test_robots_and_sitemap(self):
        robots = self.client.get("/robots.txt")
        self.assertEqual(robots.status_code, 200)
        self.assertIn("Sitemap:", robots.get_data(as_text=True))

        sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(sitemap.status_code, 200)
        xml = sitemap.get_data(as_text=True)
        self.assertIn("<urlset", xml)
        self.assertIn("/enhance", xml)
        for slug in ("enhance_2k", "enhance_4k", "portrait", "cinematic_dark",
                     "detect_ai", "retouch", "restore"):
            self.assertIn(f"/features/{slug}", xml)

    def test_health(self):
        self.assertEqual(self.client.get("/healthz").get_json()["status"], "ok")

    def test_static_assets_are_served(self):
        for path, content_type in (
            ("/static/style1.css", "text/css"),
            ("/static/logo.png", "image/png"),
            ("/static/background.png", "image/png"),
        ):
            with self.subTest(path=path):
                with self.client.get(path) as response:
                    self.assertEqual(response.status_code, 200)
                    self.assertTrue(response.content_type.startswith(content_type))


class ProcessingTest(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def post(self, feature, **extra):
        image, filename = image_file()
        data = {"image": (image, filename), "feature": feature}
        data.update(extra)
        return self.client.post("/", data=data, content_type="multipart/form-data")

    def test_edit_feature_produces_result_and_download(self):
        response = self.post("grayscale")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Processed image", html)
        token_url = re.search(r'href="(/result/([a-f0-9]+))"', html)
        self.assertIsNotNone(token_url)
        self.assertEqual(self.client.get(token_url.group(1)).status_code, 200)
        download = self.client.get("/download/" + token_url.group(2))
        self.assertIn("attachment", download.headers["Content-Disposition"])

    def test_resize_is_clamped_server_side(self):
        response = self.post("resize", width="999999", height="1")
        self.assertEqual(response.status_code, 200)
        self.assertIn("4096 × 1 px", response.get_data(as_text=True))

    def test_editable_analysis(self):
        response = self.post("check_editable")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Detected format", html)
        self.assertIn("editable", html.lower())

    def test_ai_analysis_has_disclaimer(self):
        response = self.post("detect_ai")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("heuristic", html.lower())

    def test_invalid_feature_is_rejected(self):
        response = self.post("unknown_feature")
        self.assertEqual(response.status_code, 302)


class EnhanceStudioTest(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def post(self, **extra):
        image, filename = image_file(size=(40, 30))
        data = {"image": (image, filename)}
        data.update(extra)
        return self.client.post("/api/enhance", data=data, content_type="multipart/form-data")

    def test_studio_page_is_server_rendered(self):
        response = self.client.get("/enhance")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Real-time 2K &amp; 4K enhancement", html)
        self.assertIn("Auto Retouch (Remini-style)", html)
        self.assertIn("Portrait Retouch", html)
        self.assertIn("WebApplication", html)
        self.assertIn("liveCanvas", html)
        self.assertIn("Old Photo Restore", html)

    def test_retouch_feature_links_open_matching_studio_preset(self):
        for slug, preset in (("retouch", "portrait"), ("restore", "restore")):
            with self.subTest(slug=slug):
                detail = self.client.get(f"/features/{slug}").get_data(as_text=True)
                self.assertIn(f'href="/enhance?preset={preset}"', detail)
                studio = self.client.get(f"/enhance?preset={preset}").get_data(as_text=True)
                self.assertIn(f'<option value="{preset}" selected>', studio)

    def test_api_enhance_2k_portrait(self):
        with patch.object(enhancement, "TARGET_2K", 256):
            response = self.post(mode="2k", preset="portrait", sharpen="40",
                                 denoise="20", skin="60", clarity="30",
                                 vibrance="20", warmth="5")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual((data["width"], data["height"]), (256, 192))
        self.assertIn("data:image/jpeg;base64,", data["preview"])
        self.assertEqual(data["preset"], "portrait")
        self.assertEqual(data["mode"], "2k")
        self.assertTrue(data["stages"])
        self.assertIn("Upscaling", " ".join(s["message"] for s in data["stages"]))
        self.assertIn("attachment", self.client.get(data["download_url"]).headers["Content-Disposition"])

    def test_api_enhance_4k_with_invalid_preset_fallback(self):
        image, filename = image_file(size=(30, 40))
        with patch.object(enhancement, "TARGET_4K", 200):
            response = self.client.post("/api/enhance", data={
                "image": (image, filename), "mode": "4k", "preset": "not-a-preset",
            }, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["preset"], "auto_retouch")
        self.assertEqual(data["mode"], "4k")
        self.assertTrue(data["auto"])
        self.assertEqual((data["width"], data["height"]), (150, 200))

    def test_api_rejects_missing_or_bad_image(self):
        missing = self.client.post("/api/enhance", data={}, content_type="multipart/form-data")
        self.assertEqual(missing.status_code, 400)
        self.assertFalse(missing.get_json()["ok"])

        bad = self.client.post("/api/enhance", data={
            "image": (io.BytesIO(b"not an image"), "bad.png"),
        }, content_type="multipart/form-data")
        self.assertEqual(bad.status_code, 400)
        self.assertFalse(bad.get_json()["ok"])


class AutoEnhancementTest(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_auto_levels_improves_flat_contrast(self):
        array = np.zeros((48, 48, 3), dtype=np.uint8)
        for x in range(48):
            array[:, x, :] = 100 + int(x * 40 / 47)
        img = Image.fromarray(array, "RGB")
        output = enhancement.auto_levels(img, 0.8)
        self.assertGreater(np.asarray(output).std(), np.asarray(img).std())

    def test_auto_settings_are_bounded_and_report_quality(self):
        img = Image.new("RGB", (48, 48), (120, 130, 140))
        settings = enhancement.auto_settings(img, {"preset": "auto", "auto": True})
        self.assertIn("contrast", settings["_quality"])
        for key in ("denoise", "clarity", "sharpen", "vibrance"):
            self.assertGreaterEqual(settings[key], 0)
            self.assertLessEqual(settings[key], 100)

    def test_auto_retouch_is_one_click_and_reports_adaptive_stages(self):
        image, filename = image_file(size=(40, 30))
        with patch.object(enhancement, "TARGET_2K", 256):
            response = self.client.post("/api/enhance", data={
                "image": (image, filename), "mode": "2k", "preset": "auto_retouch",
            }, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["auto"])
        self.assertEqual(data["preset"], "auto_retouch")
        messages = [stage["message"] for stage in data["stages"]]
        self.assertTrue(any("Auto clear & adjust" in message for message in messages))
        self.assertTrue(any("adaptive" in message.lower() for message in messages))

    def test_classic_2k_button_uses_auto_pipeline(self):
        image, filename = image_file()
        with patch.object(enhancement, "auto_levels", wraps=enhancement.auto_levels) as auto:
            with patch.object(enhancement, "TARGET_2K", 256):
                response = self.client.post("/", data={
                    "image": (image, filename), "feature": "enhance_2k",
                }, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(auto.called)
        self.assertIn("256 × 256 px", response.get_data(as_text=True))

    def test_classic_4k_button_uses_auto_pipeline(self):
        image, filename = image_file()
        with patch.object(enhancement, "auto_levels", wraps=enhancement.auto_levels) as auto:
            with patch.object(enhancement, "TARGET_4K", 200):
                response = self.client.post("/", data={
                    "image": (image, filename), "feature": "enhance_4k",
                }, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(auto.called)


if __name__ == "__main__":
    unittest.main()
