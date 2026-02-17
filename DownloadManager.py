import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import subprocess, threading, platform
import sys
import shutil
import signal

# ================= RESOURCE PATH =================

def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = os.path.abspath(".")
    return os.path.join(base, relative_path)


def find_binary(name):
    exe = name + ".exe" if os.name == "nt" else name

    bundled = resource_path(os.path.join("bin", exe))

    if os.path.isfile(bundled) and os.access(bundled, os.X_OK):
        return bundled

    system = shutil.which(name)
    if system:
        return system

    raise FileNotFoundError(f"{name} not found")
YTDLP = find_binary("yt-dlp")
FFMPEG = find_binary("ffmpeg")
FFPROBE = find_binary("ffprobe")

class DownloadManager:
    def __init__(self, parent):
        self.parent = parent
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.download_thread = None
        self.is_downloading = False
        self.process = None
        self.download_process = None
        self.stop_event = threading.Event()

        self.build_ui()
       
    def browse_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.folder_entry.delete(0, tk.END)
            self.folder_entry.insert(0, path)
    def open_folder(self, path):
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.call(["open", path])
        else:
            subprocess.call(["xdg-open", path])


    # ================= UI =================
    def build_ui(self):
        self.frame.columnconfigure(0, weight=3)
        self.frame.columnconfigure(1, weight=2)
        self.frame.rowconfigure(0, weight=1)

        # ===== LEFT PANEL =====
        left = ttk.Frame(self.frame)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # ===== OUTPUT FOLDER =====
        ttk.Label(left, text="Output Folder").pack(anchor="w")
        row = ttk.Frame(left)
        row.pack(fill="x", pady=4)

        self.folder_entry = ttk.Entry(row)
        self.folder_entry.pack(side="left", fill="x", expand=True)

        ttk.Button(
            row,
            text="Browse",
            command=self.browse_folder
        ).pack(side="left", padx=5)

        # list.txt selector
        ttk.Label(left, text="YouTube URL List (list.txt)").pack(anchor="w", pady=(10, 0))
        row = ttk.Frame(left)
        row.pack(fill="x", pady=4)

        self.list_entry = ttk.Entry(row)
        self.list_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse", command=self.browse_list).pack(side="left", padx=5)

        # format select
        ttk.Label(left, text="Download Format").pack(anchor="w", pady=(10, 0))
        self.format_var = tk.StringVar(value="mp3")
        ttk.Radiobutton(left, text="MP3 (audio)", variable=self.format_var, value="mp3").pack(anchor="w")
        ttk.Radiobutton(left, text="MP4 (video)", variable=self.format_var, value="mp4").pack(anchor="w")
        # ===== BATCH SIZE =====
        ttk.Label(left, text="Batch Size (files per folder)").pack(anchor="w", pady=(10, 0))

        self.batch_var = tk.StringVar(value="15")

        self.batch_entry = ttk.Entry(left, textvariable=self.batch_var)
        self.batch_entry.pack(fill="x")
        # download button
        btn_frame = ttk.Frame(left)   # parent = frame/tab tempat download
        btn_frame.pack(pady=10)
        self.download_btn = ttk.Button(
            btn_frame,
            text="Start Download",
            command=self.start_download
        )
        self.download_btn.pack(side="left", padx=5)
        self.stop_btn = ttk.Button(
            btn_frame,
            text="Stop",
            command=self.stop_download,
            state="disabled"
        )
        self.stop_btn.pack(side="left", padx=5)

        # ===== RIGHT PANEL (LOG) =====
        right = ttk.Frame(self.frame, style="Panel.TFrame")
        right.grid(row=0, column=1, sticky="nsew")

        ttk.Label(right, text="Download Log").pack(anchor="w", padx=5, pady=5)

        self.log_text = tk.Text(
            right,
            wrap="word",
            bg="#2b2b2b",
            fg="#eaeaea",
            insertbackground="white",
            state="disabled"
        )
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(self.log_text, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

    # ================= LOG =================
    def log(self, text):
        self.log_text.config(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")
        self.log_text.config(
            font=("Consolas", 10),
            bg="#0f1117",
            fg="#dcdcdc",
            insertbackground="white"
        )


    # ================= ACTIONS =================
    def browse_list(self):
        path = filedialog.askopenfilename(
            filetypes=[("Text file", "*.txt")]
        )
        if path:
            self.list_entry.delete(0, tk.END)
            self.list_entry.insert(0, path)

    def start_download(self):
        if self.is_downloading:
            return

        list_path = self.list_entry.get()
        folder = self.folder_entry.get().strip()
        fmt = self.format_var.get()
        # validate batch size
        try:
            batch_size = int(self.batch_var.get())
            if batch_size <= 0:
                raise ValueError
        except:
            messagebox.showerror("Error", "Batch size harus angka > 0")
            return
        if not os.path.exists(list_path):
            messagebox.showerror("Error", "list.txt tidak ditemukan")
            return

        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Error", "Folder output belum dipilih")
            return

        os.makedirs(folder, exist_ok=True)

        self.is_downloading = True
        
        self.stop_event.clear()
        self.download_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

        self.download_thread = threading.Thread(
            target=self.run_download,
            args=(list_path, folder, fmt, batch_size),
            daemon=True
        )
        self.download_thread.start()
    def stop_download(self):
        self.stop_event.set()

        if self.process:
            try:
                if platform.system() == "Windows":
                    self.process.send_signal(subprocess.signal.CTRL_BREAK_EVENT)
                else:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)

                self.log("⛔ Download dihentikan")
            except Exception as e:
                self.log(f"Stop error: {e}")

        self.stop_btn.config(state="disabled")
        self.download_btn.config(state="normal")


    # ================= yt-dlp =================
    def run_download(self, list_path, folder, fmt, batch_size):
        try:
            self.log("Starting download...")
            self.log(f"Format : {fmt}")
            self.log(f"Output : {folder}\n")
            self.log(f"YTDLP  : {YTDLP}")
            self.log(f"FFMPEG : {FFMPEG}")
            self.log(f"FFPROBE: {FFPROBE}")
           
            if fmt == "mp3":
                cmd = [
                    YTDLP,
                    "-a", list_path,
                    "--ffmpeg-location",FFMPEG,
                    "-x",
                    "--audio-format", "mp3",
                    "--audio-quality", "0",
                    "-o", f"{folder}/%(title)s.%(ext)s"
                ]
            else:  # mp4
                cmd = [
                    YTDLP,
                    "-a", list_path,
                    "--ffmpeg-location", FFMPEG,
                    "-f", "bv*+ba/b",
                    "--merge-output-format", "mp4",
                    "-o", os.path.join(folder, "%(title)s.%(ext)s")
                ]
            self.log(f"Using ffmpeg from: {FFMPEG}")

            if platform.system() == "Windows":
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    preexec_fn=os.setsid
                )


            for line in self.process.stdout:
                if self.stop_event.is_set():
                    break
                self.log(line.strip())

            self.process.wait()
            # 👇 TAMBAHKAN DI SINI
            if self.stop_event.is_set() or self.process.returncode != 0:
                self.log("Download dihentikan atau gagal, skip organize.")
                return
            self.log("\nDownload finished ✅")
            if fmt == "mp3":
                self.split_into_batches(folder, batch_size)

        except Exception as e:
            self.log(f"ERROR: {e}")

        finally:
            self.is_downloading = False
            self.process = None
            self.stop_btn.config(state="disabled"),
            self.download_btn.config(state="normal")
            self.open_folder(folder)
    def split_into_batches(self, folder, batch_size):
        self.log("\nOrganizing files into folders...")

        files = [
            f for f in os.listdir(folder)
            if f.lower().endswith(".mp3")
        ]

        files.sort()

        for i in range(0, len(files), batch_size):
            batch = files[i:i + batch_size]
            batch_index = (i // batch_size) + 1

            batch_folder = os.path.join(folder, f"media_{batch_index}")
            os.makedirs(batch_folder, exist_ok=True)

            for fname in batch:
                src = os.path.join(folder, fname)
                dst = os.path.join(batch_folder, fname)
                os.rename(src, dst)

        self.log("Done organizing ✅")

