"""
OP2 to HDF5 Converter - MSC Nastran Native Format
==================================================
MSC Nastran OP2 dosyalarini MSC Nastran native HDF5 (.h5) formatina
donusturen masaustu arayuzu.  Tek dosya - harici modül gerektirmez.

Kullanim:
    python op2_to_h5_gui.py
"""

import os
import glob
import threading
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
import h5py
from pyNastran.op2.op2 import OP2


# ═══════════════════════════════════════════════════════════════
#  MSC Nastran HDF5 dtype tanimlari
# ═══════════════════════════════════════════════════════════════

DOMAIN_DTYPE = np.dtype([
    ('ID', '<i8'), ('SUBCASE', '<i8'), ('STEP', '<i8'),
    ('ANALYSIS', '<i8'), ('TIME_FREQ_EIGR', '<f8'), ('EIGI', '<f8'),
    ('MODE', '<i8'), ('DESIGN_CYCLE', '<i8'), ('RANDOM', '<i8'),
    ('SE', '<i8'), ('AFPM', '<i8'), ('TRMC', '<i8'),
    ('INSTANCE', '<i8'), ('MODULE', '<i8'),
])

INDEX_DTYPE = np.dtype([
    ('DOMAIN_ID', '<i8'), ('POSITION', '<i8'), ('LENGTH', '<i8'),
])

NODAL_DTYPE = np.dtype([
    ('ID', '<i8'), ('X', '<f8'), ('Y', '<f8'), ('Z', '<f8'),
    ('RX', '<f8'), ('RY', '<f8'), ('RZ', '<f8'), ('DOMAIN_ID', '<i8'),
])

PLATE_STRESS_DTYPE = np.dtype([
    ('EID', '<i8'),
    ('FD1', '<f8'), ('X1', '<f8'), ('Y1', '<f8'), ('XY1', '<f8'),
    ('FD2', '<f8'), ('X2', '<f8'), ('Y2', '<f8'), ('XY2', '<f8'),
    ('DOMAIN_ID', '<i8'),
])

BAR_STRESS_DTYPE = np.dtype([
    ('EID', '<i8'),
    ('X1A', '<f8'), ('X2A', '<f8'), ('X3A', '<f8'), ('X4A', '<f8'),
    ('AX', '<f8'), ('MAXA', '<f8'), ('MINA', '<f8'), ('MST', '<f8'),
    ('X1B', '<f8'), ('X2B', '<f8'), ('X3B', '<f8'), ('X4B', '<f8'),
    ('MAXB', '<f8'), ('MINB', '<f8'), ('MSC', '<f8'),
    ('DOMAIN_ID', '<i8'),
])

ROD_STRESS_DTYPE = np.dtype([
    ('EID', '<i8'), ('A', '<f8'), ('MSA', '<f8'),
    ('T', '<f8'), ('MST', '<f8'), ('DOMAIN_ID', '<i8'),
])

BUSH_STRESS_DTYPE = np.dtype([
    ('EID', '<i8'), ('TX', '<f8'), ('TY', '<f8'), ('TZ', '<f8'),
    ('RX', '<f8'), ('RY', '<f8'), ('RZ', '<f8'), ('DOMAIN_ID', '<i8'),
])

_SOLID_SS = np.dtype([
    ('GRID', '<i8'), ('X', '<f8'), ('Y', '<f8'), ('Z', '<f8'),
    ('TXY', '<f8'), ('TYZ', '<f8'), ('TZX', '<f8'),
])


def _solid_dtype(npts):
    return np.dtype([
        ('EID', '<i8'), ('CID', '<i8'), ('CTYPE', 'S4'), ('NODEF', '<i8'),
        ('SS', _SOLID_SS, (npts,)), ('DOMAIN_ID', '<i8'),
    ])


HEXA_STRESS_DTYPE = _solid_dtype(9)
PENTA_STRESS_DTYPE = _solid_dtype(7)
TETRA_STRESS_DTYPE = _solid_dtype(5)

BAR_FORCE_DTYPE = np.dtype([
    ('EID', '<i8'),
    ('BM1A', '<f8'), ('BM2A', '<f8'), ('BM1B', '<f8'), ('BM2B', '<f8'),
    ('TS1', '<f8'), ('TS2', '<f8'), ('AF', '<f8'), ('TRQ', '<f8'),
    ('DOMAIN_ID', '<i8'),
])

ROD_FORCE_DTYPE = np.dtype([
    ('EID', '<i8'), ('AF', '<f8'), ('TRQ', '<f8'), ('DOMAIN_ID', '<i8'),
])

