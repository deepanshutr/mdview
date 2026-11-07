.PHONY: help list mdview demo vendor test

# Default: show usage
help: list

list:
	@echo "mdview -- render Markdown + Mermaid to a self-contained HTML preview"
	@echo ""
	@echo "  make mdview FILE=<file.md> [THEME=t] [OUT=f.html]  -- render and open in browser"
	@echo "  make demo [THEME=t]                                -- render the built-in demo (many diagram types)"
	@echo "  make vendor                                        -- refresh the offline JS libs in vendor/"
	@echo "  make test                                          -- run the test suite"
	@echo ""
	@echo "THEME: neutral (default, grayscale) | default | dark | forest | base"

# Render a Markdown file (with all Mermaid diagram types) to HTML and open it.
mdview:
	python3 bin/mdview.py $(FILE) $(if $(THEME),--theme $(THEME)) $(if $(OUT),--out $(OUT))

# Render the built-in demo doc and open it.
demo:
	python3 bin/mdview.py --demo $(if $(THEME),--theme $(THEME))

# Refresh the pinned offline libs (already committed; only needed to bump versions).
vendor:
	@mkdir -p vendor
	curl -fsSL "https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js" -o vendor/marked.min.js
	curl -fsSL "https://cdn.jsdelivr.net/npm/mermaid@11.6.0/dist/mermaid.min.js" -o vendor/mermaid.min.js
	@echo "Vendored marked@12.0.2 + mermaid@11.6.0 into vendor/"

# Run the test suite.
test:
	python3 -m pytest tests/ -v
