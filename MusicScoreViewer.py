#!/usr/bin/env python3
"""
Music Score Viewer
==================
Version: 1.1c

A robust Python application to view and annotate PDF music scores.

Improvements in this version:
1. "Zoom to Fit": Ensures the full page is always visible (no cropping).
2. Centering: Pages are centered in the window if aspect ratios differ.
3. Performance: Separated PDF rasterization from Vector drawing.
4. Robustness: Atomic file saving to prevent JSON corruption.
5. Data Integrity: Uses UUIDs for annotations.

Usage:
    python music_score_viewer.py [options]
    OR (on Linux/Mac):
    ./music_score_viewer.py [options]
"""

import sys
import os
import json
import logging
import argparse
import uuid
import tempfile
import shutil
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox

# --- Constants & Config ---
APP_VERSION = "1.1c"
ANNOTATION_VERSION = 2
DEFAULT_WIN_SIZE = "1200x900"
BG_COLOR = "#333333"
TOOLBAR_COLOR = "#e0e0e0"

# Symbols triggering smart-sizing (6.0x multiplier)
MUSICAL_SYMBOLS_SET = {
    "\U0001D15E", # Minim
    "♩", "♩.", "♪", 
    "pp", "p", "mp", "mf", "f", "ff", 
    "sfz", "cresc", "dim"
}

# --- Parsing Command Line Arguments ---
def parse_arguments():
    parser = argparse.ArgumentParser(
        description=f"Music Score Viewer v{APP_VERSION}: Robust PDF viewer and annotator.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Show informational messages.")
    parser.add_argument("-D", "--debug", action="store_true", help="Show detailed debug messages.")
    parser.add_argument("-l", "--log-file", type=str, help="Path to a log file.")
    parser.add_argument("-d", "--dir", type=str, help="Open this directory immediately.")
    parser.add_argument("-t", "--title-first", action="store_true", help="Sort by Title first.")
    
    args, unknown = parser.parse_known_args()
    return args

# --- Setup Logging ---
def setup_logging(args):
    handlers = []
    if args.log_file:
        handlers.append(logging.FileHandler(args.log_file, mode='w'))
    else:
        handlers.append(logging.StreamHandler(sys.stdout))

    level = logging.WARNING
    if args.verbose: level = logging.INFO
    if args.debug: level = logging.DEBUG

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers
    )

args = parse_arguments()
setup_logging(args)

# --- Import Libraries with Error Handling ---
try:
    import pymupdf as fitz
    logging.info(f"PyMuPDF imported (v{fitz.VersionBind})")
except ImportError:
    logging.critical("PyMuPDF not found. Run: pip install pymupdf")
    sys.exit(1)

try:
    from PIL import Image, ImageTk
    logging.info("Pillow imported successfully.")
except ImportError:
    logging.critical("Pillow not found. Run: pip install Pillow")
    sys.exit(1)


# --- Helper Classes ---

class SafeJSON:
    """Handles Atomic writes to prevent data corruption."""
    @staticmethod
    def load(filepath):
        if not os.path.exists(filepath):
            return {}
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logging.error(f"Corrupted JSON file: {filepath}")
            return {}
        except Exception as e:
            logging.error(f"Error reading JSON: {e}")
            return {}

    @staticmethod
    def save(filepath, data):
        """Writes to a temp file first, then moves it to destination."""
        dir_name = os.path.dirname(filepath)
        try:
            # Create temp file in the same directory to ensure atomic move works across filesystems
            with tempfile.NamedTemporaryFile('w', dir=dir_name, delete=False, encoding='utf-8') as tmp:
                json.dump(data, tmp, indent=2)
                tmp_name = tmp.name
            
            # Atomic replace
            shutil.move(tmp_name, filepath)
        except Exception as e:
            logging.error(f"Failed to save JSON atomically: {e}")
            if 'tmp_name' in locals() and os.path.exists(tmp_name):
                os.remove(tmp_name)

