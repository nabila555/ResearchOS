"""Builders for realistic sample documents used in tests (generated, no binary fixtures)."""

from pathlib import Path

import docx
import pymupdf

PAPER_TITLE = "Sleep Spindles Predict Overnight Memory Consolidation"
PAPER_AUTHORS = ["Ada Lovelace", "Alan M. Turing", "Grace Hopper"]
ABSTRACT = (
    "We investigated whether sleep spindle density predicts overnight retention of "
    "declarative memories in healthy adults. Using polysomnography in 48 participants, "
    "we found that spindle density during slow-wave sleep correlated with recall."
)
METHODS = (
    "Participants learned 120 word pairs before sleep. Polysomnography recorded EEG. "
    "Spindles were detected automatically with a validated algorithm. "
) * 6
RESULTS = (
    "Spindle density correlated with retention (r = 0.52, p < 0.001). The effect remained "
    "after controlling for total sleep time and age. "
) * 6


def write_paper_pdf(path: Path, *, with_metadata: bool = False) -> Path:
    doc = pymupdf.open()
    page = doc.new_page()
    y = 72
    page.insert_text((72, y), "Sleep Spindles Predict Overnight", fontsize=20)
    y += 26
    page.insert_text((72, y), "Memory Consolidation", fontsize=20)
    y += 30
    page.insert_text((72, y), "Ada Lovelace1, Alan M. Turing2 and Grace Hopper1*", fontsize=11)
    y += 16
    page.insert_text((72, y), "1 Department of Psychology, Example University", fontsize=9)
    y += 14
    page.insert_text(
        (72, y),
        "Published online: 12 March 2021 · https://doi.org/10.1234/jsr.2021.0042",
        fontsize=9,
    )
    y += 30
    body = (
        f"Abstract\n{ABSTRACT}\n\nKeywords: sleep spindles; memory consolidation; EEG\n\n"
        f"1 Introduction\nSleep supports memory. " * 1
    )
    page.insert_textbox(pymupdf.Rect(72, y, 540, 760), body, fontsize=10)
    page2 = doc.new_page()
    page2.insert_textbox(pymupdf.Rect(72, 72, 540, 760), f"2 Methods\n{METHODS}", fontsize=10)
    page3 = doc.new_page()
    page3.insert_textbox(pymupdf.Rect(72, 72, 540, 760), f"3 Results\n{RESULTS}", fontsize=10)
    page4 = doc.new_page()
    refs = (
        "References\n"
        "[1] Walker, M. P. (2009). Slow wave sleep in memory processing. J Clin Sleep Med.\n"
        "[2] Diekelmann, S., & Born, J. (2010). The memory function of sleep. Nat Rev Neurosci.\n"
        "[3] Rasch, B., & Born, J. (2013). About sleep's role in memory. Physiol Rev.\n"
    )
    page4.insert_textbox(pymupdf.Rect(72, 72, 540, 760), refs, fontsize=10)
    if with_metadata:
        doc.set_metadata({"title": PAPER_TITLE, "author": "; ".join(PAPER_AUTHORS)})
    else:
        doc.set_metadata({"title": "paper_final_v3.pdf", "author": "jsmith"})
    doc.save(path)
    doc.close()
    return path


def write_docx(path: Path) -> Path:
    document = docx.Document()
    document.core_properties.title = "Field Notes on Coral Bleaching"
    document.core_properties.author = "Rachel Carson"
    document.add_heading("Field Notes on Coral Bleaching", level=0)
    document.add_heading("Introduction", level=1)
    document.add_paragraph("Coral reefs bleach when water temperatures rise. " * 10)
    document.add_heading("Methods", level=1)
    document.add_paragraph("We surveyed 30 transects across three reefs. " * 10)
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Reef"
    table.cell(0, 1).text = "Bleached %"
    table.cell(1, 0).text = "North"
    table.cell(1, 1).text = "42"
    document.save(path)
    return path
