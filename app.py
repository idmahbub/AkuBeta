import os
import random
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import platform
import sys
import shutil
import textwrap
import arabic_reshaper
import time
from PIL import Image, ImageTk
import pygame
from bidi.algorithm import get_display
from mutagen.mp3 import MP3
import re
import unicodedata
# ================= CROSS PLATFORM FFMPEG =================
def resource_path(relative_path):
    """
    Support PyInstaller + dev mode
    """
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
#latin and arab shaping
def fix_mixed_text(text):
    reshaped = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped)
    return bidi_text
def wrap_text_by_chars(text, max_chars=28):
    lines = []
    for line in text.split("\n"):
        lines.extend(textwrap.wrap(line, max_chars))
    return "\n".join(lines)
def clean_mp3_name(filename: str, raw_filter: str) -> str:
    # ambil nama file tanpa extension
    name = os.path.splitext(os.path.basename(filename))[0]
    # normalisasi awal
    name = name.replace("_", " ")
    name = unicodedata.normalize("NFKC", name)
    # samakan semua pipe
    name = name.replace("｜", "|").replace("│", "|")
    # remove slash
    name = name.replace("⧸", "/")
    # parsing filter user
    filters = [f.strip() for f in raw_filter.split(",") if f.strip()]
    # hapus filter user
    for f in filters:
        name = re.sub(
            re.escape(f),
            "",
            name,
            flags=re.IGNORECASE
        )
    # auto cut setelah |
    name = re.sub(r"\|.*$", "", name)
    # rapikan spasi
    name = re.sub(r"\s+", " ", name).strip()
    return name
def ffmpeg_path(p):
    return p.replace("\\", "/").replace(":", "\\:")
def find_binary(name):
    exe = name + ".exe" if os.name == "nt" else name
    bundled = resource_path(os.path.join("bin", exe))
    if os.path.isfile(bundled) and os.access(bundled, os.X_OK):
        return bundled
    system = shutil.which(name)
    if system:
        return system
    raise FileNotFoundError(f"{name} not found")
FFMPEG = find_binary("ffmpeg")
FFPROBE = find_binary("ffprobe")
def format_time(seconds):
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"
def get_mp3_duration(file_path):
    try:
        audio = MP3(file_path)
        return int(audio.info.length)
    except:
        return 0
import random

def get_safe_box_color_hex():
    """
    Generate cinematic dark box color + kontras text.
    Return:
        box_color  -> "RRGGBB"
        text_color -> "RRGGBB"
    """

    # 🎨 Cinematic base palettes (dark movie tones)
    palettes = [
        (18, 32, 47),   # deep navy
        (22, 40, 35),   # dark teal
        (35, 22, 40),   # dark purple
        (30, 30, 30),   # charcoal
        (40, 28, 20),   # warm brown cinematic
        (15, 45, 60),   # blue teal film
        (25, 35, 28),   # forest dark
    ]

    base_r, base_g, base_b = random.choice(palettes)

    # 🎛 Tambah sedikit noise biar gak flat
    r = min(255, max(0, base_r + random.randint(-15, 15)))
    g = min(255, max(0, base_g + random.randint(-15, 15)))
    b = min(255, max(0, base_b + random.randint(-15, 15)))

    box_color = f"{r:02x}{g:02x}{b:02x}"

    # ===== WCAG Luminance =====
    def luminance(r, g, b):
        def channel(c):
            c = c / 255.0
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)

    lum = luminance(r, g, b)

    # ✨ Cinematic text choice
    if lum < 0.35:
        text_color = "f5f5f5@0.8"   # soft white (lebih elegan dari pure white)
    else:
        text_color = "111111@0.8"

    return box_color, text_color

def get_random_bright_color():
    return "FFEB3B"
    #if random.random() < 0.7:
    #    return "F9FF00"
    #return random.choice(["00E5FF", "FF4081", "76FF03"])
class PlaylistApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Playlist Generator PRO")
        screen_h = self.root.winfo_screenheight()
        screen_w = self.root.winfo_screenwidth()
        # kasih margin 120px biar aman dari dock & menu bar
        max_height = screen_h - 120
        max_width = min(1100, screen_w - 100)
        self.start_time = 0
        self.pause_time = 0
        self.root.geometry(f"{max_width}x{max_height}")
        self.root.minsize(900, 600)
        self.box_color = None
        self.text_color = None
        pygame.mixer.init()
        self.current_audio = None
        self.is_playing = False
        self.playlist_files = []
        self.song_durations = []
        self.queue_files = []
        self.output_folder = "output"
        self.bg_name = "background"
        self.is_rendering = False
        self.process = None
        self.setup_dark_theme()
        self.filter_var = tk.StringVar()
        self.filtered_playlist_files = []
        self.search_var = tk.StringVar()
        self.build_ui()
    def setup_dark_theme(self):
        style = ttk.Style()
        # pakai theme bawaan yang paling fleksibel
        if "clam" in style.theme_names():
            style.theme_use("clam")
        bg = "#1e1e1e"
        panel = "#2b2b2b"
        text = "#eaeaea"
        accent = "#3a86ff"
        self.root.configure(bg=bg)
        style.configure(".", 
            background=bg,
            foreground=text,
            fieldbackground=panel
        )
        style.configure("TCombobox", background=panel)
        style.map("TCombobox",
            fieldbackground=[
                ("active", "#3c3c3c"),   # hover background
                ("selected", bg)
            ],
            foreground=[
                ("active", "white"),    # hover text putih
                ("selected", "white")   # saat terpilih text putih
            ]
        )
        style.configure("TFrame", background=bg)
        style.configure("Panel.TFrame", background=panel)
        style.configure("TButton",
            background=panel,
            foreground=text,
            padding=6
        )
        style.map("TButton",
            background=[("active", accent)]
        )
        style.configure("TEntry",
            fieldbackground=panel,
            foreground=text
        )
        style.configure("TLabel", background=bg, foreground=text)
        style.configure("StatusIdle.TLabel", foreground="#4caf50")
        style.configure("StatusRender.TLabel", foreground="#ff5252")
        style.configure("TProgressbar",
            troughcolor=panel,
            background=accent
        )
        # ===== NOTEBOOK (TAB) STYLE FIX =====
        style.configure("TNotebook",
            background=bg,
            borderwidth=0
        )
        style.configure("TNotebook.Tab",
            background=panel,
            foreground=text,      # <<< ini kunci: warna tulisan tab
            padding=[14, 8],
            font=("Segoe UI", 10, "bold")
        )
        style.map("TNotebook.Tab",
            background=[
                ("selected", accent),
                ("active", "#3c3c3c")
            ],
            foreground=[
                ("selected", "white"),
                ("active", "white")
            ]
        )
        # ===== RADIOBUTTON STYLE =====
        style.configure("TRadiobutton",
            background=bg,
            foreground=text,
            indicatorcolor=accent,
            padding=5
        )
        style.map("TRadiobutton",
            background=[
                ("active", "#3c3c3c"),   # hover background
                ("selected", bg)
            ],
            foreground=[
                ("active", "white"),    # hover text putih
                ("selected", "white")   # saat terpilih text putih
            ],
            indicatorcolor=[
                ("selected", accent),   # bulatan isi warna accent
                ("active", accent)
            ]
        )
    #thumbnail
    def generate_thumbnail(self, title_text, sub_text):
        if self.thumb_title_entry.get() == "" and self.thumb_sub_entry.get() == "":
            return
        bg = self.bg_entry.get()
        if not bg or not os.path.exists(bg):
            messagebox.showerror("Error", "Background image belum dipilih")
            return
        if not os.path.exists(self.get_random_font()):
            messagebox.showerror("Error", "Font tidak ditemukan")
            return
        visual_dir = os.path.dirname(os.path.abspath(bg))
        base_dir = os.path.dirname(visual_dir)
        self.output_folder = os.path.join(base_dir, "output")
        os.makedirs(self.output_folder, exist_ok=True)
        self.bg_name = os.path.splitext(os.path.basename(bg))[0]
        output_path = os.path.join(self.output_folder, f"{self.bg_name}_thumbnail.png")
        # ===== PRE WRAP =====
        title_wrapped = wrap_text_by_chars(title_text.upper(), 12)
        sub_wrapped   = wrap_text_by_chars(sub_text, 32)
        title_file = os.path.join(self.output_folder, "_thumb_title.txt")
        sub_file   = os.path.join(self.output_folder, "_thumb_sub.txt")
        with open(title_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(title_wrapped)
        with open(sub_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(sub_wrapped)
        font_big = ffmpeg_path(self.get_random_font())
        font_small = ffmpeg_path(self.get_random_font())
        title_file = ffmpeg_path(title_file)
        sub_file   = ffmpeg_path(sub_file)
        # ==== thumbnail box params ====
        W, H = 1280, 720
        box_width = int(W * 0.5)
        position = self.box_position_var.get()  # <-- ambil dari radio UI
        max_alpha = 200
        fade_width = max(1, int(box_width * 0.45))
        solid_width = box_width - fade_width
        x_box = W - box_width if position == "right" else 0
        self.box_color,self.text_color = get_safe_box_color_hex()
        box_color,text_color = self.box_color,self.text_color
        shadow_color = "000000@0.5" if text_color == "f5f5f5" else "ffffff@0.5"
        margin = 80
        if position == "left":
            alpha_expr = f"if(lte(X,{solid_width}),{max_alpha},{max_alpha}*(1-(X-{solid_width})/{fade_width}))"
            text_align = "left"
            x_text = x_box + margin
        else:
            alpha_expr = f"if(gte(X,{fade_width}),{max_alpha},{max_alpha}*(X/{fade_width}))"
            text_align = "right"
            x_text = f"{x_box}+{box_width}-{margin}-text_w"
        #adaptif font size berdasarkan jumlah line
        from PIL import ImageFont
        font_title = ImageFont.truetype(self.get_random_font(), 76)
        title_lines = title_wrapped.split("\n")
        line_spacing = 14
        ascent, descent = font_title.getmetrics()
        line_height = ascent + descent  # ini yang benar
        title_text_height = (line_height * len(title_lines)) + (line_spacing * (len(title_lines) - 1))
        title_y = 140
        spacing_between = 30  # sedikit lebih aman
        subtitle_y = title_y + title_text_height + spacing_between
        filter_complex = f"""
        [0:v]scale={W}:{H}[bg];
        color=size={box_width}x{H}:color={box_color},format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='{alpha_expr}'[box];
        [bg][box]overlay={x_box}:0[tmp];
        [tmp]drawtext=
            fontfile='{font_big}':
            textfile='{title_file}':
            fontsize=76:
            fontcolor=0xffd700@0.8:
            text_align={text_align}:
            line_spacing=14:
            x={x_text}:
            y={title_y}[tmp2];
        [tmp2]drawtext=
            fontfile='{font_small}':
            textfile='{sub_file}':
            fontsize=40:
            fontcolor=0xe0e0e0:
            text_align={text_align}:
            line_spacing=10:
            x={x_text}:
            y={subtitle_y}
        """
        filter_complex = "\n".join(line.strip() for line in filter_complex.splitlines() if line.strip())
        is_video = bg.lower().endswith((".mp4", ".mov", ".mkv", ".webm"))
        input_cmd = []
        if is_video:
            # ambil frame di detik 3 (lebih aman daripada frame pertama)
            input_cmd = ["-ss", "3", "-i", bg]
        else:
            input_cmd = ["-i", bg]
        subprocess.run([
            FFMPEG,
            "-y",
            *input_cmd,
            "-filter_complex", filter_complex,
            "-frames:v", "1",
            output_path
        ], check=True)
        self.show_image_preview(output_path)
        self.log(f"Thumbnail OK → {output_path}")
    def validate_and_generate(self,mode="visual"):
        if not self.queue_files:
            messagebox.showwarning(
                "Playlist Kosong",
                "Silakan pilih folder playlist terlebih dahulu."
            )
            return
        bg = self.bg_entry.get()
        if not bg or not os.path.exists(bg):
            messagebox.showwarning(
                "Background Missing",
                "Pilih background image terlebih dahulu."
            )
            return
        if mode == "visual":
            self.run_thread(self.generate_visual)
        if mode == "final":
            self.run_thread(self.generate_final)
    def update_visual_button_state(self):
        if self.queue_files:
            self.btn_visual.config(state="normal")
            self.btn_final.config(state="normal")
        else:
            self.btn_visual.config(state="disabled")
            self.btn_final.config(state="disabled")
    def _append_log(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")
        self.log_text.config(
            font=("Consolas", 10),
            bg="#0f1117",
            fg="#dcdcdc",
            insertbackground="white"
        )
    def generate_youtube_timestamps(self):
        timestamps = []
        current_time = 0
        raw_filter = self.filter_var.get().strip()
        for file in self.queue_files:
            duration = get_mp3_duration(file)
            minutes = int(current_time // 60)
            seconds = int(current_time % 60)
            name = clean_mp3_name(file, raw_filter)
            timestamps.append(f"{minutes:02d}:{seconds:02d} - {name}")
            current_time += duration
        description_text = "\n".join(timestamps)
        prompt = self.generate_prompt_yt()
        description_text = (
            "📌 Timestamps:\n\n"
            + description_text
            + "\n\n🎵 Enjoy the music! Don't forget to like, comment, and subscribe for more playlists!\n\n"
            + prompt
            + "\n\nTimestamps:\n"
            + description_text
            + "\n\n=============\n\n"
        )
        # Simpan ke file
        desc_path = os.path.join(
            self.output_folder,
            f"{self.bg_name}_youtube_description.txt"
        )
        with open(desc_path, "w", encoding="utf-8") as f:
            f.write(description_text)
        return description_text
    def generate_prompt_yt(self):
        lines = ["\n=== Yt Prompt ==="]
        import textwrap
        lines.append(textwrap.dedent("""
Generate an engaging YouTube title and description based on the song list below.
Rules:
- If there is only 1 song, treat it as a SINGLE release.
- If there are 2 or more songs, treat it as a PLAYLIST.
- Adapt the tone based on the song titles (religious, pop, chill, emotional, etc.).
- Create:
  1. SEO optimized YouTube Title
  2. Full YouTube Description (emotional, engaging, include short background context based on titles)
  3. Hashtags (max 15)
  4. Tags separated by commas
- Do not fabricate artist names if not provided.
- Use natural Indonesian language.
- D not include emojis.
- Add call to action (like, comment, subscribe).
Song List:
        """))
        return "\n".join(lines)
    def log(self, text):
        self.root.after(0, lambda: (
            self.log_text.insert("end", text + "\n"),
            self.log_text.see("end")
        ))
    #filter preview list
    def filter_playlist(self, *_):
        keyword = self.search_var.get().lower().strip()
        if not keyword:
            self.filtered_playlist_files = self.playlist_files.copy()
        else:
            self.filtered_playlist_files = [
                f for f in self.playlist_files
                if keyword in os.path.basename(f).lower()
            ]
        self.update_playlist_box(filtered=True)
    def clear_search(self):
        self.search_var.set("")
    #mainui
    def build_ui(self):
        # ===== NOTEBOOK (TAB) =====
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True)
        # ===== TAB GENERATE =====
        self.tab_generate = ttk.Frame(notebook)
        notebook.add(self.tab_generate, text="Generate")
        # ===== TAB DOWNLOAD =====
        self.tab_download = ttk.Frame(notebook)
        notebook.add(self.tab_download, text="Download")
        # ===== TAB RENAME =====
        self.tab_rename = ttk.Frame(notebook)
        notebook.add(self.tab_rename, text="Bulk Rename")
        # build masing-masing tab
        self.build_generate_tab(self.tab_generate)
        self.build_download_tab(self.tab_download)
        self.build_rename_tab(self.tab_rename)
    # ================= UI =================
    def show_text_menu(self, event):
        try:
            self.text_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.text_menu.grab_release()
    def build_generate_tab(self, parent):
        main = ttk.Frame(parent)
        main.pack(fill="both", expand=True, padx=10, pady=10)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=0)
        main.rowconfigure(0, weight=1)
        # ================= LEFT PANEL =================
        left = ttk.Frame(main)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.columnconfigure(1, weight=1)
        # ---- Background ----
        ttk.Label(left, text="Background Image").grid(row=0, column=0, sticky="w")
        self.bg_var = tk.StringVar()
        self.bg_var.trace_add("write", self.on_background_changed)
        self.bg_entry = ttk.Entry(left, textvariable=self.bg_var)
        self.bg_entry.grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(
            left,
            text="Browse",
            command=self.browse_bg
        ).grid(row=0, column=2)
        # ---- Overlay ----
        ttk.Label(left, text="Overlay Video").grid(row=1, column=0, sticky="w", pady=(8,0))
        self.overlay_entry = ttk.Entry(left)
        self.overlay_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=(8,0))
        ttk.Button(left, text="Browse", command=self.browse_overlay)\
            .grid(row=1, column=2, pady=(8,0))
        # ---- Thumbnail Title ----
        ttk.Label(left, text="Thumbnail Title")\
            .grid(row=2, column=0, sticky="w", pady=(10,0))
        title_frame = ttk.Frame(left)
        title_frame.grid(row=2, column=1, columnspan=2, sticky="ew", pady=(10,0))
        title_frame.columnconfigure(0, weight=1)
        self.thumb_title_entry = ttk.Entry(title_frame)
        self.thumb_title_entry.grid(row=0, column=0, sticky="ew", padx=(5,5))
        self.add_to_final_var = tk.StringVar(value="")
        self.add_to_final_combo = ttk.Combobox(
            title_frame,
            textvariable=self.add_to_final_var,
            values=["", "left video", "center video", "right video"],
            state="readonly",
            width=10
        )
        self.add_to_final_combo.grid(row=0, column=1, sticky="e")
        # ---- Thumbnail Sub Text ----
        ttk.Label(left, text="Thumbnail Sub Text")\
            .grid(row=3, column=0, sticky="w", pady=(5,0))
        self.thumb_sub_entry = ttk.Entry(left)
        self.thumb_sub_entry.grid(row=3, column=1, columnspan=2, sticky="ew", padx=5, pady=(5,0))
        # ---- Playlist + Shuffle ----
        playlist_row = ttk.Frame(left)
        playlist_row.grid(row=5, column=0, columnspan=3, sticky="ew", pady=10)
        playlist_row.columnconfigure(0, weight=1)
        playlist_row.columnconfigure(1, weight=1)
        playlist_row.columnconfigure(2, weight=0)
        playlist_row.columnconfigure(3, weight=0)
        ttk.Button(
            playlist_row,
            text="MP3 Folder",
            command=self.select_playlist_folder
        ).grid(row=0, column=0, sticky="ew")
        ttk.Button(
            playlist_row,
            text="MP3 Files",
            command=self.select_multiple_mp3
        ).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(
            playlist_row,
            text="Clear",
            command=self.clear_playlist
        ).grid(row=0, column=3, padx=5)
       # ===== PLAYLIST PREVIEW & QUEUE =====
        list_frame = ttk.Frame(left)
        list_frame.grid(row=8, column=0, columnspan=3, sticky="nsew")
        left.rowconfigure(8, weight=1)
        # Atur grid agar proporsional
        list_frame.columnconfigure(0, weight=5)  # Preview lebih lebar
        list_frame.columnconfigure(1, weight=0)  # Tombol kecil
        list_frame.columnconfigure(2, weight=5)  # Queue sama besar
        list_frame.rowconfigure(0, weight=1)
        # --- LISTBOX 1 (Preview + Search) ---
        preview_container = ttk.Frame(list_frame)
        preview_container.grid(row=0, column=0, sticky="nsew", padx=(0,5))
        # ⬇️ penting: sekarang ada 2 row
        preview_container.rowconfigure(0, weight=0)  # search
        preview_container.rowconfigure(1, weight=1)  # listbox
        preview_container.columnconfigure(0, weight=1)
        # 🔎 SEARCH BOX
        search_frame = ttk.Frame(preview_container)
        search_frame.grid(row=0, column=0, sticky="ew", pady=(0,5))
        search_frame.columnconfigure(0, weight=1)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.grid(row=0, column=0, sticky="ew", padx=(0,5), ipady=2)
        clear_btn = tk.Label(
            search_frame,
            text="✖",
            bg="#2b2b2b",
            fg="#eaeaea",
            padx=6,
            pady=2,
            cursor="hand2"
        )
        clear_btn.grid(row=0, column=1, pady=1)
        clear_btn.bind("<Button-1>", lambda e: self.clear_search())
        # hover effect
        clear_btn.bind("<Enter>", lambda e: clear_btn.config(bg="#ff5252"))
        clear_btn.bind("<Leave>", lambda e: clear_btn.config(bg="#2b2b2b"))
        self.search_var.trace_add("write", self.filter_playlist)
        # 🎵 LISTBOX
        self.preview_box = tk.Listbox(
            preview_container,
            bg="#2b2b2b",
            fg="#eaeaea",
            selectbackground="#3a86ff",
            selectmode=tk.EXTENDED,
            borderwidth=0,
            highlightthickness=0
        )
        self.preview_box.grid(row=1, column=0, sticky="nsew")
        preview_scroll = ttk.Scrollbar(
            preview_container,
            command=self.preview_box.yview
        )
        preview_scroll.grid(row=1, column=1, sticky="ns")
        self.preview_box.config(yscrollcommand=preview_scroll.set)
        # --- MIDDLE BUTTONS ---
        btn_frame = ttk.Frame(list_frame)
        btn_frame.grid(row=0, column=1, padx=5)
        ttk.Button(btn_frame, text="▶", width=3, command=self.add_to_queue).pack(pady=5)
        ttk.Button(btn_frame, text="◀", width=3, command=self.remove_from_queue).pack(pady=5)
        # --- LISTBOX 2 (Queue Generate) ---
        queue_container = ttk.Frame(list_frame)
        queue_container.grid(row=0, column=2, sticky="nsew", padx=(5,0))
        queue_container.grid_rowconfigure(0, weight=1)
        queue_container.grid_columnconfigure(0, weight=1)
        # Listbox
        self.queue_box = tk.Listbox(
            queue_container,
            bg="#1f2a38",
            fg="#ffffff",
            selectbackground="#ff5252",
            selectmode=tk.EXTENDED,
            borderwidth=0,
            highlightthickness=0
        )
        self.queue_box.grid(row=0, column=0, sticky="nsew")
        # Scrollbar
        queue_scroll = ttk.Scrollbar(queue_container, command=self.queue_box.yview)
        queue_scroll.grid(row=0, column=1, sticky="ns")
        self.queue_box.config(yscrollcommand=queue_scroll.set)
        if platform.system() == "Darwin":  # MacOS
            self.preview_box.bind("<Button-2>", self.show_playlist_menu)
        else:
            self.preview_box.bind("<Button-3>", self.show_playlist_menu)
        self.playlist_menu = tk.Menu(self.root, tearoff=0)
        self.playlist_menu.add_command(
            label="Delete Selected",
            command=self.delete_selected_song
        )
        # ===== AUDIO CONTROL (PLAY + SEEK SATU BARIS) =====
        audio_top = ttk.Frame(left)
        audio_top.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(5, 5))
        # Layout kolom:
        # 0 Play
        # 1 Shuffle
        # 2 Seek (stretch)
        # 3 Time
        audio_top.columnconfigure(2, weight=1)  # Seek bar flexible
        self.play_btn = ttk.Button(
            audio_top,
            text="▶",
            width=3,
            command=self.toggle_play
        )
        self.play_btn.grid(row=0, column=0, padx=3)
        self.shuffle_btn = ttk.Button(
            audio_top,
            text="🔀",
            width=3,
            command=self.shuffle_playlist
        )
        self.shuffle_btn.grid(row=0, column=1, padx=3)
        # ===== SEEK BAR DI SINI =====
        self.seek_scale = ttk.Scale(
            audio_top,
            from_=0,
            to=100,
            orient="horizontal",
            command=self.seek_audio
        )
        self.seek_scale.grid(row=0, column=2, sticky="ew", padx=10)
        self.time_label = ttk.Label(audio_top, text="00:00 / 00:00")
        self.time_label.grid(row=0, column=3, sticky="e", padx=5)
        # ================= CONTROLS =================
        controls = ttk.Frame(left)
        controls.grid(row=9, column=0, columnspan=3, sticky="ew", pady=10)
        # ================= CONTROLS =================
        controls = ttk.Frame(left)
        controls.grid(row=9, column=0, columnspan=3, sticky="ew", pady=10)
        # Layout kolom:
        # 0 Label
        # 1 Left radio
        # 2 Right radio
        # 3 Spacer (flex)
        # 4 Visual
        # 5 Final
        # 6 Cancel
        controls.columnconfigure(0, weight=0)
        controls.columnconfigure(1, weight=0)
        controls.columnconfigure(2, weight=0)
        controls.columnconfigure(3, weight=1)  # spacer penting!
        controls.columnconfigure(4, weight=0)
        controls.columnconfigure(5, weight=0)
        controls.columnconfigure(6, weight=0)
        # ===== KIRI : Box Position =====
        ttk.Label(controls, text="").grid(row=0, column=0, sticky="w")
        self.box_position_var = tk.StringVar(value="left")
        ttk.Radiobutton(
            controls,
            text="Left",
            value="left",
            variable=self.box_position_var
        ).grid(row=0, column=1, padx=5)
        ttk.Radiobutton(
            controls,
            text="Right",
            value="right",
            variable=self.box_position_var
        ).grid(row=0, column=2, padx=5)
        # ===== TENGAH : Filter String =====
        filter_frame = ttk.Frame(controls)
        filter_frame.grid(row=0, column=3, sticky="e", padx=(0, 10))
        ttk.Label(filter_frame, text="Remove Text:").pack(side="left", padx=(0, 5))
        self.filter_entry = ttk.Entry(
            filter_frame,
            textvariable=self.filter_var,
            width=22
        )
        self.filter_entry.pack(side="left")
        # ===== KANAN : Buttons =====
        self.btn_visual = ttk.Button(
            controls,
            text="Generate Visual",
            command=lambda: self.validate_and_generate("visual"),
            state="disabled"
        )
        self.btn_visual.grid(row=0, column=4, padx=5)
        self.btn_final = ttk.Button(
            controls,
            text="Generate Final",
            command=lambda: self.validate_and_generate("final"),
            state="disabled"
        )
        self.btn_final.grid(row=0, column=5, padx=5)
        self.btn_cancel = ttk.Button(
            controls,
            text="Cancel",
            command=self.cancel_render,
            state="disabled"
        )
        self.btn_cancel.grid(row=0, column=6, padx=5)
        # ================= Row 2 : Progress + Status =================
        self.progress = ttk.Progressbar(
            controls,
            mode="determinate"
        )
        self.progress.grid(
            row=1,
            column=0,
            columnspan=6,   # penting! span semua kolom
            sticky="ew",
            pady=(8, 0)
        )
        self.status_label = ttk.Label(
            controls,
            text="Idle",
            style="StatusIdle.TLabel"
        )
        self.status_label.grid(row=1, column=6, padx=5)
        # ================= RIGHT PANEL =================
        right = ttk.Frame(main, style="Panel.TFrame", width=450)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_propagate(False)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=2)  # preview
        right.rowconfigure(3, weight=1)  # log
        ttk.Label(right, text="Preview").grid(row=0, column=0, sticky="w", padx=5)
        preview_frame = tk.Frame(right)
        preview_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        preview_frame.rowconfigure(0, weight=1)
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.grid_propagate(False)
        self.preview_label = tk.Label(
            preview_frame
        )
        self.preview_label.grid(row=0, column=0, sticky="nsew")
        ttk.Label(right, text="FFmpeg Log").grid(row=2, column=0, sticky="w", padx=5)
        log_frame = ttk.Frame(right)
        log_frame.grid(row=3, column=0, sticky="nsew", padx=5, pady=5)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, bg="#2b2b2b", fg="#eaeaea")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)
        # ================= CONTEXT MENU (TEXT) =================
        self.text_menu = tk.Menu(self.root, tearoff=0)
        self.text_menu.add_command(
            label="Cut",
            command=lambda: self.root.focus_get().event_generate("<<Cut>>")
        )
        self.text_menu.add_command(
            label="Copy",
            command=lambda: self.root.focus_get().event_generate("<<Copy>>")
        )
        self.text_menu.add_command(
            label="Paste",
            command=lambda: self.root.focus_get().event_generate("<<Paste>>")
        )
        def bind_text_context(widget):
            widget.bind("<Button-3>", self.show_text_menu)  # Windows
            widget.bind("<Button-2>", self.show_text_menu)  # Mac
        # bind ke semua widget input
        bind_text_context(self.thumb_title_entry)
        bind_text_context(self.thumb_sub_entry)
        bind_text_context(self.log_text)
        bind_text_context(self.bg_entry)
        bind_text_context(self.overlay_entry)
    def play_video_preview(self, video_path):
        width = 400
        height = 220
        cmd = [
            FFMPEG,
            "-i", video_path,
            "-f", "image2pipe",
            "-pix_fmt", "rgb24",
            "-vcodec", "rawvideo",
            "-vf", f"fps=24,scale={width}:{height}",
            "-"
        ]
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        threading.Thread(
            target=self.read_frames,
            args=(width, height),
            daemon=True
        ).start()
    def read_frames(self, width, height):
        frame_size = width * height * 3
        while True:
            raw = self.process.stdout.read(frame_size)
            if len(raw) != frame_size:
                break
            img = Image.frombytes("RGB", (width, height), raw)
            imgtk = ImageTk.PhotoImage(img)
            self.preview_label.imgtk = imgtk
            self.preview_label.configure(image=imgtk)
    def stop_preview(self):
        if hasattr(self, "process"):
            self.process.terminate()
    def show_image_preview(self, file_path, max_width=400):
        if not os.path.exists(file_path):
            return
        is_video = file_path.lower().endswith((".mp4", ".mov", ".mkv", ".webm"))
        preview_path = file_path
        # 🔥 Jika video → ambil 1 frame
        if is_video:
            return #biar gak berat
            """
            preview_path = os.path.join("temp_preview.jpg")
            cmd = [
                "ffmpeg",
                "-y",
                "-i", file_path,
                "-frames:v", "1",
                "-q:v", "2",
                preview_path
            ]
            self.run_ffmpeg(cmd,total_duration=1)
            """
        # 🔥 Buka gambar hasilnya
        img = Image.open(preview_path)
        ratio = max_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        self.preview_label.config(image=photo)
        self.preview_label.image = photo 
    def build_download_tab(self, parent):
        from downloadmanager import DownloadManager
        self.download_manager = DownloadManager(parent)
    def build_rename_tab(self, parent):
        from rename import RenameTab
        self.rename_tab = RenameTab(self)
        self.rename_tab.build(self.tab_rename)
    # ================= STATE =================
    def set_rendering_state(self, rendering):
        self.is_rendering = rendering
        state = "disabled" if rendering else "normal"
        style = "StatusRender.TLabel" if rendering else "StatusIdle.TLabel"
        self.root.after(0, lambda: self.btn_visual.config(state=state))
        self.root.after(0, lambda: self.btn_final.config(state=state))
        self.root.after(0, lambda: self.btn_cancel.config(
            state="normal" if rendering else "disabled"
        ))
        self.root.after(0, lambda: self.status_label.config(
            text="Rendering..." if rendering else "Idle",
            style=style
        ))
    # ================= THREAD =================
    def run_thread(self, func):
        if self.is_rendering:
            return
        def wrapper():
            try:
                self.is_rendering = True
                self.set_rendering_state(True)
                func()
            except Exception as e:
                messagebox.showerror("Error", str(e))
            finally:
                self.is_rendering = False
                self.set_rendering_state(False)
        threading.Thread(target=wrapper, daemon=True).start()
    # ================= GPU DETECT =================
    def detect_gpu_encoder(self):
        try:
            result = subprocess.run(
                [FFMPEG, "-encoders"],
                capture_output=True,
                text=True
            ).stdout
            if "h264_nvenc" in result:
                return "h264_nvenc"
            elif "h264_videotoolbox" in result:
                return "h264_videotoolbox"
            elif "h264_qsv" in result:
                return "h264_qsv"
            else:
                return "libx264"
        except:
            return "libx264"
    def get_random_font(self):
        font_dir = resource_path("fonts")
        if not os.path.exists(font_dir):
            raise Exception("Folder 'fonts' tidak ditemukan")
        fonts = [
            os.path.join(font_dir, f)
            for f in os.listdir(font_dir)
            if f.lower().endswith(".ttf")
        ]
        if not fonts:
            raise Exception("Tidak ada file .ttf di folder fonts")
        return random.choice(fonts)
    def on_background_changed(self, *_):
        bg = self.bg_entry.get()
        if not bg or not os.path.exists(bg):
            return
        self.show_image_preview(bg)
        visual_dir = os.path.dirname(os.path.abspath(bg))
        base_dir = os.path.dirname(visual_dir)
        output_root = os.path.join(base_dir, "output")
        self.output_folder = output_root
        os.makedirs(self.output_folder, exist_ok=True)
        # nama file background tanpa ekstensi
        self.bg_name = os.path.splitext(os.path.basename(bg))[0]
        self.log(f"Output folder: {output_root}")
    def generate_visual(self):
        self.log("Generating visual...")
        bg = self.bg_entry.get()
        if not bg or not os.path.exists(bg):
            messagebox.showerror("Error", "Background image belum dipilih")
            return
        screen_width = 1920
        screen_height = 1080
        # somefolder (parent dari folder visual)
        visual_dir = os.path.dirname(os.path.abspath(bg))       # somefolder/visual
        base_dir = os.path.dirname(visual_dir)                  # somefolder
        #generate thumbnail
        self.generate_thumbnail(
            self.thumb_title_entry.get(),
            self.thumb_sub_entry.get()
        )
        # somefolder/output/visualname
        output_root = os.path.join(base_dir, "output")
        self.output_folder = output_root
        os.makedirs(self.output_folder, exist_ok=True)
        overlay = self.overlay_entry.get()
        if not bg:
            messagebox.showerror("Error", "Missing background/overlay")
            return
        is_bg_video = bg.lower().endswith((".mp4", ".mov", ".mkv", ".webm"))
        has_overlay = overlay and os.path.exists(overlay)
        input_cmd = []
        if is_bg_video:
            input_cmd += ["-i", bg]
        else:
            input_cmd += ["-loop", "1", "-i", bg]
        if has_overlay:
            input_cmd += ["-i", overlay]
        encoder = self.detect_gpu_encoder()
        font_path = ffmpeg_path(self.get_random_font())
        # ================= CREATE PLAYLIST TEXT =================
        playlist_text = []
        raw_filter = self.filter_var.get().strip()
        for i, fpath in enumerate(self.queue_files, start=1):
            name = os.path.basename(fpath).replace(".mp3", "").replace("_", " ")
            name = clean_mp3_name(name, raw_filter)
            mixed_text = f"{i:02d}. {name}"
            fixed_text = fix_mixed_text(mixed_text)
            playlist_text.append(fixed_text)
        playlist_text_str = "\n".join(playlist_text)
        playlist_text_str = fix_mixed_text(playlist_text_str)
        # buat file sementara supaya multiline aman
        text_file_os = os.path.join(self.output_folder, f"{self.bg_name}_playlist.txt")
        with open(text_file_os, "w", encoding="utf-8", newline="\n") as f:
            f.write(playlist_text_str)
        text_file = ffmpeg_path(text_file_os)
        # ================= CALCULATE BOX SIZE =================
        num_lines = max(1, len(playlist_text))
        available_height = int(screen_height * 0.70)  # lebih aman
        # hitung font size ideal
        fontsize = int((available_height / num_lines) * 0.75)
        # clamp khusus playlist
        fontsize = max(22, min(fontsize, 42))
        # jarak antar baris (lebih rapat)
        line_spacing = int(fontsize * 0.18)
        box_width = int(screen_width * 0.50)
        position = self.box_position_var.get()  # 'left' / 'right'
        if num_lines <= 5:
            fontsize = min(fontsize + 6, 42)
        if position == "left":
            x_box = 0
        else:
            x_box = screen_width - box_width
        title_position = self.add_to_final_var.get()
        if title_position == "left video":
            title_x = "80"
            title_align = "left"
        elif title_position == "right video":
            title_x = f"{screen_width}-tw-80"
            title_align = "right"
        elif title_position == "center video":
            title_x = "(w-text_w)/2"
            title_align = "center"
        title_y = "60"
        margin = 80
        if position == "left":
            x_drawtext = x_box + margin
            text_align = "left"
        else:
            x_drawtext = f"{x_box + box_width}-tw-{margin}"
            text_align = "right"
        y_drawtext = 50  # mulai agak bawah atas
        fade_width = max(1, int(box_width * 0.45))
        solid_width = box_width - fade_width
        max_alpha = 200  # 0–255 (atur opacity di sini)
        if position == "left":
            alpha_expr = (
                f"if(lte(X,{solid_width}),"
                f"{max_alpha},"
                f"{max_alpha}*(1-(X-{solid_width})/{fade_width}))"
            )
        else:
            alpha_expr = (
                f"if(gte(X,{fade_width}),"
                f"{max_alpha},"
                f"{max_alpha}*(X/{fade_width}))"
            )
        if not self.box_color or not self.text_color:
            self.box_color, self.text_color = get_safe_box_color_hex()
        box_color,text_color = self.box_color,self.text_color
        shadow_color = "000000" if text_color == "ffffff" else "ffffff"
        #add title text thumbnail ke video kalau checkboxnya dicek
        title_filter = ""
        random_color = get_random_bright_color()
        if title_position != "":
            thumb_title = self.thumb_title_entry.get().upper()
            thumb_title = thumb_title.replace(":", "\\:").replace("'", "\\'")
            title_filter = (
                f",drawtext="
                f"fontfile='{font_path}':"
                f"text='{thumb_title}':"
                f"text_align={title_align}:"
                f"fontcolor=0x{random_color}:"
                f"fontsize=160:"
                f"x={title_x}:"
                f"y=80:"
                f"borderw=10:"
                f"bordercolor=0x{box_color}:"
                f"shadowcolor=0x{box_color}:"
                f"shadowx=3:"
                f"shadowy=3"
            )
        if has_overlay:
            filter_complex = (
                f"[0:v]scale={screen_width}:{screen_height}[bg];"
                f"color=color=0x{box_color}:size={box_width}x{screen_height},format=rgba,"
                f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='{alpha_expr}'[grad];"
                f"[bg][grad]overlay=x={x_box}:y=0[bg_box];"
                f"[bg_box]drawtext="
                f"fontfile='{font_path}':"
                f"textfile='{text_file}':"
                f"text_align={text_align}:"
                f"fontcolor=0x{text_color}:"
                f"fontsize={fontsize}:"
                f"line_spacing={line_spacing}:"
                f"x={x_drawtext}:"
                #f"y={y_drawtext}:"
                f"y=(h-text_h)/2:"
                f"shadowcolor=0x{shadow_color}:"
                f"shadowx=1:"
                f"shadowy=1{title_filter}[bg_text];"
                f"[1:v]scale={screen_width}:{screen_height},format=yuva420p,"
                f"colorchannelmixer=aa=0.3[ov];"
                f"[bg_text][ov]overlay=0:0"
            )
        else:
            filter_complex = (
                f"[0:v]scale={screen_width}:{screen_height}[bg];"
                f"color=color=0x{box_color}:size={box_width}x{screen_height},format=rgba,"
                f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='{alpha_expr}'[grad];"
                f"[bg][grad]overlay=x={x_box}:y=0[bg_box];"
                f"[bg_box]drawtext="
                f"fontfile='{font_path}':"
                f"textfile='{text_file}':"
                f"text_align={text_align}:"
                f"fontcolor=0x{text_color}:"
                f"fontsize={fontsize}:"
                f"line_spacing={line_spacing}:"
                f"x={x_drawtext}:"
                #f"y={y_drawtext}:"
                f"y=(h-text_h)/2:"
                f"shadowcolor=0x{shadow_color}:"
                f"shadowx=1:"
                f"shadowy=1{title_filter}"
            )
        output_path = os.path.join(self.output_folder, f"{self.bg_name}_visual_playlist.mp4")
        cmd = [
            FFMPEG,
            "-y",
            *input_cmd,
            "-filter_complex", filter_complex,
            "-shortest",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-b:a", "128k", 
            "-pix_fmt", "yuv420p",
            "-preset", "slow",           # optimasi kompresi
            "-crf", "28",
            output_path
        ]
        duration = 5 if (not has_overlay and not is_bg_video) else None
        if duration:
            idx = cmd.index("-shortest")
            cmd[idx:idx] = ["-t", str(duration)]
        self.run_ffmpeg(cmd, total_duration=60)  # <-- total_duration bisa disesuaikan
        self.play_video_preview(output_path)
    # ================= FINAL =================
    def generate_final(self):
        self.log("Generating final video...")
        encoder = self.detect_gpu_encoder()
        if not self.queue_files:
            messagebox.showerror("Error", "Playlist kosong")
            return
        visual_path = os.path.join(self.output_folder, f"{self.bg_name}_visual_playlist.mp4")
        if not os.path.exists(visual_path):
            messagebox.showerror("Error", "Generate visual dulu")
            return
        # ================= CREATE PLAYLIST FILE =================
        desc = self.generate_youtube_timestamps()
        print("\n=== YOUTUBE DESCRIPTION ===\n")
        print(desc)
        list_path = os.path.join(self.output_folder, f"{self.bg_name}_playlist.txt")
        with open(list_path, "w", encoding="utf-8", newline="\n") as f:
            for file in self.queue_files:
                abs_path = os.path.abspath(file).replace("\\", "/")
                safe_path = abs_path.replace("'", "'\\''")
                f.write(f"file '{safe_path}'\n")
        # ================= COMBINE MP3 =================
        combined_path = os.path.join(self.output_folder, f"{self.bg_name}_combined.mp3")
        combine_cmd = [
            FFMPEG,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_path,
            "-c", "copy",
            combined_path
        ]
        self.run_ffmpeg(combine_cmd, total_duration=1)
        # ================= GET AUDIO DURATION =================
        audio_duration = get_mp3_duration(combined_path)
        # ================= FINAL VIDEO =================
        output_path = os.path.join(
            self.output_folder,
            f"{self.bg_name}_final_youtube.mp4"
        )
        cmd = [
            FFMPEG,
            "-y",
            "-stream_loop", "-1",
            "-i", visual_path,
            "-i", combined_path,
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-r", "30",
            "-t", str(audio_duration),
            "-movflags", "+faststart",
            output_path
        ]
        self.run_ffmpeg(cmd, total_duration=audio_duration)
        self.log("Play list generated")
        self.queue_files.clear()
        self.root.after(0, self.update_queue_box)
        os.remove(list_path)
        os.remove(combined_path)
        os.remove(visual_path)
        self.rename_bg_file()
    # ================= RUN FFMPEG =================
    def run_ffmpeg(self, cmd, total_duration):
        if not isinstance(cmd, list):
            raise ValueError("run_ffmpeg expects cmd as list")
        # ===== inject progress flags =====
        cmd = cmd.copy()
        cmd.insert(1, "-progress")
        cmd.insert(2, "pipe:1")
        cmd.insert(3, "-nostats")
        self.log(">>> " + " ".join(cmd) + "\n")
        popen_kwargs = dict(
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        # 🔒 HIDE CONSOLE WINDOW (WINDOWS ONLY)
        if platform.system() == "Windows":
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        self.is_rendering = True
        self.process = subprocess.Popen(cmd, **popen_kwargs)
        duration = max(total_duration, 1)
        try:
            for line in self.process.stdout:
                if not self.is_rendering:
                    break
                line = line.strip()
                self.log(line)
                if line.startswith("out_time_ms="):
                    value = line.split("=", 1)[1].strip()
                    if not value.isdigit():
                        continue
                    out_time_ms = int(value)
                    current_sec = out_time_ms / 1_000_000
                    percent = min((current_sec / duration) * 100, 100)
                    self.root.after(
                        0,
                        lambda p=percent: self.progress.config(value=p)
                    )
            self.process.wait()
            if self.process.returncode != 0 and self.is_rendering:
                raise RuntimeError("FFmpeg failed")
        except Exception as e:
            self.log(f"FFmpeg error: {e}")
        finally:
            self.process = None
            self.is_rendering = False
            self.root.after(0, lambda: self.progress.config(value=100))
    # ================= CANCEL =================
    def cancel_render(self):
        if not self.process:
            return
        self.is_rendering = False
        try:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
        except Exception as e:
            self.log(f"Cancel error: {e}")
        self.process = None
        self.root.after(0, lambda: self.progress.config(value=0))
        self.log("Rendering dihentikan.")
    # ================= Rename Bg agar tidak di pakai lagi =================
    def rename_bg_file(self):
        old_path = self.bg_entry.get()

        if not old_path or not os.path.exists(old_path):
            return

        folder = os.path.dirname(old_path)
        filename = os.path.basename(old_path)

        new_filename = "used_" + filename
        new_path = os.path.join(folder, new_filename)

        # kalau sudah ada file dengan nama itu, jangan overwrite
        if os.path.exists(new_path):
            print("File sudah ada:", new_filename)
            return

        os.rename(old_path, new_path)

        # update entry supaya path ikut berubah
        self.bg_entry.delete(0, "end")
        self.bg_entry.insert(0, new_path)
        self.log(f"Background file renamed to: {new_filename}")
    # ================= PLAYLIST =================
    def clear_playlist(self):
        self.playlist_files.clear()
        self.update_playlist_box()
        self.update_visual_button_state()
    def select_playlist_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        mp3_files = [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if f.lower().endswith(".mp3")
        ]
        # append, bukan replace
        self.playlist_files.extend(mp3_files)
        # optional: remove duplicate
        self.playlist_files = list(dict.fromkeys(self.playlist_files))
        self.update_playlist_box()
        self.update_visual_button_state()
    def select_multiple_mp3(self):
        files = filedialog.askopenfilenames(
            title="Select MP3 Files",
            filetypes=[("MP3 Files", "*.mp3")]
        )
        if not files:
            return
        # append
        self.playlist_files.extend(files)
        # remove duplicate
        self.playlist_files = list(dict.fromkeys(self.playlist_files))
        self.update_playlist_box()
        self.update_visual_button_state()
    def update_playlist_box(self, filtered=False):
        self.preview_box.delete(0, tk.END)
        if not filtered:
            self.filtered_playlist_files = self.playlist_files.copy()
        for f in self.filtered_playlist_files:
            name = os.path.basename(f)
            duration = get_mp3_duration(f)
            formatted = format_time(duration)
            display_text = f"{name}  ({formatted})"
            self.preview_box.insert(tk.END, display_text)
        self.update_visual_button_state()
    def update_queue_box(self):
        self.queue_box.delete(0, tk.END)
        total_seconds = 0
        for i, file_path in enumerate(self.queue_files):
            name = os.path.basename(file_path)
            duration = get_mp3_duration(file_path)
            total_seconds += duration
            formatted = format_time(duration)
            display_text = f"{i+1:02d}. {name}  ({formatted})"
            self.queue_box.insert(tk.END, display_text)
        # 🔥 Kirim ke log saja
        total_formatted = format_time(total_seconds)
        self.log(f"Total playlist duration: {total_formatted}")
    def shuffle_playlist(self):
        random.shuffle(self.queue_files)
        self.update_queue_box()
    def show_playlist_menu(self, event):
        try:
            self.preview_box.selection_clear(0, tk.END)
            self.preview_box.selection_set(self.preview_box.nearest(event.y))
            self.playlist_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.playlist_menu.grab_release()
    def delete_selected_song(self):
        selected = self.preview_box.curselection()
        if not selected:
            return
        index = selected[0]
        file_path = self.filtered_playlist_files[index]
        if file_path in self.playlist_files:
            self.playlist_files.remove(file_path)
        self.filter_playlist()
        self.update_visual_button_state()
    #preview mp3
    def toggle_play(self):
        selected = self.preview_box.curselection() or self.queue_box.curselection()
        if not selected:
            return
        selected_preview = self.preview_box.curselection()
        selected_queue = self.queue_box.curselection()
        if selected_preview:
            index = selected_preview[0]
            file_path = self.playlist_files[index]
            curbox = self.preview_box
        elif selected_queue:
            index = selected_queue[0]
            file_path = self.queue_files[index]
            curbox = self.queue_box
        if self.current_audio != file_path:
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            curbox.itemconfig(index, bg="#1DB954", fg="white")
            self.current_audio = file_path
            self.is_playing = True
            self.play_btn.config(text="⏸")
            sound = pygame.mixer.Sound(file_path)
            self.total_duration = sound.get_length()
            self.seek_scale.config(to=self.total_duration)
            self.start_time = time.time()
            self.update_seek_bar()
        else:
            if self.is_playing:
                pygame.mixer.music.pause()
                self.pause_time = time.time()
                self.play_btn.config(text="▶")
            else:
                pygame.mixer.music.unpause()
                self.start_time += time.time() - self.pause_time
                self.play_btn.config(text="⏸")
            self.is_playing = not self.is_playing
    def update_seek_bar(self):
        if not self.is_playing:
            return
        current = time.time() - self.start_time
        if current >= self.total_duration:
            self.play_btn.config(text="▶")
            self.is_playing = False
            return
        self.seek_scale.set(current)
        self.time_label.config(
            text=f"{format_time(current)} / {format_time(self.total_duration)}"
        )
        self.root.after(500, self.update_seek_bar)
    def seek_audio(self, value):
        if not self.current_audio:
            return
        position = float(value)
        pygame.mixer.music.play(start=position)
        self.start_time = time.time() - position
        self.is_playing = True
        self.play_btn.config(text="⏸")
    def add_to_queue(self):
        selected = self.preview_box.curselection()
        if not selected:
            return
        for index in reversed(selected):
            # ambil dari filtered list
            file_path = self.filtered_playlist_files[index]
            # hapus dari playlist utama
            if file_path in self.playlist_files:
                self.playlist_files.remove(file_path)
            # masukkan ke queue
            self.queue_files.append(file_path)
        # refresh filter ulang
        self.filter_playlist()
        self.update_queue_box()
        self.update_visual_button_state()
    def remove_from_queue(self):
        selected = self.queue_box.curselection()
        if not selected:
            return
        for index in reversed(selected):
            file_path = self.queue_files.pop(index)     # hapus dari queue
            self.playlist_files.append(file_path)       # kembalikan ke preview
        self.update_playlist_box()
        self.update_queue_box()
        self.update_visual_button_state()
    # ================= BROWSE =================
    def browse_bg(self):
        path = filedialog.askopenfilename()
        if path:
            self.bg_entry.delete(0, tk.END)
            self.bg_entry.insert(0, path)
    def browse_overlay(self):
        path = filedialog.askopenfilename()
        if path:
            self.overlay_entry.delete(0, tk.END)
            self.overlay_entry.insert(0, path)
# ================= MAIN =================
if __name__ == "__main__":
    root = tk.Tk()
    app = PlaylistApp(root)
    root.mainloop()