BUSH_FORCE_DTYPE = np.dtype([
    ('EID', '<i8'), ('FX', '<f8'), ('FY', '<f8'), ('FZ', '<f8'),
    ('MX', '<f8'), ('MY', '<f8'), ('MZ', '<f8'), ('DOMAIN_ID', '<i8'),
])

QUAD4_FORCE_DTYPE = np.dtype([
    ('EID', '<i8'),
    ('MX', '<f8'), ('MY', '<f8'), ('MXY', '<f8'),
    ('BMX', '<f8'), ('BMY', '<f8'), ('BMXY', '<f8'),
    ('TX', '<f8'), ('TY', '<f8'),
    ('DOMAIN_ID', '<i8'),
])

# ── Kolon esleme tablolari ──
BAR_STRESS_COLS = [
    ('X1A', 0), ('X2A', 1), ('X3A', 2), ('X4A', 3),
    ('AX', 4), ('MAXA', 5), ('MINA', 6), ('MST', 7),
    ('X1B', 8), ('X2B', 9), ('X3B', 10), ('X4B', 11),
    ('MAXB', 12), ('MINB', 13), ('MSC', 14),
]
ROD_STRESS_COLS = [('A', 0), ('MSA', 1), ('T', 2), ('MST', 3)]
BUSH_STRESS_COLS = [
    ('TX', 0), ('TY', 1), ('TZ', 2), ('RX', 3), ('RY', 4), ('RZ', 5),
]
BAR_FORCE_COLS = [
    ('BM1A', 0), ('BM2A', 1), ('BM1B', 2), ('BM2B', 3),
    ('TS1', 4), ('TS2', 5), ('AF', 6), ('TRQ', 7),
]
ROD_FORCE_COLS = [('AF', 0), ('TRQ', 1)]
BUSH_FORCE_COLS = [
    ('FX', 0), ('FY', 1), ('FZ', 2), ('MX', 3), ('MY', 4), ('MZ', 5),
]
QUAD4_FORCE_COLS = [
    ('MX', 0), ('MY', 1), ('MXY', 2), ('BMX', 3),
    ('BMY', 4), ('BMXY', 5), ('TX', 6), ('TY', 7),
]


# ═══════════════════════════════════════════════════════════════
#  Domain yoneticisi
# ═══════════════════════════════════════════════════════════════

class _Domains:
    def __init__(self):
        self._map = {}
        self._records = []

    def get_id(self, subcase, itime, result):
        key = (subcase, itime)
        if key in self._map:
            return self._map[key]

        did = len(self._records) + 1
        self._map[key] = did

        rec = np.zeros(1, dtype=DOMAIN_DTYPE)
        rec['ID'] = did
        rec['SUBCASE'] = subcase

        if hasattr(result, 'analysis_code'):
            rec['ANALYSIS'] = int(result.analysis_code)

        modes = getattr(result, 'modes', None)
        if modes is not None and itime < len(modes):
            rec['MODE'] = int(modes[itime])

        eigrs = getattr(result, 'eigrs', None)
        if eigrs is not None and itime < len(eigrs):
            rec['TIME_FREQ_EIGR'] = float(eigrs[itime])
        else:
            times = getattr(result, '_times', None)
            if times is not None and itime < len(times):
                rec['TIME_FREQ_EIGR'] = float(times[itime])

        self._records.append(rec[0])
        return did

    def to_array(self):
        if not self._records:
            return np.zeros(0, dtype=DOMAIN_DTYPE)
        out = np.zeros(len(self._records), dtype=DOMAIN_DTYPE)
        for i, r in enumerate(self._records):
            out[i] = r
        return out


# ═══════════════════════════════════════════════════════════════
#  HDF5 yazim yardimcilari
# ═══════════════════════════════════════════════════════════════

def _save(h5, path, data_list, index_list):
    if not data_list:
        return
    data = np.concatenate(data_list)
    h5.create_dataset(path, data=data)
    idx = np.array(index_list, dtype=INDEX_DTYPE)
    h5.create_dataset(f'/INDEX{path}', data=idx)


