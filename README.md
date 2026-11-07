# mdview

Render a Markdown file, including every Mermaid diagram type, to a self-contained
HTML page and open it in your browser. Works fully offline.

Terminal Markdown viewers (glow, mdcat, bat) show a ` ```mermaid ` block as raw
text. mdview renders it as an actual diagram, so it is useful for reviewing specs
and design docs where the diagrams carry the meaning.

## Quick start

```bash
git clone git@github.com:gitchadd/mdview.git
cd mdview
make demo                      # see all diagram types render
make mdview FILE=path/to/spec.md
```

No install step. The Markdown and diagram libraries are vendored in `vendor/`, so a
fresh clone renders offline with nothing to download.

Requirements: Python 3 (standard library only) and a browser.

## Usage

```bash
python3 bin/mdview.py <file.md> [--out PATH] [--no-open] [--theme THEME]
python3 bin/mdview.py --demo
```

| Option | Meaning |
|--------|---------|
| `--out PATH` | write the HTML here (default: `$TMPDIR/mdview/<hash>-<name>.html`) |
| `--no-open` | write the file but do not open a browser (headless / scripting) |
| `--theme T` | Mermaid theme: `neutral` (default, grayscale) \| `default` \| `dark` \| `forest` \| `base` |
| `--demo` | render a built-in doc covering many diagram types |

Or via make:

```bash
make mdview FILE=spec.md THEME=dark OUT=/tmp/spec.html
make demo
make test
```

## Supported diagrams

Everything Mermaid supports, since rendering is done by the canonical Mermaid
library rather than a reimplementation: flowchart, sequence, class, state, ER,
gantt, pie, gitGraph, mindmap, journey, quadrant, timeline, and more.

## How it works

The script only templates HTML. `marked` parses the Markdown and `mermaid` renders
the diagrams in the browser. Both libraries are inlined into the output, so the
page renders from a `file://` URL with no network access.

- The Markdown document is embedded as base64 and decoded at runtime. This makes it
  immune to a literal `</script>` or non-ASCII content breaking the page.
- After parsing, Mermaid code blocks are swapped to `<pre class="mermaid">` and
  drawn with `mermaid.run()`. This is independent of any specific marked or mermaid
  renderer-hook API, so it survives library upgrades.
- The default theme is `neutral` (grayscale), which reads well on any display.

## Refreshing the vendored libraries

The pinned builds are committed. To bump versions:

```bash
make vendor   # re-fetches marked@12.0.2 + mermaid@11.6.0 into vendor/
```

## Development

Tests are plain `unittest`, run with pytest. They cover HTML generation, base64
round-trip of adversarial content, vendor-lib resolution, and the CLI.

```bash
make test
```

## License

MIT. See [LICENSE](LICENSE).