class TextEntryDialog(tk.Toplevel):
    """Modal dialog for text entry with music symbols."""
    def __init__(self, parent, title="Add Text", initial_color="black", initial_text="", initial_font="New Century Schoolbook"):
        super().__init__(parent)
        self.transient(parent)
        self.title(title)
        self.result = None
        self.initial_color = initial_color
        
        # UI Setup
        self.update_idletasks()
        x = parent.winfo_rootx() + 50
        y = parent.winfo_rooty() + 50
        self.geometry(f"+{x}+{y}")
        self._setup_ui(initial_text, initial_font)
        
        # Robust focus grabbing
        self.wait_visibility()
        self.grab_set()
        self.entry.focus_set()
        self.entry.icursor(tk.END)
        self.wait_window(self)

    def _setup_ui(self, initial_text, initial_font):
        # 1. Text Entry
        f_input = tk.Frame(self, padx=10, pady=10)
        f_input.pack(fill=tk.X)
        tk.Label(f_input, text="Text:").pack(side=tk.LEFT)
        self.entry = tk.Entry(f_input, width=40)
        self.entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        if initial_text: self.entry.insert(0, initial_text)

        # 2. Font Selector
        f_font = tk.Frame(self, padx=10, pady=5)
        f_font.pack(fill=tk.X)
        tk.Label(f_font, text="Font:").pack(side=tk.LEFT)
        
        fonts = sorted(list(tkfont.families()))
        curr = initial_font if initial_font in fonts else "Arial"
        
        self.var_font = tk.StringVar(value=curr)
        self.combo_font = ttk.Combobox(f_font, textvariable=self.var_font, values=fonts, state="readonly")
        self.combo_font.pack(side=tk.LEFT, padx=5)

        # 3. Symbol Palette
        f_sym = tk.LabelFrame(self, text="Symbols", padx=5, pady=5)
        f_sym.pack(fill=tk.X, padx=10, pady=5)

        symbols = [
            ("Minim", "\U0001D15E"), ("Crotchet", "♩"), ("D.Crotchet", "♩."), ("Quaver", "♪"),
            ("pp", "pp"), ("p", "p"), ("mp", "mp"), ("mf", "mf"), ("f", "f"), ("ff", "ff")
        ]

        r, c = 0, 0
        MAX_COLS = 5
        btn_f = tkfont.Font(family="Times New Roman", size=14, weight="bold")

        for name, char in symbols:
            # Render 'Minim' text if glyph usually fails, else char
            display = "𝅗𝅥" if "Minim" in name else char
            is_dyn = len(char) > 1 and char[0] in "mpf"
            f_style = tkfont.Font(family="Times New Roman", size=14, weight="bold", slant="italic" if is_dyn else "roman")
            
            btn = tk.Button(f_sym, text=display, font=f_style, width=4, 
                            command=lambda ch=char: self._insert(ch))
            btn.grid(row=r, column=c, padx=2, pady=2, sticky="ew")
            c += 1
            if c >= MAX_COLS: c=0; r+=1

        # 4. Action Buttons
        f_btn = tk.Frame(self, padx=10, pady=10)
        f_btn.pack(fill=tk.X)
        tk.Button(f_btn, text="Cancel", command=self.destroy).pack(side=tk.RIGHT, padx=5)
        tk.Button(f_btn, text="OK", command=self._on_ok).pack(side=tk.RIGHT, padx=5)

    def _insert(self, char):
        self.entry.insert(tk.INSERT, char)
        self.entry.focus_set()

    def _on_ok(self):
        txt = self.entry.get()
        if txt:
            self.result = {"text": txt, "font": self.var_font.get()}
        self.destroy()

class Score:
    """Data class for a music score file."""
    __slots__ = ['filepath', 'filename', 'composer', 'title', 'tags']
    
    def __init__(self, filepath, filename, folder_tags=None):
        self.filepath = filepath
        self.filename = filename
        self.composer = "Unknown"
        self.title = ""
        self.tags = set()
        if folder_tags: self.tags.update(folder_tags)
        self._parse()

    def _parse(self):
        try:
            base = os.path.splitext(self.filename)[0]
            if " -- " in base:
                parts = base.split(" -- ")
                base = parts[0]
                if len(parts) > 1:
                    self.tags.update({t for t in parts[1].split(" ") if t})
            
            if " - " in base:
                parts = base.split(" - ")
                self.composer = parts[0].strip()
                self.title = parts[1].strip() if len(parts) > 1 else ""
            else:
                self.title = base.strip()
        except Exception:
            logging.warning(f"Could not parse filename: {self.filename}")

