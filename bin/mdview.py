#!/usr/bin/env python3
"""mdview.py -- render a Markdown file (with ALL Mermaid diagram types) to a
self-contained HTML preview and open it in the browser.

Why this exists: the terminal here is greyscale/ASCII-only and cannot draw Mermaid
graphically -- terminal renderers (glow, mdcat, bat) show ```mermaid blocks as raw
text. This produces a real rendered page so a Markdown spec can be reviewed and
approved. It is invocable headlessly (`--out`, `--no-open`) so it can be driven by
an agent.

How it works: the script only templates HTML. Markdown is parsed by the vendored
`marked.min.js` and diagrams by the vendored `mermaid.min.js`, both inlined into the
output so the page renders fully offline from a file:// URL with zero network. The
Markdown doc is embedded as base64 and decoded at runtime, which makes it immune to
a literal </script> or non-ASCII in the document. After parsing, mermaid code blocks
are swapped to <pre class="mermaid"> and mermaid.run() draws them -- a
version-independent approach that needs no marked/mermaid renderer-hook API.

Self-contained, stdlib only. Vendor the libs once with `make mdview-vendor`.

Usage:
  mdview.py <file.md> [--out PATH] [--no-open] [--theme THEME]
  mdview.py --demo [--out PATH] [--no-open] [--theme THEME]
  mdview.py --help

Options:
  --out PATH     write the HTML here (default: $TMPDIR/mdview/<hash>-<name>.html)
  --no-open      write the file but do not open a browser (for headless/agent use)
  --theme THEME  mermaid theme: neutral (default, grayscale) | default | dark | forest | base
  --demo         render a built-in doc covering many Mermaid diagram types

Env:
  MDVIEW_VENDOR_DIR   override the vendored-libs dir (default: <repo>/vendor)
"""
import argparse
import base64
import hashlib
import os
import sys
import tempfile
import webbrowser

VENDOR_LIBS = ("marked.min.js", "mermaid.min.js")
DEFAULT_THEME = "neutral"  # grayscale; matches a greyscale display


def vendor_dir():
    """Directory holding the vendored JS libs (overridable for tests)."""
    override = os.environ.get("MDVIEW_VENDOR_DIR")
    if override:
        return override
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "vendor")


def read_vendor_lib(name):
    """Read a vendored JS lib, with an actionable error if it is missing."""
    path = os.path.join(vendor_dir(), name)
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise RuntimeError(
            "vendored library not found: %s\n"
            "Fetch the offline libs first:  make mdview-vendor" % path
        )


def read_markdown(path):
    """Read a UTF-8 Markdown file; exit non-zero with a clear message if missing."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        sys.stderr.write("mdview: no such file: %s\n" % path)
        raise SystemExit(2)
    except IsADirectoryError:
        sys.stderr.write("mdview: is a directory, not a file: %s\n" % path)
        raise SystemExit(2)


# Built-in sample exercising a broad set of Mermaid diagram types (used by --demo
# and by the end-to-end render check).
DEMO_MD = """# mdview demo