def _write_nodal(h5, name, result_dict, dom):
    rows_list, idx_list, pos = [], [], 0
    for sc in sorted(result_dict):
        res = result_dict[sc]
        nids = res.node_gridtype[:, 0]
        ntimes = res.data.shape[0]
        ncols = min(res.data.shape[2], 6)
        for it in range(ntimes):
            did = dom.get_id(sc, it, res)
            n = len(nids)
            arr = np.zeros(n, dtype=NODAL_DTYPE)
            arr['ID'] = nids
            for c, f in enumerate(['X', 'Y', 'Z', 'RX', 'RY', 'RZ'][:ncols]):
                arr[f] = res.data[it, :, c]
            arr['DOMAIN_ID'] = did
            rows_list.append(arr)
            idx_list.append((did, pos, n))
            pos += n
    _save(h5, f'/NASTRAN/RESULT/NODAL/{name}', rows_list, idx_list)


def _write_plate_stress(h5, msc_name, result_dict, dom, category):
    rows_list, idx_list, pos = [], [], 0
    for sc in sorted(result_dict):
        res = result_dict[sc]
        en = res.element_node
        ntimes = res.data.shape[0]
        nnodes = getattr(res, 'nnodes_per_element', None)
        if nnodes is None:
            nnodes = getattr(res, 'nnodes', 1)
        rpe = 2 * nnodes
        n_elem = len(en) // rpe
        eids = en[::rpe, 0]
        for it in range(ntimes):
            did = dom.get_id(sc, it, res)
            d = res.data[it]
            top_i = np.arange(0, len(en), rpe)
            bot_i = top_i + 1
            top, bot = d[top_i], d[bot_i]
            arr = np.zeros(n_elem, dtype=PLATE_STRESS_DTYPE)
            arr['EID'] = eids
            arr['FD1'] = top[:, 0]; arr['X1'] = top[:, 1]
            arr['Y1'] = top[:, 2];  arr['XY1'] = top[:, 3]
            arr['FD2'] = bot[:, 0]; arr['X2'] = bot[:, 1]
            arr['Y2'] = bot[:, 2];  arr['XY2'] = bot[:, 3]
            arr['DOMAIN_ID'] = did
            rows_list.append(arr)
            idx_list.append((did, pos, n_elem))
            pos += n_elem
    _save(h5, f'/NASTRAN/RESULT/ELEMENTAL/{category}/{msc_name}',
          rows_list, idx_list)


def _write_1d_result(h5, path, dtype, col_map, result_dict, dom):
    rows_list, idx_list, pos = [], [], 0
    for sc in sorted(result_dict):
        res = result_dict[sc]
        if hasattr(res, 'element') and res.element is not None:
            eids = res.element
        elif hasattr(res, 'element_node') and res.element_node is not None:
            eids = res.element_node[:, 0]
        else:
            continue
        ntimes = res.data.shape[0]
        for it in range(ntimes):
            did = dom.get_id(sc, it, res)
            n = len(eids)
            d = res.data[it]
            arr = np.zeros(n, dtype=dtype)
            arr['EID'] = eids
            for field_name, col_idx in col_map:
                if col_idx < d.shape[1]:
                    arr[field_name] = d[:, col_idx]
            arr['DOMAIN_ID'] = did
            rows_list.append(arr)
            idx_list.append((did, pos, n))
            pos += n
    _save(h5, path, rows_list, idx_list)


def _write_solid_stress(h5, path, npts, dtype, result_dict, dom):
    rows_list, idx_list, pos = [], [], 0
    nodef_map = {9: 8, 7: 6, 5: 4}
    nodef = nodef_map.get(npts, npts - 1)
    for sc in sorted(result_dict):
        res = result_dict[sc]
        en = res.element_node
        ntimes = res.data.shape[0]
        n_elem = len(en) // npts
        en_r = en.reshape(n_elem, npts, 2)
        for it in range(ntimes):
            did = dom.get_id(sc, it, res)
            d = res.data[it].reshape(n_elem, npts, -1)
            arr = np.zeros(n_elem, dtype=dtype)
            arr['EID'] = en_r[:, 0, 0]
            arr['CID'] = 0
            arr['CTYPE'] = b'GRID'
            arr['NODEF'] = nodef
            arr['SS']['GRID'] = en_r[:, :, 1]
            arr['SS']['X'] = d[:, :, 0]
            arr['SS']['Y'] = d[:, :, 1]
            arr['SS']['Z'] = d[:, :, 2]
            arr['SS']['TXY'] = d[:, :, 3]
            arr['SS']['TYZ'] = d[:, :, 4]
            arr['SS']['TZX'] = d[:, :, 5]
            arr['DOMAIN_ID'] = did
            rows_list.append(arr)
            idx_list.append((did, pos, n_elem))
            pos += n_elem
    _save(h5, path, rows_list, idx_list)


# ═══════════════════════════════════════════════════════════════
#  Ana MSC HDF5 donusum fonksiyonu
# ═══════════════════════════════════════════════════════════════

