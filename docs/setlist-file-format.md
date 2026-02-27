# Setlist File Format

**File:** `setlists.json` (written to the writable app directory alongside `config.json`)

---

## Overview

The setlist file stores all user-defined setlists as a single JSON object.
Each key is a setlist name (string); each value is an ordered array of song items.

---

## Top-level structure

```json
{
  "Setlist Name A": [ <item>, <item>, ... ],
  "Setlist Name B": [ <item>, ... ]
}
```

| Field | Type | Description |
|---|---|---|
| key | string | Setlist name, as entered by the user. Must be unique. |
| value | array | Ordered list of song items (may be empty). |

---

## Song item object

Each element of a setlist array is a JSON object with the following fields:

| Field | Type | Required | Description |
|---|---|---|---|
| `path` | string | **yes** | Portable path to the PDF file (see [Path encoding](#path-encoding)). |
| `title` | string | **yes** | Display title shown in the UI and window title bar. |
| `composer` | string | **yes** | Composer name (may be empty string `""`). |
| `start_page` | integer | **yes** | 1-based page number where playback of this item begins. Minimum value: `1`. |
| `end_page` | integer \| null | **yes** | 1-based page number where playback ends (inclusive). `null` means "last page of the PDF". |

### Constraints

- `start_page` ≥ 1.
- `end_page` ≥ `start_page`, or `null`.
- If `start_page` exceeds the actual page count of the PDF at runtime, the viewer clamps it to `0` (first page, 0-based internally).
- If `end_page` exceeds the actual page count, the viewer clamps it to `total_pages - 1` (0-based internally).

### Minimal valid item

```json
{
  "path": "Z:/Music/Scores/Bach/Goldberg.pdf",
  "title": "Goldberg Variations",
  "composer": "Bach",
  "start_page": 1,
  "end_page": null
}
```

### Item with page constraints

```json
{
  "path": "/mnt/z/Music/Scores/Bach/Goldberg.pdf",
  "title": "Aria",
  "composer": "Bach",
  "start_page": 3,
  "end_page": 4
}
```

---

## Path encoding

Paths are stored in **portable form** (function `portable_path()`):

- Forward slashes only — no backslashes, so no escaping is needed in JSON.
- Windows absolute paths keep the drive letter: `Z:/PARA/Scores/foo.pdf`
- WSL/Linux mount paths are kept as-is: `/mnt/z/PARA/Scores/foo.pdf`

At read time, `normalize_path()` converts to the OS-native format and translates
between Windows (`Z:/...`) and WSL (`/mnt/z/...`) automatically, so a setlist
saved on Windows loads correctly on WSL and vice versa.

---

## Full example

```json
{
  "Sunday Service": [
    {
      "path": "Z:/Music/Hymns/Amazing Grace.pdf",
      "title": "Amazing Grace",
      "composer": "Newton",
      "start_page": 1,
      "end_page": null
    },
    {
      "path": "Z:/Music/Hymns/How Great Thou Art.pdf",
      "title": "How Great Thou Art",
      "composer": "Boberg",
      "start_page": 2,
      "end_page": 5
    }
  ],
  "Concert Programme": [
    {
      "path": "Z:/Music/Classical/Moonlight Sonata.pdf",
      "title": "Moonlight Sonata (1st mvt)",
      "composer": "Beethoven",
      "start_page": 1,
      "end_page": 6
    }
  ]
}
```

---

## File location

The file is written to the **writable app directory**, resolved at startup by
`get_writable_app_dir()` in the following priority order:

1. Same directory as the executable / script (portable mode).
2. `~/.music_score_viewer/` (user home, if the app directory is read-only).
3. System temp directory (last resort).

The path constant `SETLIST_PATH` in the source is
`os.path.join(APP_DIR, "setlists.json")`.

---

## Persistence

- Loaded once at startup via `SafeJSON.load(SETLIST_PATH)`.
- Written after every mutation (add setlist, rename, delete, reorder, add/remove
  song) via `SafeJSON.save(SETLIST_PATH, self.setlists)`.
- `SafeJSON` writes atomically (temp file + `os.replace`) to avoid corruption on
  power loss.
- If the file is absent, `SafeJSON.load` returns `{}` (no setlists).
- If the file is corrupt JSON, a warning dialog is shown and `{}` is returned.

---

## Editing by hand

The file is plain JSON and can be edited in any text editor.
Guidelines:

- Ensure the top-level structure is a JSON **object** (curly braces), not an array.
- Each setlist value must be a JSON **array** (square brackets), even if empty (`[]`).
- `end_page` must be a JSON integer **or** the JSON literal `null` — not an empty
  string.
- Paths should use forward slashes.  Backslashes will be normalised at read time
  but are harder to read.
- There is no version field in this file; it is always the current format.
