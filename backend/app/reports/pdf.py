"""Markdown → PDF, fully offline, using PyMuPDF's HTML layout engine (Story).

Raw HTML in the Markdown is disabled, so report content cannot inject markup.
"""

import io
from datetime import datetime

import pymupdf
from markdown_it import MarkdownIt

_MARKDOWN = MarkdownIt("commonmark", {"html": False, "typographer": True}).enable(
    ["table", "strikethrough"]
)

CSS = """
body { font-family: sans-serif; font-size: 10pt; line-height: 1.45; color: #1f2328; }
h1 { font-size: 18pt; margin: 0 0 10pt 0; }
h2 { font-size: 13pt; margin: 16pt 0 6pt 0; border-bottom: 1px solid #d0d7de; padding-bottom: 2pt; }
h3 { font-size: 11pt; margin: 12pt 0 4pt 0; }
p { margin: 0 0 7pt 0; }
ul, ol { margin: 0 0 7pt 0; }
li { margin-bottom: 2pt; }
table { border-collapse: collapse; margin: 6pt 0 10pt 0; width: 100%; }
th, td { border: 1px solid #c8ccd1; padding: 3pt 4pt; vertical-align: top; font-size: 8.5pt; }
th { background-color: #f3f4f6; text-align: left; }
blockquote { margin: 6pt 0; padding-left: 8pt; color: #57606a; border-left: 2px solid #d0d7de; }
code { font-family: monospace; font-size: 9pt; }
hr { border: 0; border-top: 1px solid #d0d7de; margin: 12pt 0; }
em { font-style: italic; }
"""

PAGE = pymupdf.paper_rect("a4")
MARGIN = 56  # points (~2 cm)


def markdown_to_html(markdown: str) -> str:
    return _MARKDOWN.render(markdown)


def markdown_to_pdf(markdown: str, title: str) -> bytes:
    story = pymupdf.Story(html=markdown_to_html(markdown), user_css=CSS)
    buffer = io.BytesIO()
    writer = pymupdf.DocumentWriter(buffer)
    content = PAGE + (MARGIN, MARGIN, -MARGIN, -MARGIN)
    more = True
    while more:
        device = writer.begin_page(PAGE)
        more, _ = story.place(content)
        story.draw(device)
        writer.end_page()
    writer.close()

    # Footer with title and page numbers, plus document metadata.
    document = pymupdf.open(stream=buffer.getvalue(), filetype="pdf")
    total = document.page_count
    footer_title = title if len(title) <= 80 else title[:77] + "…"
    for index, page in enumerate(document):
        y = PAGE.height - MARGIN / 2
        page.insert_text((MARGIN, y), footer_title, fontsize=7.5, color=(0.45, 0.45, 0.45))
        label = f"{index + 1} / {total}"
        width = pymupdf.get_text_length(label, fontsize=7.5)
        page.insert_text(
            (PAGE.width - MARGIN - width, y), label, fontsize=7.5, color=(0.45, 0.45, 0.45)
        )
    document.set_metadata(
        {
            "title": title,
            "creator": "ResearchOS",
            "producer": "ResearchOS (PyMuPDF)",
            "creationDate": pymupdf.get_pdf_now(),
            "subject": f"Generated {datetime.now():%Y-%m-%d}",
        }
    )
    data = document.tobytes(garbage=3, deflate=True)
    document.close()
    return data
