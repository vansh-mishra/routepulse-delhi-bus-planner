from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class FrontendConfigurationTests(unittest.TestCase):
    def test_theme_toggle_is_in_global_navigation(self):
        base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertIn('id="theme-toggle"', base)
        self.assertIn("theme.js", base)

    def test_theme_preference_is_persisted(self):
        script = (ROOT / "static" / "theme.js").read_text(encoding="utf-8")
        self.assertIn("localStorage.setItem('routepulse-theme'", script)
        self.assertIn("localStorage.getItem(\"routepulse-theme\")", (ROOT / "templates" / "base.html").read_text(encoding="utf-8"))

    def test_map_uses_keyless_openstreetmap_tiles_and_attribution(self):
        planner = (ROOT / "static" / "planner.js").read_text(encoding="utf-8")
        self.assertIn("https://tile.openstreetmap.org/{z}/{x}/{y}.png", planner)
        self.assertIn("OpenStreetMap contributors", planner)
        self.assertNotIn("maptiler", planner.lower())
        self.assertNotIn("mapbox", planner.lower())
        self.assertNotIn("google.com/maps", planner.lower())

    def test_video_and_readiness_guides_exist(self):
        self.assertTrue((ROOT / "docs" / "demo_video_guide.md").is_file())
        self.assertTrue((ROOT / "docs" / "submission_readiness.md").is_file())

if __name__ == "__main__":
    unittest.main()