Rendered Markdown with **bold**, _italic_, `code`, a [link](https://example.com),
a table, and many Mermaid diagram types below.

| rail | region |
|------|--------|
| UPI  | India  |
| PIX  | Brazil |

## Flowchart
```mermaid
graph TD
  A[Order] --> B{Matched?}
  B -->|yes| C[Settle]
  B -->|no| D[Queue]
```

## Sequence
```mermaid
sequenceDiagram
  User->>Merchant: place order
  Merchant->>Chain: lock funds
  Chain-->>User: settled
```

## Class
```mermaid
classDiagram
  class Order { +id +amount settle() }
  Order <|-- BuyOrder
  Order <|-- SellOrder
```

## State
```mermaid
stateDiagram-v2
  [*] --> Open
  Open --> Settled
  Open --> Disputed
  Disputed --> Settled
  Settled --> [*]
```

## ER
```mermaid
erDiagram
  MERCHANT ||--o{ ORDER : fulfils
  ORDER ||--|{ SETTLEMENT : produces
```

## Gantt
```mermaid
gantt
  title Rollout
  section Phase
  Spec    :a1, 2026-06-01, 3d
  Build   :after a1, 5d
```

## Pie
```mermaid
pie title Revenue split
  "Operators" : 80
  "Treasury" : 20
```

## Git graph
```mermaid
gitGraph
  commit
  branch feat
  commit
  checkout main
  merge feat
```

## Mindmap
```mermaid
mindmap
  root((P2P))
    Rails
      UPI
      PIX
    Compliance
      ZK-KYC
```
"""


def build_html(markdown_text, marked_js, mermaid_js, title=None, theme=DEFAULT_THEME):
    """Return a complete, self-contained HTML document that renders `markdown_text`
    (Markdown + Mermaid) in the browser, with both libraries inlined.

    The Markdown is embedded as base64 so any content -- including a literal
    </script> or non-ASCII -- survives intact and cannot break the page.
    """
    if title is None:
        title = "mdview"
    b64 = base64.b64encode(markdown_text.encode("utf-8")).decode("ascii")

    # JS strings injected verbatim; keep them in a separate concat to avoid
    # f-string brace-escaping noise around the CSS/JS braces.
    head = (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>" + _escape_title(title) + "</title>\n"
        "<style>\n" + _CSS + "</style>\n"
        "</head>\n<body>\n"
        "<main id=\"content\" class=\"markdown-body\"></main>\n"
    )

    boot = (
        "<script>\n"
        "const __MD_B64__ = \"" + b64 + "\";\n"
        "const __MD__ = new TextDecoder().decode("
        "Uint8Array.from(atob(__MD_B64__), c => c.charCodeAt(0)));\n"
        "const __THEME__ = " + _js_string(theme) + ";\n"
        "(function () {\n"
        "  const html = (window.marked && (marked.parse ? marked.parse(__MD__)"
        " : marked(__MD__))) || __MD__;\n"
        "  document.getElementById('content').innerHTML = html;\n"
        "  document.querySelectorAll('code.language-mermaid').forEach(function (code) {\n"
        "    const host = code.closest('pre') || code;\n"
        "    const div = document.createElement('pre');\n"
        "    div.className = 'mermaid';\n"
        "    div.textContent = code.textContent;\n"
        "    host.replaceWith(div);\n"
        "  });\n"
        "  if (window.mermaid) {\n"
        "    mermaid.initialize({ startOnLoad: false, theme: __THEME__,"
        " securityLevel: 'loose' });\n"
        "    mermaid.run({ querySelector: 'pre.mermaid' });\n"
        "  }\n"
        "})();\n"
        "</script>\n"
    )

    return (
        head
        + "<script>\n" + marked_js + "\n</script>\n"
        + "<script>\n" + mermaid_js + "\n</script>\n"
        + boot
        + "</body>\n</html>\n"
    )


def _escape_title(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _js_string(s):
    """Minimal JS string literal."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


_CSS = """
:root { color-scheme: light dark; }
body {
  font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  max-width: 900px; margin: 2rem auto; padding: 0 1.25rem; color: #1b1f24;
  background: #fff;
}
h1, h2, h3, h4 { line-height: 1.25; margin-top: 1.6em; }
h1 { border-bottom: 1px solid #d0d7de; padding-bottom: .3em; }
h2 { border-bottom: 1px solid #d8dee4; padding-bottom: .3em; }
code { font: 13px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace;
  background: #f3f4f6; padding: .15em .35em; border-radius: 4px; }
pre { background: #f6f8fa; padding: 1rem; border-radius: 6px; overflow: auto; }
pre code { background: none; padding: 0; }
pre.mermaid { background: none; padding: .5rem 0; text-align: center; }
table { border-collapse: collapse; }
th, td { border: 1px solid #d0d7de; padding: .4em .7em; }
th { background: #f6f8fa; }
blockquote { color: #57606a; border-left: .25em solid #d0d7de; margin: 0; padding: 0 1em; }
a { color: #0969da; }
img { max-width: 100%; }
@media (prefers-color-scheme: dark) {
  body { background: #0d1117; color: #e6edf3; }
  code, pre { background: #161b22; }
  th { background: #161b22; }
  a { color: #58a6ff; }
}
"""


def open_in_browser(path):
    """Open a local HTML file in the default browser. Isolated for testability."""
    url = "file://" + os.path.abspath(path)
    webbrowser.open(url)


def default_out_path(src_path):
    """Deterministic temp path so re-renders of the same file overwrite."""
    abspath = os.path.abspath(src_path)
    h = hashlib.sha1(abspath.encode("utf-8")).hexdigest()[:8]
    base = os.path.basename(src_path) or "doc.md"
    name = "%s-%s.html" % (h, base)
    out_dir = os.path.join(tempfile.gettempdir(), "mdview")
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, name)


def render(markdown_text, out_path, title=None, theme=DEFAULT_THEME):
    """Build the HTML for `markdown_text` and write it to `out_path`."""
    marked_js = read_vendor_lib("marked.min.js")
    mermaid_js = read_vendor_lib("mermaid.min.js")
    html = build_html(markdown_text, marked_js, mermaid_js, title=title, theme=theme)
    out_dir = os.path.dirname(os.path.abspath(out_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="mdview",
        description="Render a Markdown file (with all Mermaid diagram types) to a "
        "self-contained HTML preview and open it in the browser.",
    )
    parser.add_argument("file", nargs="?", help="path to a .md file")
    parser.add_argument("--out", help="output HTML path (default: $TMPDIR/mdview/...)")
    parser.add_argument("--no-open", action="store_true",
                        help="write the file but do not open a browser")
    parser.add_argument("--theme", default=DEFAULT_THEME,
                        help="mermaid theme: neutral|default|dark|forest|base")
    parser.add_argument("--demo", action="store_true",
                        help="render a built-in doc covering many Mermaid diagram types")
    args = parser.parse_args(argv)

    if args.demo:
        md = DEMO_MD
        title = "mdview demo"
        src_for_out = "mdview-demo.md"
    else:
        if not args.file:
            parser.error("a Markdown file is required (or use --demo)")
        md = read_markdown(args.file)
        title = os.path.basename(args.file)
        src_for_out = args.file

    out_path = args.out or default_out_path(src_for_out)
    render(md, out_path, title=title, theme=args.theme)

    if args.no_open:
        sys.stdout.write("%s\n" % out_path)
    else:
        open_in_browser(out_path)
        sys.stderr.write("mdview: opened %s\n" % out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
