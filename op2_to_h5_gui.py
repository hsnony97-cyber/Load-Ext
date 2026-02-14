"""
OP2 to HDF5 Converter - GUI
============================
MSC Nastran OP2 dosyalarini HDF5 (.h5) formatina donusturen
masaustu arayuzu.

Kullanim:
    python op2_to_h5_gui.py
"""

import os
import sys
import threading
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from pyNastran.op2.op2 import OP2
from msc_h5_writer import write_msc_h5


class ConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("OP2 -> H5 Donusturucu")
        self.geometry("700x520")
        self.resizable(True, True)
        self.minsize(550, 420)

        self.op2_files = []
        self.output_dir = tk.StringVar(value="")
        self._converting = False

        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        # --- Dosya secimi ---
        file_frame = ttk.LabelFrame(self, text="OP2 Dosyalari")
        file_frame.pack(fill="x", **pad)

        btn_row = ttk.Frame(file_frame)
        btn_row.pack(fill="x", **pad)

        ttk.Button(btn_row, text="Dosya Ekle", command=self._add_files).pack(
            side="left", padx=(0, 4)
        )
        ttk.Button(btn_row, text="Klasor Ekle", command=self._add_folder).pack(
            side="left", padx=(0, 4)
        )
        ttk.Button(btn_row, text="Secileni Kaldir", command=self._remove_selected).pack(
            side="left", padx=(0, 4)
        )
        ttk.Button(btn_row, text="Temizle", command=self._clear_files).pack(
            side="left"
        )

        list_frame = ttk.Frame(file_frame)
        list_frame.pack(fill="both", expand=True, **pad)

        self.file_listbox = tk.Listbox(
            list_frame, selectmode="extended", height=8
        )
        self.file_listbox.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(
            list_frame, orient="vertical", command=self.file_listbox.yview
        )
        scrollbar.pack(side="right", fill="y")
        self.file_listbox.config(yscrollcommand=scrollbar.set)

        self.file_count_label = ttk.Label(file_frame, text="0 dosya secili")
        self.file_count_label.pack(anchor="w", **pad)

        # --- Cikti klasoru ---
        out_frame = ttk.LabelFrame(self, text="Cikti Klasoru")
        out_frame.pack(fill="x", **pad)

        out_row = ttk.Frame(out_frame)
        out_row.pack(fill="x", **pad)

        ttk.Entry(out_row, textvariable=self.output_dir).pack(
            side="left", fill="x", expand=True, padx=(0, 4)
        )
        ttk.Button(out_row, text="Gozat...", command=self._browse_output).pack(
            side="right"
        )

        # --- Donustur butonu ---
        self.convert_btn = ttk.Button(
            self, text="Donustur", command=self._start_conversion
        )
        self.convert_btn.pack(**pad)

        # --- Progress bar ---
        self.progress = ttk.Progressbar(self, mode="determinate")
        self.progress.pack(fill="x", **pad)

        # --- Log alani ---
        log_frame = ttk.LabelFrame(self, text="Log")
        log_frame.pack(fill="both", expand=True, **pad)

        self.log_text = tk.Text(log_frame, height=8, state="disabled", wrap="word")
        self.log_text.pack(side="left", fill="both", expand=True, padx=4, pady=4)

        log_scroll = ttk.Scrollbar(
            log_frame, orient="vertical", command=self.log_text.yview
        )
        log_scroll.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=log_scroll.set)

    # --------------------------------------------------------- Dosya islemleri
    def _add_files(self):
        files = filedialog.askopenfilenames(
            title="OP2 Dosyalarini Secin",
            filetypes=[("OP2 Dosyalari", "*.op2"), ("Tum Dosyalar", "*.*")],
        )
        for f in files:
            if f not in self.op2_files:
                self.op2_files.append(f)
                self.file_listbox.insert("end", f)
        self._update_count()

    def _add_folder(self):
        folder = filedialog.askdirectory(title="OP2 Klasorunu Secin")
        if not folder:
            return
        import glob

        found = sorted(glob.glob(os.path.join(folder, "*.op2")))
        if not found:
            messagebox.showwarning("Uyari", "Secilen klasorde .op2 dosyasi bulunamadi.")
            return
        for f in found:
            if f not in self.op2_files:
                self.op2_files.append(f)
                self.file_listbox.insert("end", f)
        self._update_count()

    def _remove_selected(self):
        selected = list(self.file_listbox.curselection())
        for idx in reversed(selected):
            self.file_listbox.delete(idx)
            del self.op2_files[idx]
        self._update_count()

    def _clear_files(self):
        self.file_listbox.delete(0, "end")
        self.op2_files.clear()
        self._update_count()

    def _update_count(self):
        self.file_count_label.config(text=f"{len(self.op2_files)} dosya secili")

    def _browse_output(self):
        d = filedialog.askdirectory(title="Cikti Klasorunu Secin")
        if d:
            self.output_dir.set(d)

    # ------------------------------------------------------------ Log
    def _log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    # ------------------------------------------------------------ Donusum
    def _start_conversion(self):
        if self._converting:
            return

        if not self.op2_files:
            messagebox.showwarning("Uyari", "Lutfen en az bir OP2 dosyasi secin.")
            return

        out = self.output_dir.get().strip()
        if not out:
            messagebox.showwarning("Uyari", "Lutfen cikti klasorunu secin.")
            return

        os.makedirs(out, exist_ok=True)
        self._converting = True
        self.convert_btn.config(state="disabled")
        self.progress["value"] = 0
        self.progress["maximum"] = len(self.op2_files)

        thread = threading.Thread(
            target=self._convert_worker,
            args=(list(self.op2_files), out),
            daemon=True,
        )
        thread.start()

    def _convert_worker(self, files, output_dir):
        success = 0
        failed = 0

        for i, op2_path in enumerate(files, 1):
            name = os.path.basename(op2_path)
            self.after(0, self._log, f"[{i}/{len(files)}] {name}")

            basename = os.path.splitext(name)[0]
            h5_path = os.path.join(output_dir, basename + ".h5")

            try:
                self.after(0, self._log, f"  Okunuyor: {op2_path}")
                op2_model = OP2()
                op2_model.read_op2(op2_path)

                self.after(0, self._log, f"  Yaziliyor (MSC formati): {h5_path}")
                write_msc_h5(op2_model, h5_path,
                             log=lambda msg: self.after(0, self._log, msg))

                self.after(0, self._log, f"  Basarili: {h5_path}")
                success += 1
            except Exception:
                err = traceback.format_exc()
                self.after(0, self._log, f"  HATA: {name}\n{err}")
                failed += 1

            self.after(0, self._update_progress, i)

        summary = (
            f"\n{'='*40}\n"
            f"  Toplam   : {len(files)}\n"
            f"  Basarili : {success}\n"
            f"  Basarisiz: {failed}\n"
            f"{'='*40}"
        )
        self.after(0, self._log, summary)
        self.after(0, self._conversion_done, success, failed)

    def _update_progress(self, value):
        self.progress["value"] = value

    def _conversion_done(self, success, failed):
        self._converting = False
        self.convert_btn.config(state="normal")

        if failed == 0:
            messagebox.showinfo("Tamamlandi", f"{success} dosya basariyla donusturuldu.")
        else:
            messagebox.showwarning(
                "Tamamlandi",
                f"{success} basarili, {failed} basarisiz.\nDetaylar icin log'a bakin.",
            )


if __name__ == "__main__":
    app = ConverterApp()
    app.mainloop()
