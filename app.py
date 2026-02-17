import os
import random
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import shlex
import re
import platform
import sys
import shutil
import textwrap
import random
import arabic_reshaper
from PIL import Image, ImageTk
from bidi.algorithm import get_display
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



def get_safe_box_color_hex():
    """
    Generate box color + text color yang kontras & harmonis.
    Return:
        box_color  -> "RRGGBB"
        text_color -> "RRGGBB"
    """

    # 1️⃣ Generate dark-modern box color
    r = random.randint(25, 90)
    g = random.randint(25, 90)
    b = random.randint(25, 90)

    box_color = f"{r:02x}{g:02x}{b:02x}"

    # 2️⃣ Hitung luminance (WCAG)
    def luminance(r, g, b):
        def channel(c):
            c = c / 255.0
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)

    lum = luminance(r, g, b)

    # 3️⃣ Tentukan warna text berdasarkan kontras
    if lum < 0.35:
        # Box cukup gelap → pakai putih clean
        text_color = "ffffff"
    else:
        # Box agak terang → pakai warna gelap elegan
        text_color = "111111"

    return box_color, text_color


class PlaylistApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Playlist Generator FFmpeg PRO")
        
        screen_h = self.root.winfo_screenheight()
        screen_w = self.root.winfo_screenwidth()

        # kasih margin 120px biar aman dari dock & menu bar
        max_height = screen_h - 120
        max_width = min(1100, screen_w - 100)

        self.root.geometry(f"{max_width}x{max_height}")
        self.root.minsize(900, 600)
        
        self.playlist_files = []
        self.song_durations = []
        self.output_folder = "output"
        self.bg_name = "background"
        self.is_rendering = False
        self.process = None
        self.setup_dark_theme()
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
        # Periksa file teks
        if not os.path.exists(title_file):
            messagebox.showerror("Error", f"File teks judul '{title_file}' tidak ditemukan.")
            return
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
        box_color,text_color = get_safe_box_color_hex()
        shadow_color = "000000" if text_color == "ffffff" else "ffffff"
        margin = 80
        if position == "left":
            alpha_expr = f"if(lte(X,{solid_width}),{max_alpha},{max_alpha}*(1-(X-{solid_width})/{fade_width}))"
            text_align = "left"
            x_text = x_box + margin
        else:
            alpha_expr = f"if(gte(X,{fade_width}),{max_alpha},{max_alpha}*(X/{fade_width}))"
            text_align = "right"
            x_text = f"{x_box}+{box_width}-{margin}-text_w"
        title_y = 300
        spacing_between = 40  # jarak antara title dan subtitle
        filter_complex = f"""
        [0:v]scale={W}:{H}[bg];
        color=size={box_width}x{H}:color={box_color},format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='{alpha_expr}'[box];
        [bg][box]overlay={x_box}:0[tmp];

        [tmp]drawtext=
            fontfile='{font_big}':
            textfile='{title_file}':
            fontsize=76:
            fontcolor={text_color}:
            text_align={text_align}:
            line_spacing=14:
            x={x_text}:
            y=140:
            shadowcolor={shadow_color}:
            shadowx=4:
            shadowy=4[tmp2];

        [tmp2]drawtext=
            fontfile='{font_small}':
            textfile='{sub_file}':
            fontsize=40:
            fontcolor=0xe0e0e0:
            text_align={text_align}:
            line_spacing=10:
            x={x_text}:
            y={title_y}+text_h+{spacing_between}:
            shadowcolor={shadow_color}:
            shadowx=3:
            shadowy=3
        """
        filter_complex = "\n".join(line.strip() for line in filter_complex.splitlines() if line.strip())

        subprocess.run([
            FFMPEG, "-y", "-i", bg,
            "-filter_complex", filter_complex,
            "-frames:v", "1",
            output_path
        ], check=True)
        self.show_image_preview(output_path)
        self.log(f"Thumbnail OK → {output_path}")

    def validate_and_generate(self,mode="visual"):
        if not self.playlist_files:
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

        overlay = self.overlay_entry.get()
        if not overlay or not os.path.exists(overlay):
            messagebox.showwarning(
                "Overlay Missing",
                "Pilih overlay video terlebih dahulu."
            )
            return
        if mode == "visual":
            self.run_thread(self.generate_visual)
        if mode == "final":
            self.run_thread(self.generate_final)
    def update_visual_button_state(self):
        if self.playlist_files:
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
        for i, file in enumerate(self.playlist_files):
            duration = self.get_media_duration(file)
            minutes = int(current_time // 60)
            seconds = int(current_time % 60)
            name = os.path.splitext(os.path.basename(file))[0]
            name = name.replace("_", " ")
            timestamps.append(f"{minutes:02d}:{seconds:02d} - {name}")
            current_time += duration
        description_text = "\n".join(timestamps)
        # Simpan ke file
        desc_path = os.path.join(self.output_folder, f"{self.bg_name}_youtube_description.txt")
        with open(desc_path, "w", encoding="utf-8") as f:
            f.write(description_text)
        return description_text
    def log(self, text):
        self.root.after(0, lambda: (
            self.log_text.insert("end", text + "\n"),
            self.log_text.see("end")
        ))
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

            # build masing-masing tab
            self.build_generate_tab(self.tab_generate)
            self.build_download_tab(self.tab_download)

    # ================= UI =================
    def show_text_menu(self, event):
        try:
            self.text_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.text_menu.grab_release()
    def build_generate_tab(self, parent):

        main = ttk.Frame(parent)
        main.pack(fill="both", expand=True, padx=10, pady=10)

        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)
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

        self.thumb_title_entry = ttk.Entry(left)
        self.thumb_title_entry.grid(row=2, column=1, columnspan=2, sticky="ew", padx=5, pady=(10,0))

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
            text="Select Folder",
            command=self.select_playlist_folder
        ).grid(row=0, column=0, sticky="ew")

        ttk.Button(
            playlist_row,
            text="Select MP3 Files",
            command=self.select_multiple_mp3
        ).grid(row=0, column=1, sticky="ew", padx=5)

        ttk.Button(
            playlist_row,
            text="Shuffle",
            command=self.shuffle_playlist
        ).grid(row=0, column=2, padx=5)

        ttk.Button(
            playlist_row,
            text="Clear",
            command=self.clear_playlist
        ).grid(row=0, column=3, padx=5)


        # ---- Playlist Listbox ----
        self.playlist_box = tk.Listbox(
            left,
            height=8,
            bg="#2b2b2b",
            fg="#eaeaea",
            selectbackground="#3a86ff"
        )

        if platform.system() == "Darwin":  # MacOS
            self.playlist_box.bind("<Button-2>", self.show_playlist_menu)
        else:
            self.playlist_box.bind("<Button-3>", self.show_playlist_menu)
        self.playlist_box.grid(row=6, column=0, columnspan=3, sticky="nsew")
        left.rowconfigure(6, weight=1)
        self.playlist_menu = tk.Menu(self.root, tearoff=0)
        self.playlist_menu.add_command(
            label="Delete Selected",
            command=self.delete_selected_song
        )

        # ================= CONTROLS =================
        controls = ttk.Frame(left)
        controls.grid(row=7, column=0, columnspan=3, sticky="ew", pady=10)
        controls.columnconfigure(3, weight=1)

        # ---- Box Position + Radio ----
        ttk.Label(controls, text="Box:").grid(row=0, column=0, sticky="w")

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
        ).grid(row=0, column=2)
        
        # ---- Generate Buttons (Sejajar) ----
        self.btn_visual = ttk.Button(
            controls,
            text="Generate Visual",
            command=lambda: self.validate_and_generate("visual"),
            state="disabled"  # default disable dulu
        )
        self.btn_visual.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)

        self.btn_final = ttk.Button(
            controls,
            text="Generate Final",
            command=lambda: self.validate_and_generate("final"),
            state="disabled"  # default disable dulu
        )
        self.btn_final.grid(row=1, column=2, columnspan=2, sticky="ew", pady=5, padx=(5,0))

        # ---- Cancel + Status ----
        self.btn_cancel = ttk.Button(
            controls,
            text="Cancel",
            command=self.cancel_render,
            state="disabled"
        )
        self.btn_cancel.grid(row=2, column=0, sticky="ew", pady=5)

        self.status_label = ttk.Label(
            controls,
            text="Idle",
            style="StatusIdle.TLabel"
        )
        self.status_label.grid(row=2, column=1, columnspan=3, sticky="w", padx=10)

        # ---- Progress ----
        self.progress = ttk.Progressbar(
            controls,
            mode="determinate"
        )
        self.progress.grid(row=3, column=0, columnspan=4, sticky="ew", pady=5)
        # ================= RIGHT PANEL =================
        right = ttk.Frame(main, style="Panel.TFrame")
        right.grid(row=0, column=1, sticky="nsew")

        right.columnconfigure(0, weight=1)
        right.rowconfigure(3, weight=1)

        ttk.Label(right, text="Preview").grid(row=0, column=0, sticky="w", padx=5)

        preview_frame = tk.Frame(right, height=220, bg="#1e1e1e")
        preview_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        preview_frame.grid_propagate(False)

        self.preview_label = tk.Label(preview_frame, bg="#1e1e1e")
        self.preview_label.pack(expand=True)

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
    
    def show_image_preview(self, image_path, max_width=400):
        img = Image.open(image_path)

        ratio = max_width / img.width
        new_height = int(img.height * ratio)

        img = img.resize((max_width, new_height))
        
        photo = ImageTk.PhotoImage(img)

        self.preview_label.config(image=photo)
        self.preview_label.image = photo  # prevent garbage collect
    def build_download_tab(self, parent):
        from DownloadManager import DownloadManager
        self.download_manager = DownloadManager(parent)




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
    def get_media_duration(self, path):
        cmd = [
            FFPROBE,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(result.stderr)
        return float(result.stdout.strip())
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
        if not bg or not overlay:
            messagebox.showerror("Error", "Missing background/overlay")
            return
        encoder = self.detect_gpu_encoder()
        font_path = ffmpeg_path(self.get_random_font())
        # ================= CREATE PLAYLIST TEXT =================
        playlist_text = []
        for i, fpath in enumerate(self.playlist_files, start=1):
            name = os.path.basename(fpath).replace(".mp3", "").replace("_", " ")
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
        fontsize = 42
        line_spacing = max(6, int(fontsize * 0.12))
        screen_width = 1920
        screen_height = 1080
        box_width = int(screen_width * 0.50)  # 65% dari layar
        position = self.box_position_var.get()  # 'left' atau 'right'
        if position == "left":
            x_box = 0
        else:
            x_box = screen_width - box_width
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
        box_color,text_color = get_safe_box_color_hex()
        shadow_color = "000000" if text_color == "ffffff" else "ffffff"
            
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
            f"y={y_drawtext}:"
            f"shadowcolor=0x{shadow_color}:"
            f"shadowx=3:"
            f"shadowy=3[bg_text];"
            f"[1:v]scale={screen_width}:{screen_height},format=yuva420p,"
            f"colorchannelmixer=aa=0.3[ov];"
            f"[bg_text][ov]overlay=0:0"
        )
        output_path = os.path.join(self.output_folder, f"{self.bg_name}_visual_playlist.mp4")
        cmd = [
            FFMPEG,
            "-y",
            "-loop", "1",
            "-i", bg,
            "-i", overlay,
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
        self.run_ffmpeg(cmd, total_duration=60)  # <-- total_duration bisa disesuaikan
        self.play_video_preview(output_path)
    
    # ================= FINAL =================
    def generate_final(self):
        self.log("Generating final video...")
        encoder = self.detect_gpu_encoder()

        if not self.playlist_files:
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
            for file in self.playlist_files:
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
        audio_duration = self.get_media_duration(combined_path)
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
        messagebox.showinfo("Cancelled", "Rendering dihentikan.")

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


    def update_playlist_box(self):
        self.playlist_box.delete(0, tk.END)
        for f in self.playlist_files:
            self.playlist_box.insert(tk.END, os.path.basename(f))
        self.update_visual_button_state()
    

    def shuffle_playlist(self):
        random.shuffle(self.playlist_files)
        self.update_playlist_box()
    def show_playlist_menu(self, event):
        try:
            self.playlist_box.selection_clear(0, tk.END)
            self.playlist_box.selection_set(self.playlist_box.nearest(event.y))
            self.playlist_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.playlist_menu.grab_release()
    def delete_selected_song(self):
        selected = self.playlist_box.curselection()
        if not selected:
            return

        index = selected[0]

        # hapus dari data
        del self.playlist_files[index]

        # refresh
        self.update_playlist_box()
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