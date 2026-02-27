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
1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Run:
   ```
   python MusicScoreViewer.py
   ```

## Building the Windows Executable
Run `make.bat` from the project root. Requires PyInstaller and `icon.ico` to
be present in the same directory.

## Running the Tests

### Install test dependencies
```
pip install -r requirements-dev.txt
```

### Linux / WSL
```
python3 -m pytest -v
```

### Windows
```
python -m pytest -v
```

Some tests are platform-specific. On Linux/WSL, 4 Windows-only path tests
are skipped (56 of 60 pass). On Windows, 11 Linux/WSL-only tests are skipped
instead (49 of 60 pass).

### What the tests cover

| File | Total | Linux passes | Windows passes | What is tested |
|---|---|---|---|---|
| `tests/test_path_utils.py` | 22 | 18 | 12 | `normalize_path()` and `portable_path()`, including WSL↔Windows translation and round-trip invariants |
| `tests/test_rotation.py` | 17 | 17 | 17 | `_rotate_annotation_coords()` rotation transform maths: identity, known corners, CW/CCW inverse, composition, bounds |
| `tests/test_safe_json.py` | 21 | 21 | 20 | `SafeJSON.load()` and `SafeJSON.save()`: missing files, valid JSON, corrupt JSON, missing directory, atomic write, unicode, round-trips |

## Architecture

### Key classes and module-level constructs

| Name | Kind | Description |
|---|---|---|
| `SetlistSession` | dataclass | Holds all active setlist playback state (`name`, `items`, `index`, `start_page`, `end_page`). `None` on `MusicScoreApp._session` means library mode; set means setlist mode. |
| `_rotate_annotation_coords` | function | Rotates annotation coordinates in-place by N×90°. Used by `AnnotationManager` and tested directly in `tests/test_rotation.py`. |
| `AnnotationManager` | class | Owns annotation state (`annotations`, `rotations`, `_undo_stack`, `tool`, `pen_color`, `current_stroke`) and all persistence / mutation logic. Accessed via `app.annot`. |
| `MusicScoreApp` | class | Main Tk application controller. Delegates annotation work to `self.annot` and setlist state to `self._session`. |

### File formats

- **`setlists.json`** — setlist definitions; see `docs/setlist-file-format.md` for the full specification.
- **`<score>.json`** — annotation sidecar written alongside each PDF; versioned JSON containing per-page annotation lists and rotation overrides.