def write_msc_h5(op2, h5_path, log=None):
    """pyNastran OP2 modelini MSC Nastran native HDF5 formatina yazar."""
    def _log(msg):
        if log:
            log(msg)

    dom = _Domains()

    with h5py.File(h5_path, 'w') as h5:

        # Nodal sonuclar
        for name, rdict in [
            ('DISPLACEMENT', op2.displacements),
            ('EIGENVECTOR', op2.eigenvectors),
            ('SPC_FORCE', op2.spc_forces),
            ('MPC_FORCE', op2.mpc_forces),
            ('VELOCITY', op2.velocities),
            ('ACCELERATION', op2.accelerations),
            ('APPLIED_LOAD', op2.load_vectors),
        ]:
            if rdict:
                _log(f'    Nodal/{name}: {len(rdict)} subcase')
                _write_nodal(h5, name, rdict, dom)

        # Elemental stress & strain
        for category in ('STRESS', 'STRAIN'):
            cl = category.lower()
            for elem, attr in [('QUAD4', f'cquad4_{cl}'),
                                ('TRIA3', f'ctria3_{cl}')]:
                rdict = getattr(op2, attr, {})
                if rdict:
                    _log(f'    Elemental/{category}/{elem}: {len(rdict)} subcase')
                    _write_plate_stress(h5, elem, rdict, dom, category)

            for elem, attr, dtype, cols in [
                ('BAR', f'cbar_{cl}', BAR_STRESS_DTYPE, BAR_STRESS_COLS),
                ('ROD', f'crod_{cl}', ROD_STRESS_DTYPE, ROD_STRESS_COLS),
                ('CONROD', f'conrod_{cl}', ROD_STRESS_DTYPE, ROD_STRESS_COLS),
                ('BUSH', f'cbush_{cl}', BUSH_STRESS_DTYPE, BUSH_STRESS_COLS),
            ]:
                rdict = getattr(op2, attr, {})
                if rdict:
                    _log(f'    Elemental/{category}/{elem}: {len(rdict)} subcase')
                    _write_1d_result(h5, f'/NASTRAN/RESULT/ELEMENTAL/{category}/{elem}',
                                     dtype, cols, rdict, dom)

            for elem, attr, npts, dtype in [
                ('HEXA', f'chexa_{cl}', 9, HEXA_STRESS_DTYPE),
                ('PENTA', f'cpenta_{cl}', 7, PENTA_STRESS_DTYPE),
                ('TETRA', f'ctetra_{cl}', 5, TETRA_STRESS_DTYPE),
            ]:
                rdict = getattr(op2, attr, {})
                if rdict:
                    _log(f'    Elemental/{category}/{elem}: {len(rdict)} subcase')
                    _write_solid_stress(h5, f'/NASTRAN/RESULT/ELEMENTAL/{category}/{elem}',
                                        npts, dtype, rdict, dom)

        # Element kuvvetleri
        for elem, attr, dtype, cols in [
            ('BAR', 'cbar_force', BAR_FORCE_DTYPE, BAR_FORCE_COLS),
            ('ROD', 'crod_force', ROD_FORCE_DTYPE, ROD_FORCE_COLS),
            ('BUSH', 'cbush_force', BUSH_FORCE_DTYPE, BUSH_FORCE_COLS),
            ('QUAD4', 'cquad4_force', QUAD4_FORCE_DTYPE, QUAD4_FORCE_COLS),
        ]:
            rdict = getattr(op2, attr, {})
            if rdict:
                _log(f'    ElementForce/{elem}: {len(rdict)} subcase')
                _write_1d_result(h5, f'/NASTRAN/RESULT/ELEMENTAL/ELEMENT_FORCE/{elem}',
                                 dtype, cols, rdict, dom)

        # DOMAINS tablosu
        domains_arr = dom.to_array()
        if len(domains_arr) > 0:
            h5.create_dataset('/NASTRAN/RESULT/DOMAINS', data=domains_arr)
        _log(f'    Toplam {len(dom._records)} domain yazildi')


# ═══════════════════════════════════════════════════════════════
#  GUI
# ═══════════════════════════════════════════════════════════════

class ConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OP2 -> H5 Donusturucu  (MSC Nastran Formati)")
        self.geometry("720x540")
        self.resizable(True, True)
        self.minsize(560, 440)
        self.op2_files = []
        self.output_dir = tk.StringVar(value="")
        self._converting = False
        self._build_ui()

    # ── UI ──
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
