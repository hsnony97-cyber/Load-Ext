"""
OP2 to HDF5 Converter - MSC Nastran Native Format (Patran Compatible)
=====================================================================
MSC Nastran OP2 dosyalarini MSC Nastran native HDF5 (.h5) formatina
donusturen masaustu arayuzu.

Tum HDF5 yazim mantigi msc_h5_writer modulundedir.

Patran uyumlulugu icin asagidaki ogeleri icerir:
  - Root SCHEMA attribute
  - Her dataset'te version attribute
  - /NASTRAN/INPUT/NODE/GRID                (dugum noktasi geometrisi)
  - /NASTRAN/INPUT/ELEMENT/{type}           (CQUAD4, CTRIA3, CBAR, CBUSH, CHEXA, CROD, RBE2, RBE3, ...)
  - /NASTRAN/INPUT/PROPERTY/{type}          (PSHELL, PBAR, PBARL, PBUSH, PCOMP, PROD, PSOLID, ...)
  - /NASTRAN/INPUT/MATERIAL/{type}          (MAT1, MAT2, MAT8, MAT9)
  - /NASTRAN/INPUT/LOAD/FORCE|MOMENT        (yuk kartlari)
  - /NASTRAN/INPUT/COORDINATE_SYSTEM/R|G    (koordinat sistemleri)
  - /NASTRAN/INPUT/CONSTRAINT/SPC           (sinir kosullari)
  - /NASTRAN/INPUT/PARAMETER/PVT/*          (parametreler)
  - /NASTRAN/INPUT/DOMAINS                  (giris domain tablosu)
  - /NASTRAN/RESULT/NODAL/*                 (DISPLACEMENT, SPC_FORCE, APPLIED_LOAD, GRID_FORCE, ...)
  - /NASTRAN/RESULT/ELEMENTAL/STRESS/*      (QUAD4, TRIA3, BAR, ROD, BUSH, BEAM, HEXA, ...)
  - /NASTRAN/RESULT/ELEMENTAL/ELEMENT_FORCE/* (BAR, ROD, BUSH, QUAD4, TRIA3, BEAM)
  - /NASTRAN/RESULT/SUMMARY/EIGENVALUE      (modal analiz ozet)
  - /INDEX/... mirror agaci

Kullanim:
    python op2_to_h5_gui.py
"""

import os
import glob
import threading
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from pyNastran.op2.op2_geom import OP2Geom
from msc_h5_writer import write_msc_h5


# ═══════════════════════════════════════════════════════════════
#  GUI
# ═══════════════════════════════════════════════════════════════

class ConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OP2 -> H5 Donusturucu  (MSC Nastran / Patran Formati)")
        self.geometry("720x540")
        self.resizable(True, True)
        self.minsize(560, 440)
        self.op2_files = []
        self.output_dir = tk.StringVar(value="")
        self._converting = False
        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        # Dosya secimi
        file_frame = ttk.LabelFrame(self, text="OP2 Dosyalari")
        file_frame.pack(fill="x", **pad)

        btn_row = ttk.Frame(file_frame)
        btn_row.pack(fill="x", **pad)
        ttk.Button(btn_row, text="Dosya Ekle", command=self._add_files).pack(
            side="left", padx=(0, 4))
        ttk.Button(btn_row, text="Klasor Ekle", command=self._add_folder).pack(
            side="left", padx=(0, 4))
        ttk.Button(btn_row, text="Secileni Kaldir", command=self._remove_selected).pack(
            side="left", padx=(0, 4))
        ttk.Button(btn_row, text="Temizle", command=self._clear_files).pack(
            side="left")

        list_frame = ttk.Frame(file_frame)
        list_frame.pack(fill="both", expand=True, **pad)
        self.file_listbox = tk.Listbox(list_frame, selectmode="extended", height=8)
        self.file_listbox.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical",
                                  command=self.file_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.file_listbox.config(yscrollcommand=scrollbar.set)

        self.file_count_label = ttk.Label(file_frame, text="0 dosya secili")
        self.file_count_label.pack(anchor="w", **pad)

        # Cikti klasoru
        out_frame = ttk.LabelFrame(self, text="Cikti Klasoru")
        out_frame.pack(fill="x", **pad)
        out_row = ttk.Frame(out_frame)
        out_row.pack(fill="x", **pad)
        ttk.Entry(out_row, textvariable=self.output_dir).pack(
            side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(out_row, text="Gozat...", command=self._browse_output).pack(
            side="right")

        # Donustur butonu
        self.convert_btn = ttk.Button(self, text="Donustur",
                                      command=self._start_conversion)
        self.convert_btn.pack(**pad)

        # Progress bar
        self.progress = ttk.Progressbar(self, mode="determinate")
        self.progress.pack(fill="x", **pad)

        # Log alani
        log_frame = ttk.LabelFrame(self, text="Log")
        log_frame.pack(fill="both", expand=True, **pad)
        self.log_text = tk.Text(log_frame, height=8, state="disabled", wrap="word")
        self.log_text.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical",
                                   command=self.log_text.yview)
        log_scroll.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=log_scroll.set)

    # ── Dosya islemleri ──
    def _add_files(self):
        files = filedialog.askopenfilenames(
            title="OP2 Dosyalarini Secin",
            filetypes=[("OP2 Dosyalari", "*.op2"), ("Tum Dosyalar", "*.*")])
        for f in files:
            if f not in self.op2_files:
                self.op2_files.append(f)
                self.file_listbox.insert("end", f)
        self._update_count()

    def _add_folder(self):
        folder = filedialog.askdirectory(title="OP2 Klasorunu Secin")
        if not folder:
            return
        found = sorted(glob.glob(os.path.join(folder, "*.op2")))
        if not found:
            messagebox.showwarning("Uyari",
                                   "Secilen klasorde .op2 dosyasi bulunamadi.")
            return
        for f in found:
            if f not in self.op2_files:
                self.op2_files.append(f)
                self.file_listbox.insert("end", f)
        self._update_count()

    def _remove_selected(self):
        for idx in reversed(self.file_listbox.curselection()):
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

    # ── Log ──
    def _log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    # ── Donusum ──
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
        threading.Thread(target=self._convert_worker,
                         args=(list(self.op2_files), out),
                         daemon=True).start()

    def _convert_worker(self, files, output_dir):
        success, failed = 0, 0
        for i, op2_path in enumerate(files, 1):
            name = os.path.basename(op2_path)
            self.after(0, self._log, f"[{i}/{len(files)}] {name}")
            basename = os.path.splitext(name)[0]
            h5_path = os.path.join(output_dir, basename + ".h5")
            try:
                self.after(0, self._log, f"  Okunuyor (geometri+sonuc): {op2_path}")
                op2_model = OP2Geom()
                op2_model.read_op2(op2_path)
                # Bulunan verileri logla
                n_nodes = len(getattr(op2_model, 'nodes', {}) or {})
                n_elems = len(getattr(op2_model, 'elements', {}) or {})
                n_props = len(getattr(op2_model, 'properties', {}) or {})
                n_mats = len(getattr(op2_model, 'materials', {}) or {})
                n_rigid = len(getattr(op2_model, 'rigid_elements', {}) or {})
                n_coords = len(getattr(op2_model, 'coords', {}) or {})
                n_loads = len(getattr(op2_model, 'loads', {}) or {})
                self.after(0, self._log,
                    f"  Geometri: {n_nodes} dugum, {n_elems} eleman, "
                    f"{n_props} ozellik, {n_mats} malzeme, "
                    f"{n_rigid} rigid, {n_coords} coord, {n_loads} yuk")
                # Sonuc verilerini logla
                result_info = []
                for rname, rattr in [
                    ('disp', 'displacements'), ('spc', 'spc_forces'),
                    ('applied', 'load_vectors'), ('gpf', 'grid_point_forces'),
                    ('bar_f', 'cbar_force'), ('rod_f', 'crod_force'),
                    ('bush_f', 'cbush_force'), ('quad4_f', 'cquad4_force'),
                    ('tria3_f', 'ctria3_force'),
                    ('bar_s', 'cbar_stress'), ('quad4_s', 'cquad4_stress'),
                ]:
                    rd = getattr(op2_model, rattr, {})
                    if rd:
                        result_info.append(f'{rname}={len(rd)}')
                if result_info:
                    self.after(0, self._log, f"  Sonuclar: {', '.join(result_info)}")
                else:
                    self.after(0, self._log, f"  Sonuclar: sadece nodal veriler")
                self.after(0, self._log, f"  Yaziliyor (MSC/Patran formati): {h5_path}")
                write_msc_h5(op2_model, h5_path,
                             log=lambda msg: self.after(0, self._log, msg))
                self.after(0, self._log, f"  Basarili: {h5_path}")
                success += 1
            except Exception:
                err = traceback.format_exc()
                self.after(0, self._log, f"  HATA: {name}\n{err}")
                failed += 1
            self.after(0, self._update_progress, i)

        summary = (f"\n{'='*40}\n"
                   f"  Toplam   : {len(files)}\n"
                   f"  Basarili : {success}\n"
                   f"  Basarisiz: {failed}\n"
                   f"{'='*40}")
        self.after(0, self._log, summary)
        self.after(0, self._conversion_done, success, failed)

    def _update_progress(self, value):
        self.progress["value"] = value

    def _conversion_done(self, success, failed):
        self._converting = False
        self.convert_btn.config(state="normal")
        if failed == 0:
            messagebox.showinfo("Tamamlandi",
                                f"{success} dosya basariyla donusturuldu.")
        else:
            messagebox.showwarning(
                "Tamamlandi",
                f"{success} basarili, {failed} basarisiz.\nDetaylar icin log'a bakin.")


if __name__ == "__main__":
    app = ConverterApp()
    app.mainloop()
