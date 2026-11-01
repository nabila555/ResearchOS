# ResearchOS user guide

ResearchOS is a private research workspace that runs on your own computer. This guide walks
through a typical workflow, from importing papers to exporting a literature review.

> **How to read AI output in ResearchOS.** Every AI-generated statement is linked to the page it
> came from. Code checks each link: does the cited passage exist, does the quote appear in it, do
> the numbers match? Anything that fails is shown faded or marked **unverified / unsupported**.
> These checks prove *where* a statement comes from, not that the model understood it correctly,
> so open the cited page for anything important.

## 1. Start the app

Windows (PowerShell, in the `researchos` folder):

```powershell
.\start.ps1
```

macOS / Linux:

```bash
./start.sh
```

The first run installs everything (a few minutes). Then open **http://localhost:3000**. Press
`Ctrl+C` in the terminal to stop. Use `-Production` / `--production` for faster pages.

For AI features, install [Ollama](https://ollama.com) and download two free models once:

```bash
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

**Settings** shows whether Ollama and both models are detected.

## 2. Build your library

**Research Library → Add** (or drag files onto the page):
- **Upload files**: PDF, Word (.docx), Markdown, plain text. Duplicates are detected.
- **From URL**: web articles or direct PDF links (only public websites).
- **Note**: your own Markdown notes; they are searchable and usable by the assistant.

Title, authors, year, DOI, abstract, keywords and references are detected automatically. The
document page lists which details were *guessed from the text*. Check them with **Edit details**,
where you can also add journal, volume, issue, pages and publisher for citations.

Organise with **collections** (left sidebar of the library), **tags**, and **projects**. Search
covers titles, authors, abstracts and full text, and shows the matching page. Press **Ctrl+K**
anywhere for quick search.

In the background, documents are indexed for semantic search. Progress is shown in **Settings → AI
assistant**.

## 3. Ask questions — AI Assistant

Ask anything about your sources. Limit the search to a collection or project with the scope
picker. Answers cite numbered sources; click a number to read the passage, or open the document
at that page. You'll see:
- **Cites N sources**: every citation points to a passage that was actually provided.
- **Insufficient evidence**: your sources don't answer the question (the assistant won't guess).
- **Unverified**: the answer cited nothing; treat it with caution.

A local 8B model takes about 25–40 seconds per answer on a laptop CPU.

## 4. Understand papers — profiles, comparison, gaps, Detective

- **Paper profile** (document page → *Extract profile*): objective, research questions, framework,
  methods, data, sample size, population, findings, limitations, future research, each statement
  with a page link. About 3 minutes per paper locally; saved and reused everywhere.
- **Paper Comparison**: pick 2–6 papers for a side-by-side table.
- **Research Gap Finder**: run on a collection or 2–12 papers, with an optional focus. Items are
  labelled **Literature** (supported by named papers) or **AI hypothesis** (a suggestion to
  investigate).
- **Paper Detective** (document page): careful observations about claims, methods, possible bias
  and reproducibility. These are prompts for your own critical reading, not verdicts.

Analyses run in the background; you can leave the page. Each finished analysis becomes a report.

## 5. Connect ideas — Knowledge Graph

Shows how papers relate through authors, topics, shared keywords, similar content and shared
references. Click a node to see its connections; on a paper, **Methods & findings** adds its
verified profile statements as nodes. Use the layer buttons and similarity slider to reduce
clutter.

## 6. Write — Literature Review

1. **New review** with a title and research question; write your introduction.
2. Add **themes** and their sources, or use **Suggest themes** to group papers by similarity.
3. **Generate synthesis** per theme: a short comparison in which every sentence cites the papers
   in that theme. Highlighted sentences have no valid source.
4. **Export Markdown**, or **Save as report** to get a PDF from the Reports page. In-text
   citations and the reference list follow the review's citation style.

## 7. Cite — Citation Manager

Choose APA 7, MLA 9, Chicago or IEEE; copy one reference or a whole bibliography (italics are kept
when pasting into Word/Docs), or export **BibTeX**, **RIS** or Markdown. Missing details are
listed, never invented. Fix them with *Edit details* on the document. Check title capitalisation
yourself; titles are used exactly as stored.

## 8. Reports

**Reports** lists everything generated: comparisons, gap analyses, Detective runs, saved reviews,
and the reports from **New report**:
- **Research summary** (1–10 papers) and **Methodology analysis** (2–15 papers) are assembled
  from verified paper profiles, with no extra AI writing.
- **Research proposal** (2–12 papers, optionally building on a gap analysis) is drafted by the AI.
  The background must cite papers; research questions, methods and contributions are clearly
  marked as proposals.

Every report downloads as **Markdown** or **PDF** (created offline on your computer).

## Privacy

Your files, database and search index stay in the `data/` folder on this computer. Nothing is sent
anywhere unless you set an `ANTHROPIC_API_KEY` **and** tick the consent box in Settings. Even then,
only your question (or analysis input) and the matching passages are sent; whole files never are.
URL import downloads only the page you entered.

## Back up or reset

- **Back up:** stop the app and copy the `data/` folder.
- **Reset:** stop the app and delete `data/`. This permanently deletes your library.

Troubleshooting: see the table in [README.md](../README.md#troubleshooting).
