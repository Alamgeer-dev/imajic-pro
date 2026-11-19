"""Smoke tests for the SSR pages, SEO endpoints and image processing."""

import io
import re
import unittest

from PIL import Image

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
        for slug in ("enhance_2k", "enhance_4k", "portrait", "cinematic_dark", "detect_ai"):
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


if __name__ == "__main__":
    unittest.main()
