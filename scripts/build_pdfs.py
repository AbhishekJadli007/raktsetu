"""Render the main documents to PDF (docs/pdf/), for submissions and sharing.

    pip install markdown-it-py playwright && python -m playwright install chromium
    python scripts/build_pdfs.py

Relative links become GitHub links so they work inside the PDF. Mermaid diagrams are drawn by mermaid.js.
"""
import asyncio
import re
from pathlib import Path

from markdown_it import MarkdownIt
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
REPO = "https://github.com/AbhishekJadli007/raktsetu/blob/main/"
DOCS = {
    "docs/PROJECT_EXPLAINER.md": "RaktSetu_Project_Explainer.pdf",
    "docs/SOLUTION_BRIEF.md": "RaktSetu_Solution_Brief.pdf",
}

CSS = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }
body { font-family: 'Inter', -apple-system, Segoe UI, sans-serif; font-size: 10.5pt; line-height: 1.5; color: #1a1d24; }
h1 { font-size: 22pt; margin: 0 0 4px; color: #9f1239; letter-spacing: -0.01em; }
h2 { font-size: 14pt; margin: 22px 0 6px; color: #9f1239; border-bottom: 1px solid #e5e7eb; padding-bottom: 4px; page-break-after: avoid; }
h3 { font-size: 11.5pt; margin: 14px 0 4px; page-break-after: avoid; }
p, li { margin: 4px 0; }
a { color: #0e7490; text-decoration: none; }
blockquote { margin: 10px 0; padding: 8px 12px; border-left: 3px solid #e11d48; background: #fff1f2; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; font-size: 9pt; page-break-inside: avoid; }
th, td { border: 1px solid #d9dde5; padding: 4px 6px; vertical-align: top; text-align: left; }
th { background: #f4f5f8; font-weight: 600; }
code { font-family: 'JetBrains Mono', Menlo, monospace; font-size: 8.5pt; background: #f4f5f8; padding: 1px 3px; border-radius: 3px; }
pre { background: #f4f5f8; padding: 8px 10px; border-radius: 6px; overflow: hidden; white-space: pre-wrap; page-break-inside: avoid; }
pre code { background: none; padding: 0; }
pre.mermaid { background: none; text-align: center; }
hr { border: none; border-top: 1px solid #e5e7eb; margin: 12px 0; }
em { color: #4b5563; }
"""


def to_html(md_path: Path) -> str:
    text = md_path.read_text()
    base = md_path.parent.relative_to(ROOT)

    def fix(m):
        label, target = m.group(1), m.group(2)
        if re.match(r"^(https?:|mailto:|#)", target):
            return m.group(0)
        resolved = (Path(base) / target).as_posix()
        parts = []
        for p in resolved.split("/"):
            if p == "..":
                parts and parts.pop()
            elif p != ".":
                parts.append(p)
        return f"[{label}]({REPO}{'/'.join(parts)})"

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", fix, text)
    body = MarkdownIt("commonmark").enable("table").render(text)
    body = re.sub(r'<pre><code class="language-mermaid">(.*?)</code></pre>', r'<pre class="mermaid">\1</pre>', body, flags=re.S)
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{md_path.stem}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono&display=swap" rel="stylesheet">
<style>{CSS}</style>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"></script>
</head><body>{body}
<script>mermaid.initialize({{startOnLoad: false, theme: 'neutral', flowchart: {{htmlLabels: true}}}});
mermaid.run().then(() => document.body.dataset.ready = '1').catch(() => document.body.dataset.ready = '1');</script>
</body></html>"""


async def main():
    out_dir = ROOT / "docs" / "pdf"
    out_dir.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        for src, name in DOCS.items():
            await page.set_content(to_html(ROOT / src), wait_until="networkidle")
            await page.wait_for_selector("body[data-ready='1']", timeout=20000)
            await page.pdf(path=str(out_dir / name), format="A4", print_background=True,
                           margin={"top": "18mm", "bottom": "18mm", "left": "16mm", "right": "16mm"})
            print("wrote", (out_dir / name).relative_to(ROOT))
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
