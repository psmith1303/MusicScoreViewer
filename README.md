# Music Score Viewer

A Python application to view, navigate, and annotate PDF music scores.

## Features
- Zoom-to-fit and side-by-side page view
- Per-page rotation (stored non-destructively in a sidecar file)
- Annotations: pen, text, eraser, with per-page undo
- Metadata search by composer, title, and folder tags
- Setlist management: create, reorder, and play through sets of scores
- Cross-platform: runs as a Windows executable or via Python on WSL/Linux

## Requirements
- Python 3.10+
- Dependencies listed in `requirements.txt`

## How to Run
1. Install dependencies: `pip install -r requirements.txt`
2. Run: `python MusicScoreViewer.py`

## Building the Windows Executable
Run `make.bat` from the project root. Requires PyInstaller and `icon.ico` to
be present in the same directory.