class CompactTagFrame(tk.Frame):
    """Grid of checkboxes for tags."""
    def __init__(self, master, callback, **kwargs):
        super().__init__(master, **kwargs)
        self.callback = callback
        self.vars = {}
        
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.frame = tk.Frame(self.canvas)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas_win = self.canvas.create_window((0,0), window=self.frame, anchor="nw")
        
        self.frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_win, width=e.width))

    def set_tags(self, all_tags, selected):
        for w in self.frame.winfo_children(): w.destroy()
        self.vars = {}
        
        sorted_tags = sorted(list(all_tags), key=str.lower)
        cols = 4
        for i, tag in enumerate(sorted_tags):
            var = tk.BooleanVar(value=(tag in selected))
            self.vars[tag] = var
            btn = ttk.Checkbutton(self.frame, text=tag, variable=var, command=self.callback)
            btn.grid(row=i//cols, column=i%cols, sticky='w', padx=2)
        
        for i in range(cols): self.frame.grid_columnconfigure(i, weight=1)

    def get_selected(self):
        return {t for t, v in self.vars.items() if v.get()}

# --- Main Application ---

class MusicScoreApp:
    def __init__(self, root, start_dir=None, sort_by_title=False):
        self.root = root
        self.root.title(f"Music Score Viewer v{APP_VERSION}")
        self.root.geometry(DEFAULT_WIN_SIZE)
        self._maximize()

        # Data State
        self.scores = []
        self.doc = None
        self.current_score_path = None
        self.current_page = 0
        self.total_pages = 0
        self.tk_image = None # Prevent GC
        
        # View Config
        self.start_dir = start_dir
        self.sort_by_title = sort_by_title
        self.ignore_events = False
        
        # Annotation & Render State
        self.is_two_page = False
        self.page_layout = [] # List of dicts {page, x, y, w, h}
        self.annotations = {} # {page_num: [ {uuid:..., type:..., ...} ] }
        
        self.tool = "nav"
        self.pen_color = "black"
        self.current_stroke = []

        # UI Construction
        style = ttk.Style()
        style.configure("Treeview", rowheight=25)
        
        self.f_select = tk.Frame(root)
        self.f_display = tk.Frame(root, bg=BG_COLOR)
        
        self._setup_selection_ui()
        self._setup_display_ui()
        self._bind_keys()

        self._show_view("select")

        if self.start_dir:
            self.root.after(200, lambda: self._load_dir(self.start_dir))
        else:
            self.root.after(200, self._prompt_dir)

    def _maximize(self):
        try: self.root.state('zoomed')
        except: 
            try: self.root.attributes('-zoomed', True)
            except: pass

    # --- UI Setup Methods ---

    def _setup_selection_ui(self):
        # 1. Top Controls
        top = tk.Frame(self.f_select, padx=10, pady=10)
        top.pack(fill=tk.X)
        
        tk.Label(top, text="Search:").pack(side=tk.LEFT)
        self.ent_search = tk.Entry(top)
        self.ent_search.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.ent_search.bind("<KeyRelease>", self._on_filter)
        
        tk.Button(top, text="Folder", command=self._prompt_dir).pack(side=tk.RIGHT, padx=5)
        tk.Button(top, text="Reset", command=self._reset_filters).pack(side=tk.RIGHT)

        # 2. Filters (Facet)
        mid = tk.Frame(self.f_select, padx=10, pady=5, height=200)
        mid.pack(fill=tk.X)
        mid.pack_propagate(False)
        
        f_comp = tk.LabelFrame(mid, text="Composer")
        f_comp.pack(side=tk.LEFT, fill=tk.Y, padx=(0,10))
        self.cb_comp = ttk.Combobox(f_comp, state="readonly", width=30)
        self.cb_comp.pack(padx=5, pady=5)
        self.cb_comp.bind("<<ComboboxSelected>>", self._on_filter)

        f_tags = tk.LabelFrame(mid, text="Tags")
        f_tags.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tag_grid = CompactTagFrame(f_tags, callback=self._on_filter)
        self.tag_grid.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 3. List
        cols = ("composer", "title", "tags")
        self.tree = ttk.Treeview(self.f_select, columns=cols, show="headings")
        for c in cols: self.tree.heading(c, text=c.capitalize())
        self.tree.column("composer", width=200); self.tree.column("title", width=400)
        
        sb = ttk.Scrollbar(self.f_select, command=self.tree.yview)
        self.tree.configure(yscroll=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.tree.bind("<Double-1>", self._on_open)
        self.tree.bind("<Return>", self._on_open)

    def _setup_display_ui(self):
        # Toolbar
        tb = tk.Frame(self.f_display, bg=TOOLBAR_COLOR, height=50)
        tb.pack(side=tk.TOP, fill=tk.X)
        tb.pack_propagate(False)

        # Helper to make tool buttons
        def mk_btn(txt, cmd, side=tk.LEFT):
            tk.Button(tb, text=txt, width=5, command=lambda: self._set_tool(cmd)).pack(side=side, padx=2, pady=5)

        tk.Label(tb, text="Tools:", bg=TOOLBAR_COLOR).pack(side=tk.LEFT, padx=5)
        mk_btn("Nav", "nav")
        mk_btn("Pen", "pen")
        mk_btn("Text", "text")
        mk_btn("Erase", "eraser")

        # Separator
        tk.Frame(tb, width=1, bg="#999").pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        # Colors
        for c in ["black", "red", "blue", "green", "orange", "purple", "magenta"]:
            tk.Button(tb, bg=c, width=2, command=lambda x=c: self._set_color(x)).pack(side=tk.LEFT, padx=1)

        tk.Frame(tb, width=1, bg="#999").pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        # Width Slider
        tk.Label(tb, text="Size:", bg=TOOLBAR_COLOR).pack(side=tk.LEFT)
        self.sc_size = tk.Scale(tb, from_=1, to=10, orient=tk.HORIZONTAL, length=80, bg=TOOLBAR_COLOR)
        self.sc_size.set(2)
        self.sc_size.pack(side=tk.LEFT, padx=5)

        # Status indicators
        self.lbl_status = tk.Label(tb, text="Mode: Nav", bg=TOOLBAR_COLOR, font=("Arial", 10, "bold"))
        self.lbl_status.pack(side=tk.RIGHT, padx=10)
        self.lbl_col_ind = tk.Label(tb, width=3, bg="black")
        self.lbl_col_ind.pack(side=tk.RIGHT, padx=5)

        # Main Canvas
        self.canvas = tk.Canvas(self.f_display, bg=BG_COLOR, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Events
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.f_display.bind("<Configure>", self._on_resize)

    def _bind_keys(self):
        self.root.bind("<Escape>", self._close_score)
        for k in ["<space>", "n", "<Right>", "<Down>", "<Next>"]: self.root.bind(k, self._next_page)
        for k in ["<BackSpace>", "p", "<Left>", "<Up>", "<Prior>"]: self.root.bind(k, self._prev_page)
        self.root.bind("<Home>", lambda e: self._goto_page(0))
        self.root.bind("<End>", lambda e: self._goto_page(self.total_pages - 1))

    # --- Core Logic ---

    def _prompt_dir(self):
        self.root.lift()
        d = filedialog.askdirectory()
        if d: self._load_dir(d)

    def _load_dir(self, path):
        logging.info(f"Scanning {path}")
        self.scores = []
        try:
            for root, _, files in os.walk(path):
                rel = os.path.relpath(root, path)
                ftags = set(rel.replace("\\", "/").split("/")) if rel != "." else set()
                
                for f in files:
                    if f.lower().endswith(".pdf"):
                        self.scores.append(Score(os.path.join(root, f), f, ftags))
            
            # Sort
            key = (lambda s: (s.title.lower(), s.composer.lower())) if self.sort_by_title \
                  else (lambda s: (s.composer.lower(), s.title.lower()))
            self.scores.sort(key=key)
            self._reset_filters()
        except Exception as e:
            messagebox.showerror("Scan Error", str(e))

    def _reset_filters(self):
        self.ignore_events = True
        self.ent_search.delete(0, tk.END)
        self.cb_comp.set("")
        self._apply_filters(reset_tags=True)
        self.ignore_events = False

    def _on_filter(self, event=None):
        if not self.ignore_events: self._apply_filters()

    def _apply_filters(self, reset_tags=False):
        self.ignore_events = True
        
        txt = self.ent_search.get().lower()
        comp = self.cb_comp.get()
        if comp == "All Composers": comp = ""
        tags = set() if reset_tags else self.tag_grid.get_selected()

        matches = []
        for s in self.scores:
            if txt and txt not in s.title.lower(): continue
            if comp and s.composer != comp: continue
            if not tags.issubset(s.tags): continue
            matches.append(s)

        # Update List
        for x in self.tree.get_children(): self.tree.delete(x)
        for s in matches:
            t_str = ", ".join(sorted(list(s.tags), key=str.lower))
            self.tree.insert("", tk.END, values=(s.composer, s.title, t_str), iid=s.filepath)

        # Update Facets logic (optimized to single loop)
        av_comps = set()
        av_tags = set()
        for s in self.scores:
            # For composers: obey text & tags
            if (not txt or txt in s.title.lower()) and tags.issubset(s.tags):
                av_comps.add(s.composer)
            # For tags: obey text & composer
            if (not txt or txt in s.title.lower()) and (not comp or s.composer == comp):
                if tags.issubset(s.tags): av_tags.update(s.tags)

        # Update UI
        c_list = ["All Composers"] + sorted(list(av_comps))
        self.cb_comp['values'] = c_list
        if comp not in c_list: self.cb_comp.set("All Composers")
        
        self.tag_grid.set_tags(av_tags, tags)
        self.ignore_events = False

    # --- Viewing Logic ---

    def _on_open(self, event):
        sel = self.tree.selection()
        if not sel: return
        self._load_pdf(sel[0])

    def _load_pdf(self, path):
        try:
            self.doc = fitz.open(path)
            self.current_score_path = path
            self.total_pages = self.doc.page_count
            self.current_page = 0
            
            # Load Annotations safely
            base = os.path.splitext(path)[0] + ".json"
            raw = SafeJSON.load(base)
            self.annotations = {}
            
            # Normalize versioning
            if "version" in raw:
                # V2+ structure
                pages = raw.get("pages", {})
                for p, items in pages.items():
                    # Ensure every item has a UUID for V2
                    clean_items = []
                    for it in items:
                        if "uuid" not in it: it["uuid"] = str(uuid.uuid4())
                        clean_items.append(it)
                    self.annotations[int(p)] = clean_items
            else:
                # V1 structure
                for p, items in raw.items():
                    clean_items = []
                    for it in items:
                        it["uuid"] = str(uuid.uuid4())
                        clean_items.append(it)
                    self.annotations[int(p)] = clean_items

            self._show_view("display")
            self._set_tool("nav")
            self.root.update_idletasks() # Ensure geometry is calculated
            self._render_pdf() # Initial Render
        except Exception as e:
            messagebox.showerror("PDF Error", str(e))

    def _show_view(self, mode):
        if mode == "select":
            self.f_display.pack_forget()
            self.f_select.pack(fill=tk.BOTH, expand=True)
            self.doc = None
        else:
            self.f_select.pack_forget()
            self.f_display.pack(fill=tk.BOTH, expand=True)

    def _close_score(self, event=None):
        if self.f_display.winfo_ismapped():
            self._show_view("select")

    def _save_annots(self):
        if not self.current_score_path: return
        base = os.path.splitext(self.current_score_path)[0] + ".json"
        data = {"version": ANNOTATION_VERSION, "pages": self.annotations}
        SafeJSON.save(base, data)

    # --- Graphics Logic (Render & Center) ---

    def _render_pdf(self):
        """Rasterizes PDF pages to background image. Called on resize/nav."""
        if not self.doc: return
        
        # 1. Calc Dimensions
        win_w = self.canvas.winfo_width()
        win_h = self.canvas.winfo_height()
        if win_w < 10: win_w, win_h = 1200, 850 # Fallback

        p1 = self.doc.load_page(self.current_page)
        r1 = p1.rect # w, h
        
        # Determine "Fit Height" Zoom
        zoom_fit_h = win_h / r1.height
        sep = 4
        
        # Check Side-by-Side feasibility
        width_two_pages = (r1.width * zoom_fit_h * 2) + sep
        self.is_two_page = (width_two_pages <= win_w and self.current_page + 1 < self.total_pages)
        
        self.page_layout = [] # Reset layout map

        # 2. Render Pixmaps (CPU Heavy)
        if self.is_two_page:
            # We assume fit-height is best for 2 pages if they fit
            zoom = zoom_fit_h
            
            mat = fitz.Matrix(zoom, zoom)
            pix1 = p1.get_pixmap(matrix=mat)
            
            p2 = self.doc.load_page(self.current_page + 1)
            pix2 = p2.get_pixmap(matrix=mat)
            
            # Composite using PIL
            total_w = pix1.width + pix2.width + sep
            max_h = max(pix1.height, pix2.height)
            
            # Calculate Centering Offsets
            x_off = (win_w - total_w) // 2
            y_off = (win_h - max_h) // 2
            
            img = Image.new("RGB", (total_w, max_h), (0,0,0))
            im1 = Image.frombytes("RGB", [pix1.width, pix1.height], pix1.samples)
            im2 = Image.frombytes("RGB", [pix2.width, pix2.height], pix2.samples)
            img.paste(im1, (0,0))
            img.paste(im2, (pix1.width + sep, 0))
            
            self.page_layout = [
                {"p": self.current_page, "x": x_off, "y": y_off, "w": pix1.width, "h": pix1.height},
                {"p": self.current_page+1, "x": x_off + pix1.width + sep, "y": y_off, "w": pix2.width, "h": pix2.height}
            ]
            
            # Create centered image
            self.tk_image = ImageTk.PhotoImage(img)
            self.canvas.delete("all") 
            self.canvas.create_image(x_off, y_off, image=self.tk_image, anchor="nw", tags="bg")

        else:
            # Single Page: Calculate "Best Fit" (Min of Width or Height)
            zoom_w = win_w / r1.width
            zoom_h = win_h / r1.height
            zoom = min(zoom_w, zoom_h)
            
            mat = fitz.Matrix(zoom, zoom)
            pix1 = p1.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix1.width, pix1.height], pix1.samples)
            
            # Calculate Centering Offsets
            x_off = (win_w - pix1.width) // 2
            y_off = (win_h - pix1.height) // 2
            
            self.page_layout = [
                {"p": self.current_page, "x": x_off, "y": y_off, "w": pix1.width, "h": pix1.height}
            ]
            
            self.tk_image = ImageTk.PhotoImage(img)
            self.canvas.delete("all") 
            self.canvas.create_image(x_off, y_off, image=self.tk_image, anchor="nw", tags="bg")

        # 4. Draw Annotations (Vector)
        self._draw_vectors()

    def _draw_vectors(self):
        """Draws annotations on top of existing PDF background."""
        # Clear old vectors only, keep background 'bg'
        self.canvas.delete("annot") 
        
        for layout in self.page_layout:
            pg = layout['p']
            if pg in self.annotations:
                for annot in self.annotations[pg]:
                    self._draw_single_annot(annot, layout)

    def _draw_single_annot(self, annot, layout):
        ox, oy, w, h = layout['x'], layout['y'], layout['w'], layout['h']
        tag = ("annot", f"uuid_{annot['uuid']}")
        
        if annot['type'] == 'ink':
            pts = []
            for nx, ny in annot['points']:
                pts.append(ox + nx*w)
                pts.append(oy + ny*h)
            if len(pts) >= 4:
                wd = annot.get('width', 2)
                self.canvas.create_line(pts, fill=annot['color'], width=wd, 
                                        capstyle=tk.ROUND, joinstyle=tk.ROUND, 
                                        smooth=True, splinesteps=36, tags=tag)
        
        elif annot['type'] == 'text':
            x = ox + annot['x'] * w
            y = oy + annot['y'] * h
            txt = annot['text']
            fam = annot.get('font', 'Arial')
            sz = 12 + (annot.get('size', 2) * 4)
            
            if txt.strip() in MUSICAL_SYMBOLS_SET:
                sz = int(sz * 6.0) # Massive scaling for music symbols
            
            # Font fallback
            try: f = (fam, sz)
            except: f = ("Arial", sz)
            
            self.canvas.create_text(x, y, text=txt, fill=annot['color'], font=f, anchor="w", tags=tag)

    # --- Interaction Logic ---

    def _set_tool(self, t):
        self.tool = t
        self.lbl_status.config(text=f"Mode: {t.capitalize()}")
        cursors = {"nav":"", "pen":"pencil", "text":"xterm", "eraser":"crosshair"}
        self.canvas.config(cursor=cursors.get(t, ""))

    def _set_color(self, c):
        self.pen_color = c
        self.lbl_col_ind.config(bg=c)
        if self.tool in ["nav", "eraser"]: self._set_tool("pen")

    def _get_layout_at(self, x, y):
        for l in self.page_layout:
            if l['x'] <= x <= l['x']+l['w'] and l['y'] <= y <= l['y']+l['h']:
                return l
        return None

    def _on_click(self, event):
        if self.tool == "nav":
            h = self.canvas.winfo_height()
            w = self.canvas.winfo_width()
            if event.y < h * 0.15: self._close_score()
            elif event.x < w / 2: self._prev_page()
            else: self._next_page()
            return

        l = self._get_layout_at(event.x, event.y)
        if not l: return

        if self.tool == "pen":
            self.current_stroke = [(event.x, event.y)]
        
        elif self.tool == "text":
            # Check if editing existing text
            item = self.canvas.find_closest(event.x, event.y, halo=5)
            tags = self.canvas.gettags(item)
            target_uuid = None
            for t in tags:
                if t.startswith("uuid_"): target_uuid = t[5:]
            
            # Find annot data
            edit_data = None
            if target_uuid and l['p'] in self.annotations:
                for a in self.annotations[l['p']]:
                    if a['uuid'] == target_uuid and a['type'] == 'text':
                        edit_data = a
                        break
            
            if edit_data:
                # Edit Mode
                d = TextEntryDialog(self.root, "Edit Text", edit_data['color'], edit_data['text'], edit_data.get('font',''))
                if d.result:
                    edit_data.update({
                        "text": d.result['text'], "font": d.result['font'], 
                        "size": self.sc_size.get(), "color": self.pen_color
                    })
                    self._save_annots()
                    self._draw_vectors()
            else:
                # New Mode
                d = TextEntryDialog(self.root, initial_color=self.pen_color)
                if d.result:
                    nx = (event.x - l['x']) / l['w']
                    ny = (event.y - l['y']) / l['h']
                    annot = {
                        "uuid": str(uuid.uuid4()), "type": "text",
                        "x": nx, "y": ny, "text": d.result['text'],
                        "font": d.result['font'], "color": self.pen_color,
                        "size": self.sc_size.get()
                    }
                    self._add_annot(l['p'], annot)

        elif self.tool == "eraser":
            item = self.canvas.find_closest(event.x, event.y, halo=5)
            tags = self.canvas.gettags(item)
            for t in tags:
                if t.startswith("uuid_"):
                    uid = t[5:]
                    # Remove from data
                    if l['p'] in self.annotations:
                        # Filter out the deleted item
                        self.annotations[l['p']] = [a for a in self.annotations[l['p']] if a['uuid'] != uid]
                        self._save_annots()
                        self.canvas.delete(item) # Immediate visual feedback
                    break

    def _on_drag(self, event):
        if self.tool == "pen" and self.current_stroke:
            x, y = event.x, event.y
            self.current_stroke.append((x, y))
            # Draw temporary line (no save/render trigger)
            pts = self.current_stroke[-2:]
            w = self.sc_size.get()
            self.canvas.create_line(pts[0][0], pts[0][1], pts[1][0], pts[1][1], 
                                    fill=self.pen_color, width=w, capstyle=tk.ROUND, joinstyle=tk.ROUND)

    def _on_release(self, event):
        if self.tool == "pen" and len(self.current_stroke) > 1:
            l = self._get_layout_at(self.current_stroke[0][0], self.current_stroke[0][1])
            if l:
                # Normalize points
                norm = []
                for sx, sy in self.current_stroke:
                    nx = (sx - l['x']) / l['w']
                    ny = (sy - l['y']) / l['h']
                    norm.append([nx, ny])
                
                annot = {
                    "uuid": str(uuid.uuid4()), "type": "ink",
                    "points": norm, "color": self.pen_color, "width": self.sc_size.get()
                }
                self._add_annot(l['p'], annot)
            self.current_stroke = []

    def _add_annot(self, pg, annot):
        if pg not in self.annotations: self.annotations[pg] = []
        self.annotations[pg].append(annot)
        self._save_annots()
        self._draw_vectors() # Redraw just vectors to smooth out the new stroke

    def _on_resize(self, event):
        # Debounce or simple check
        if self.doc: self._render_pdf()

    def _goto_page(self, p):
        if self.doc and 0 <= p < self.total_pages:
            self.current_page = p
            self._render_pdf()

    def _next_page(self, e=None):
        if not self.doc or self.tool == "text": return
        step = 2 if self.is_two_page else 1
        self._goto_page(self.current_page + step if self.current_page + step < self.total_pages else self.current_page)

    def _prev_page(self, e=None):
        if not self.doc or self.current_page == 0 or self.tool == "text": return
        step = 2 if self.is_two_page else 1
        self._goto_page(max(0, self.current_page - step))

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = MusicScoreApp(root, start_dir=args.dir, sort_by_title=args.title_first)
        root.mainloop()
    except Exception as e:
        logging.critical(f"App Crash: {e}")