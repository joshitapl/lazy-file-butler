# Lazy File Butler

A local file organizer: choose a folder, review AI filenames and categories, then move only the files you approve. Every batch has an undo record.

## Run

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open **http://localhost:8002**. On this workspace, the existing environment also works: `../sloth/.venv/bin/python app.py`, or double-click `start.command`.

**No additional model is required or downloaded by the app.** Start the installed Ollama app and select an already-installed text model in **Engine & settings**. This installation uses `llama3.2:1b`. Its small size limits suggestion quality; review the actual filenames and source evidence.

## Main workflow

1. Choose a folder using **Browse folders**, the Desktop/Downloads/Documents shortcuts, or a pasted absolute path.
2. Click **Analyze folder**. Nothing moves during analysis. Stop after the current file if needed.
3. Review filenames, categories, and extracted text. Search and filter by AI suggestions, file-type placement, or items needing attention. Edits and selections survive filter changes.
4. AI suggestions are preselected. File-type placements and reader errors are not; explicitly select those if you want to include them. All readable files can be named manually.
5. Click **Review & organize** to inspect the concrete list of moves, then confirm. Files move to `Organized/<category>/` inside the selected folder.
6. Use **Activity & undo** to restore original filenames and locations.

## Document reading

- **PDFs:** checks the first 12 pages and several later pages for a text layer. If insufficient, OCR samples up to 8 pages (front, later, and middle pages).
- **Scanned PDFs and screenshots:** English OCR uses macOS Vision when the local helper is available; otherwise the existing Tesseract executable. The app does not download OCR models.
- **Word:** reads text in `.docx` without Microsoft Word.
- **Text:** TXT, Markdown, CSV, JSON, code files, logs, YAML and related formats.
- **Other files:** installers, archives, audio/video and images without readable text get extension-based folder placement, preserving the original name. They are labelled **By file type**, never AI.
- **Manual review:** if reading or inference fails, the original name and a suggested folder remain editable. The app explains the problem instead of disabling all controls.

For handwritten notes, OCR can misread text. PDF/image OCR suggestions are shown as needing attention; inspect the extracted text. The app does not understand photo subjects or guarantee complete document reading. Content extraction is bounded to sampled excerpts and files up to 80 MB. Larger files can still be sorted by type.

On macOS with an existing Swift compiler, app startup builds a small bridge to the built-in Vision framework in `data/macos-ocr`. This compiles the included source, not a downloaded model or service. If unavailable, Tesseract remains a fallback. Nothing installs automatically. Other operating systems require an existing Tesseract installation for OCR.

## Local AI and validation

The selected Ollama model receives extracted text and returns a filename, category, reason, and self-reported confidence. Python validates names/categories, retries invalid or generic names once, rejects invented years, and sanitizes paths. Narrow document-type checks correct obvious conflicts such as examination papers labelled as bills, or digital-logic PDF notes labelled as source code; those corrections are marked for review. These checks do not make the AI infallible. Confidence is a model assertion, not measured accuracy.

Extraction and suggestions are cached locally, keyed by content, model, and reader/prompt version, to avoid repeating the same work. The app never downloads or silently switches models. Multiple tabs can reconnect to an active scan. Interrupted analysis must be restarted; completed previews and move journals persist.

## Moves and undo

- Up to 100 files per batch; hidden files, symbolic links, `.git`, `.venv`, `node_modules`, and existing `Organized` folders are skipped.
- Preflight checks hashes and destination collisions before moving files.
- Existing files are never overwritten; category destinations are restricted and path boundaries are checked.
- Each move is journaled before and after execution. Same-filesystem exclusive hard-link/unlink operations preserve contents and refuse collisions. Unsupported filesystems stop safely; completed moves remain undoable.
- Undo checks hashes and original locations. If an organized file was edited or an old path is occupied, it stops to protect those edits. Resolve the conflict before retrying. Empty category folders may remain.
- Undo is not a substitute for a backup. A folder path must be a specific directory, not the entire home or filesystem root.

## Privacy and open innovation

Document excerpts go to Ollama at `127.0.0.1:11434`, not a hosted inference provider. OCR runs on this computer. After setup, the local inference workflow can operate offline. You can inspect prompts, change categories, and select existing compatible open-weight models. No per-call inference provider fee is required; hardware and electricity still have costs.

The frontend loads no remote fonts, analytics, or other assets. The web server binds to loopback and checks origins and per-process tokens for mutations. It is intended for one user's laptop; do not expose its port publicly. Extracted text, previews, and file paths are stored locally in `data/butler.db`; `data/` is excluded from source control. Model and dependency licenses remain separate from this project's MIT source license.

## Validation

```sh
python -m unittest discover -s tests -v
```

Twenty-two checks cover content-preserving move/undo, partial failures, interrupted links, changed files, path collisions, symlinks, later PDF pages, OCR fallback, images, file-type placement, model caches, invalid names, and category consistency. Live testing has also checked local OCR on printed and handwritten PDFs. Naming quality still depends on OCR clarity and the installed model.

## Files

- `app.py`: local API, folder browser, progress, cancellation and history.
- `butler.py`: model gateway, caches, consistency checks, safe moves and journal.
- `readers.py`: PDF, image, text and Word extraction.
- `native/ocr.swift`: optional bridge to macOS Vision.
- `static/`: responsive interface, no build step or remote dependencies.
- `tests/`: temporary-file regression tests.

The sibling Sloth and StudySloth apps are preserved. See `DEMO.md` for a submission recording guide.
