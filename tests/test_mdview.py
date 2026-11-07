#!/usr/bin/env python3
"""Red/green tests for mdview — Markdown+Mermaid -> self-contained HTML preview."""

import base64
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))

import mdview as mod


def _extract_b64(html):
    """Pull the base64 doc out of the generated HTML."""
    m = re.search(r'__MD_B64__\s*=\s*"([A-Za-z0-9+/=]*)"', html)
    assert m, "no __MD_B64__ constant found in generated HTML"
    return m.group(1)


class TestBuildHtml(unittest.TestCase):
    """build_html(markdown, marked_js, mermaid_js, ...) -> a full HTML document."""

    SAMPLE = "# Title\n\n```mermaid\ngraph TD; A-->B;\n```\n\nbody text\n"

    def test_is_a_full_html_document(self):
        html = mod.build_html(self.SAMPLE, "MARKED_SENTINEL", "MERMAID_SENTINEL")
        self.assertIn("<!doctype html>", html.lower())
        self.assertIn("</html>", html.lower())

    def test_inlines_both_libraries(self):
        html = mod.build_html(self.SAMPLE, "MARKED_SENTINEL", "MERMAID_SENTINEL")
        self.assertIn("MARKED_SENTINEL", html)
        self.assertIn("MERMAID_SENTINEL", html)

    def test_markdown_embedded_as_base64_roundtrips(self):
        html = mod.build_html(self.SAMPLE, "m", "m")
        decoded = base64.b64decode(_extract_b64(html)).decode("utf-8")
        self.assertEqual(decoded, self.SAMPLE)

    def test_adversarial_markdown_never_appears_raw(self):
        """A literal </script> or non-ASCII in the doc must not break the page."""
        nasty = "# x\n\nhere is </script><script>alert(1)</script> and unicode — é \U0001f600\n"
        html = mod.build_html(nasty, "m", "m")
        # The raw injection must not survive into the document body.
        self.assertNotIn("alert(1)", html)
        # ...but it must round-trip perfectly through base64.
        decoded = base64.b64decode(_extract_b64(html)).decode("utf-8")
        self.assertEqual(decoded, nasty)

    def test_has_mermaid_postprocess_and_run(self):
        html = mod.build_html(self.SAMPLE, "m", "m")
        self.assertIn("language-mermaid", html)   # finds marked's mermaid code blocks
        self.assertIn("mermaid.run", html)         # and renders them
        self.assertIn("marked.parse", html)        # markdown is actually parsed

    def test_title_is_used(self):
        html = mod.build_html(self.SAMPLE, "m", "m", title="my-spec.md")
        self.assertIn("<title>my-spec.md</title>", html)

    def test_theme_is_threaded_into_mermaid_init(self):
        html = mod.build_html(self.SAMPLE, "m", "m", theme="dark")
        self.assertIn("dark", html)
        self.assertIn("mermaid.initialize", html)


class TestVendor(unittest.TestCase):
    """Vendored libs are read from vendor/ (overridable via MDVIEW_VENDOR_DIR)."""

    def test_missing_lib_raises_actionable_error(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["MDVIEW_VENDOR_DIR"] = d
            try:
                with self.assertRaises(RuntimeError) as ctx:
                    mod.read_vendor_lib("mermaid.min.js")
                # error should tell the user how to fix it
                self.assertIn("mdview-vendor", str(ctx.exception))
            finally:
                del os.environ["MDVIEW_VENDOR_DIR"]

    def test_reads_existing_lib(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "marked.min.js"), "w") as f:
                f.write("VENDORED_CONTENT")
            os.environ["MDVIEW_VENDOR_DIR"] = d
            try:
                self.assertEqual(mod.read_vendor_lib("marked.min.js"), "VENDORED_CONTENT")
            finally:
                del os.environ["MDVIEW_VENDOR_DIR"]


class TestReadMarkdown(unittest.TestCase):
    def test_missing_file_exits_nonzero(self):
        with self.assertRaises(SystemExit) as ctx:
            mod.read_markdown("/no/such/file/at/all.md")
        self.assertNotEqual(ctx.exception.code, 0)

    def test_reads_utf8(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("# héllo\n")
            path = f.name
        try:
            self.assertEqual(mod.read_markdown(path), "# héllo\n")
        finally:
            os.unlink(path)


class TestMain(unittest.TestCase):
    """End-to-end orchestration with the browser opener stubbed out."""

    def setUp(self):
        # Point the vendor dir at a temp dir with stub libs so main() needs no real download.
        self._vendor = tempfile.mkdtemp()
        for name in ("marked.min.js", "mermaid.min.js"):
            with open(os.path.join(self._vendor, name), "w") as f:
                f.write("/* stub %s */" % name)
        os.environ["MDVIEW_VENDOR_DIR"] = self._vendor
        self._opened = []
        self._orig_open = mod.open_in_browser
        mod.open_in_browser = lambda p: self._opened.append(p)

    def tearDown(self):
        mod.open_in_browser = self._orig_open
        del os.environ["MDVIEW_VENDOR_DIR"]

    def _write_md(self, text):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
        f.write(text)
        f.close()
        return f.name

    def test_no_open_writes_file_and_does_not_open(self):
        src = self._write_md("# hi\n\n```mermaid\ngraph TD; A-->B;\n```\n")
        out = os.path.join(self._vendor, "out.html")
        try:
            rc = mod.main([src, "--out", out, "--no-open"])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(out))
            with open(out, encoding="utf-8") as fh:
                html = fh.read()
            self.assertIn("__MD_B64__", html)
            self.assertEqual(self._opened, [])  # opener not called
        finally:
            os.unlink(src)

    def test_opens_by_default(self):
        src = self._write_md("# hi\n")
        out = os.path.join(self._vendor, "out2.html")
        try:
            rc = mod.main([src, "--out", out])
            self.assertEqual(rc, 0)
            self.assertEqual(len(self._opened), 1)
            self.assertTrue(self._opened[0].endswith("out2.html"))
        finally:
            os.unlink(src)

    def test_demo_needs_no_input_file(self):
        out = os.path.join(self._vendor, "demo.html")
        rc = mod.main(["--demo", "--out", out, "--no-open"])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
