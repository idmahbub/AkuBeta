from tkinter import filedialog, messagebox, ttk
import tkinter as tk
from tkinter import filedialog
import os

class RenameTab:
    def __init__(self, app):
        self.app = app   # referensi ke main app
    def build(self, parent):
        parent.columnconfigure(1, weight=1)

        ttk.Label(parent, text="Folder:").grid(row=0, column=0, padx=10)

        self.rename_folder_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.rename_folder_var)\
            .grid(row=0, column=1, sticky="ew")

        ttk.Button(
            parent,
            text="Browse",
            command=self.select_rename_folder
        ).grid(row=0, column=2)

        ttk.Label(parent, text="Extension:").grid(row=1, column=0, padx=10)

        self.rename_ext_var = tk.StringVar(value=".png")
        ttk.Entry(parent, textvariable=self.rename_ext_var, width=10)\
            .grid(row=1, column=1, sticky="w")

        ttk.Button(
            parent,
            text="Rename Files",
            command=self.rename_files
        ).grid(row=2, column=1, sticky="w", pady=10)

        self.rename_log = tk.Text(parent, height=10)
        self.rename_log.grid(row=3, column=0, columnspan=3, sticky="nsew", padx=10)

        parent.rowconfigure(3, weight=1)
    def select_rename_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.rename_folder_var.set(folder)

    def rename_files(self):
        folder = self.rename_folder_var.get()
        ext = self.rename_ext_var.get().lower()

        if not os.path.isdir(folder):
            self.rename_log.insert("end", "❌ Folder tidak valid\n")
            return

        files = [f for f in os.listdir(folder) if f.lower().endswith(ext)]
        files.sort()

        if not files:
            self.rename_log.insert("end", "⚠️ Tidak ada file\n")
            return

        self.rename_log.delete("1.0", "end")

        # rename aman (2-step)
        temp = []
        for i, f in enumerate(files):
            src = os.path.join(folder, f)
            tmp = os.path.join(folder, f"__tmp__{i}{ext}")
            os.rename(src, tmp)
            temp.append(tmp)

        for i, tmp in enumerate(temp, start=1):
            dst = os.path.join(folder, f"{i}{ext}")
            os.rename(tmp, dst)
            self.rename_log.insert("end", f"✔ {i}{ext}\n")

        self.rename_log.insert("end", "\n✅ Selesai\n")
