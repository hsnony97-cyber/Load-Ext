"""
OP2 to HDF5 Converter - MSC Nastran Native Format (Patran Compatible)
=====================================================================
MSC Nastran OP2 dosyalarini MSC Nastran native HDF5 (.h5) formatina
donusturen masaustu arayuzu.  Tek dosya - harici modul gerektirmez.

Patran uyumlulugu icin asagidaki ogeleri icerir:
  - Root SCHEMA attribute
  - Her dataset'te version attribute
  - /NASTRAN/INPUT/NODE/GRID         (dugum noktasi geometrisi)
  - /NASTRAN/INPUT/ELEMENT/{type}    (eleman baglantilari)
  - /NASTRAN/INPUT/PROPERTY/{type}   (ozellik kartlari)
  - /NASTRAN/INPUT/MATERIAL/{type}   (malzeme kartlari)
  - /NASTRAN/INPUT/DOMAINS           (giris domain tablosu)
  - /NASTRAN/RESULT/SUMMARY/EIGENVALUE  (modal analiz ozet)
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

import numpy as np
import h5py
from pyNastran.op2.op2 import OP2


# ═══════════════════════════════════════════════════════════════
#  Sabitler
# ═══════════════════════════════════════════════════════════════

MSC_SCHEMA_VERSION = np.int64(20182)

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

INPUT_DOMAIN_DTYPE = np.dtype([
    ('ID', '<i8'), ('SE', '<i8'), ('AFPM', '<i8'),
    ('TRMC', '<i8'), ('MODULE', '<i8'),
])

INDEX_DTYPE = np.dtype([
    ('DOMAIN_ID', '<i8'), ('POSITION', '<i8'), ('LENGTH', '<i8'),
])

NODAL_DTYPE = np.dtype([
    ('ID', '<i8'), ('X', '<f8'), ('Y', '<f8'), ('Z', '<f8'),
    ('RX', '<f8'), ('RY', '<f8'), ('RZ', '<f8'), ('DOMAIN_ID', '<i8'),
])

# --- INPUT/NODE/GRID ---
GRID_DTYPE = np.dtype([
    ('ID', '<i8'), ('CP', '<i8'), ('X', '<f8', (3,)),
    ('CD', '<i8'), ('PS', '<i8'), ('SEID', '<i8'), ('DOMAIN_ID', '<i8'),
])

# --- Eigenvalue summary ---
EIGENVALUE_DTYPE = np.dtype([
    ('MODE', '<i8'), ('ORDER', '<i8'), ('EIGEN', '<f8'),
    ('OMEGA', '<f8'), ('FREQ', '<f8'), ('MASS', '<f8'),
    ('STIFF', '<f8'), ('RESFLG', '<i8'), ('FLDFLG', '<i8'),
    ('DOMAIN_ID', '<i8'),
])

# --- Plate stress/strain ---
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

BEAM_STRESS_DTYPE = np.dtype([
    ('EID', '<i8'), ('NID', '<i8'),
    ('LONG', '<f8'), ('LS1', '<f8'), ('LS2', '<f8'),
    ('LS3', '<f8'), ('LS4', '<f8'),
    ('SMAX', '<f8'), ('SMIN', '<f8'),
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

BEAM_FORCE_DTYPE = np.dtype([
    ('EID', '<i8'), ('NIDA', '<i8'),
    ('BM1A', '<f8'), ('BM2A', '<f8'), ('TS1A', '<f8'), ('TS2A', '<f8'),
    ('AFA', '<f8'), ('TRQA', '<f8'),
    ('NIDB', '<i8'),
    ('BM1B', '<f8'), ('BM2B', '<f8'), ('TS1B', '<f8'), ('TS2B', '<f8'),
    ('AFB', '<f8'), ('TRQB', '<f8'),
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

# --- QUAD4 corner stress (QUAD_CN) ---
# MSC Nastran STRESS(CORNER) isteginde QUAD_CN olarak yazar
QUAD_CN_STRESS_DTYPE = np.dtype([
    ('EID', '<i8'), ('TERM', 'S4'), ('GRID', '<i8'),
    ('FD1', '<f8'), ('X1', '<f8'), ('Y1', '<f8'), ('XY1', '<f8'),
    ('FD2', '<f8'), ('X2', '<f8'), ('Y2', '<f8'), ('XY2', '<f8'),
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
#  INPUT element dtype haritasi (pyNastran card_name -> HDF5)
# ═══════════════════════════════════════════════════════════════

def _elem_dtype(nnodes):
    """Genel eleman dtype'i: EID, PID, G(nnodes), DOMAIN_ID."""
    return np.dtype([
        ('EID', '<i8'), ('PID', '<i8'),
        ('G', '<i8', (nnodes,)),
        ('DOMAIN_ID', '<i8'),
    ])

# CQUAD4 ve CTRIA3 ozel alanlar iceriyor
CQUAD4_INPUT_DTYPE = np.dtype([
    ('EID', '<i8'), ('PID', '<i8'), ('G', '<i8', (4,)),
    ('THETA', '<f8'), ('ZOFFS', '<f8'), ('TFLAG', '<i8'),
    ('T', '<f8', (4,)), ('MCID', '<i8'), ('DOMAIN_ID', '<i8'),
])

CTRIA3_INPUT_DTYPE = np.dtype([
    ('EID', '<i8'), ('PID', '<i8'), ('G', '<i8', (3,)),
    ('THETA', '<f8'), ('ZOFFS', '<f8'), ('TFLAG', '<i8'),
    ('T', '<f8', (3,)), ('MCID', '<i8'), ('DOMAIN_ID', '<i8'),
])


# ═══════════════════════════════════════════════════════════════
#  INPUT property dtype haritasi
# ═══════════════════════════════════════════════════════════════

PROD_DTYPE = np.dtype([
    ('PID', '<i8'), ('MID', '<i8'), ('A', '<f8'), ('J', '<f8'),
    ('C', '<f8'), ('NSM', '<f8'), ('DOMAIN_ID', '<i8'),
])

PBAR_DTYPE = np.dtype([
    ('PID', '<i8'), ('MID', '<i8'), ('A', '<f8'),
    ('I1', '<f8'), ('I2', '<f8'), ('J', '<f8'), ('NSM', '<f8'),
    ('DOMAIN_ID', '<i8'),
])

PBEAM_DTYPE = np.dtype([
    ('PID', '<i8'), ('MID', '<i8'), ('A', '<f8'),
    ('I1', '<f8'), ('I2', '<f8'), ('I12', '<f8'),
    ('J', '<f8'), ('NSM', '<f8'),
    ('DOMAIN_ID', '<i8'),
])

PSHELL_DTYPE = np.dtype([
    ('PID', '<i8'), ('MID1', '<i8'), ('T', '<f8'), ('MID2', '<i8'),
    ('BK', '<f8'), ('MID3', '<i8'), ('TS', '<f8'), ('NSM', '<f8'),
    ('Z1', '<f8'), ('Z2', '<f8'), ('MID4', '<i8'),
    ('DOMAIN_ID', '<i8'),
])

PSOLID_DTYPE = np.dtype([
    ('PID', '<i8'), ('MID', '<i8'), ('CORDM', '<i8'),
    ('IN', '<i8'), ('STRESS', '<i8'), ('ISOP', '<i8'),
    ('FCTN', 'S4'), ('DOMAIN_ID', '<i8'),
])

PBUSH_DTYPE = np.dtype([
    ('PID', '<i8'),
    ('K', '<f8', (6,)), ('B', '<f8', (6,)), ('GE', '<f8', (6,)),
    ('DOMAIN_ID', '<i8'),
])

# ═══════════════════════════════════════════════════════════════
#  INPUT material dtype
# ═══════════════════════════════════════════════════════════════

MAT1_DTYPE = np.dtype([
    ('MID', '<i8'), ('E', '<f8'), ('G', '<f8'), ('NU', '<f8'),
    ('RHO', '<f8'), ('A', '<f8'), ('TREF', '<f8'), ('GE', '<f8'),
    ('ST', '<f8'), ('SC', '<f8'), ('SS', '<f8'), ('MCSID', '<i8'),
    ('DOMAIN_ID', '<i8'),
])

MAT2_DTYPE = np.dtype([
    ('MID', '<i8'),
    ('G11', '<f8'), ('G12', '<f8'), ('G13', '<f8'),
    ('G22', '<f8'), ('G23', '<f8'), ('G33', '<f8'),
    ('RHO', '<f8'),
    ('A1', '<f8'), ('A2', '<f8'), ('A12', '<f8'),
    ('TREF', '<f8'), ('GE', '<f8'),
    ('ST', '<f8'), ('SC', '<f8'), ('SS', '<f8'),
    ('MCSID', '<i8'), ('DOMAIN_ID', '<i8'),
])

MAT8_DTYPE = np.dtype([
    ('MID', '<i8'),
    ('E1', '<f8'), ('E2', '<f8'), ('NU12', '<f8'),
    ('G12', '<f8'), ('G1Z', '<f8'), ('G2Z', '<f8'),
    ('RHO', '<f8'),
    ('A1', '<f8'), ('A2', '<f8'), ('TREF', '<f8'), ('GE', '<f8'),
    ('XT', '<f8'), ('XC', '<f8'), ('YT', '<f8'), ('YC', '<f8'),
    ('S', '<f8'), ('F12', '<f8'),
    ('DOMAIN_ID', '<i8'),
])


# ═══════════════════════════════════════════════════════════════
#  Domain yoneticisi
# ═══════════════════════════════════════════════════════════════

class _Domains:
    def __init__(self):
        self._map = {}
        self._records = []

    # SOL tipleri icin ANALYSIS kodlari
    _SOL_ANALYSIS = {
        101: 1, 103: 2, 105: 7, 106: 10, 107: 9,
        108: 5, 109: 6, 110: 9, 111: 5, 112: 6,
        144: 1, 200: 1,
    }

    def get_id(self, subcase, itime, result):
        key = (subcase, itime)
        if key in self._map:
            return self._map[key]

        did = len(self._records) + 1
        self._map[key] = did

        rec = np.zeros(1, dtype=DOMAIN_DTYPE)
        rec['ID'] = did
        rec['SUBCASE'] = subcase

        # ANALYSIS kodu: oncelikle result.analysis_code, yoksa SOL tipinden cikart
        if hasattr(result, 'analysis_code') and result.analysis_code:
            rec['ANALYSIS'] = int(result.analysis_code)
        else:
            # SOL101 -> ANALYSIS=1 (statics)
            sol = getattr(result, 'sol', None) or getattr(result, 'solution', None)
            if sol and sol in self._SOL_ANALYSIS:
                rec['ANALYSIS'] = self._SOL_ANALYSIS[sol]
            else:
                rec['ANALYSIS'] = 1  # varsayilan: statik

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

        eigis = getattr(result, 'eigis', None)
        if eigis is not None and itime < len(eigis):
            rec['EIGI'] = float(eigis[itime])

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

def _ds(h5, path, data, version=0):
    """Dataset olustur ve version attribute ekle."""
    ds = h5.create_dataset(path, data=data)
    ds.attrs['version'] = np.int64(version)
    return ds


def _save(h5, path, data_list, index_list, version=0):
    """Verileri birlestir, dataset ve INDEX tablosu olustur."""
    if not data_list:
        return
    data = np.concatenate(data_list)
    _ds(h5, path, data, version)
    idx = np.array(index_list, dtype=INDEX_DTYPE)
    _ds(h5, f'/INDEX{path}', idx, 0)


# ═══════════════════════════════════════════════════════════════
#  INPUT yazicilari
# ═══════════════════════════════════════════════════════════════

def _write_input_grids(h5, op2, _log):
    """OP2 modelindeki GRID noktalarini /NASTRAN/INPUT/NODE/GRID'e yazar."""
    nodes = getattr(op2, 'nodes', None) or getattr(op2, 'node_ids', None)
    if nodes is None:
        return

    # pyNastran OP2: op2.nodes -> {nid: GRID_card}
    if isinstance(nodes, dict) and len(nodes) > 0:
        nids = sorted(nodes.keys())
        n = len(nids)
        arr = np.zeros(n, dtype=GRID_DTYPE)
        for i, nid in enumerate(nids):
            card = nodes[nid]
            arr[i]['ID'] = nid
            arr[i]['CP'] = card.cp
            xyz = card.xyz
            arr[i]['X'][0] = xyz[0]
            arr[i]['X'][1] = xyz[1]
            arr[i]['X'][2] = xyz[2]
            arr[i]['CD'] = card.cd
            arr[i]['PS'] = 0
            arr[i]['SEID'] = card.seid
            arr[i]['DOMAIN_ID'] = 1
        _ds(h5, '/NASTRAN/INPUT/NODE/GRID', arr, 0)
        _log(f'    INPUT/NODE/GRID: {n} dugum noktasi')


def _write_input_elements(h5, op2, _log):
    """OP2 modelindeki elemanlari /NASTRAN/INPUT/ELEMENT/{type}'a yazar."""
    elements = getattr(op2, 'elements', None)
    if not elements:
        return

    # Elemanlari tipe gore grupla
    by_type = {}
    for eid, elem in elements.items():
        etype = elem.type
        by_type.setdefault(etype, []).append(elem)

    for etype, elems in sorted(by_type.items()):
        elems_sorted = sorted(elems, key=lambda e: e.eid)
        n = len(elems_sorted)
        path = f'/NASTRAN/INPUT/ELEMENT/{etype}'

        if etype == 'CQUAD4':
            arr = np.zeros(n, dtype=CQUAD4_INPUT_DTYPE)
            for i, e in enumerate(elems_sorted):
                arr[i]['EID'] = e.eid
                arr[i]['PID'] = e.pid
                nids = e.node_ids
                for j in range(min(4, len(nids))):
                    arr[i]['G'][j] = nids[j] if nids[j] is not None else 0
                arr[i]['THETA'] = getattr(e, 'theta_mcid', 0.0) if not isinstance(getattr(e, 'theta_mcid', 0), int) else 0.0
                arr[i]['ZOFFS'] = getattr(e, 'zoffset', 0.0)
                arr[i]['DOMAIN_ID'] = 1

        elif etype == 'CTRIA3':
            arr = np.zeros(n, dtype=CTRIA3_INPUT_DTYPE)
            for i, e in enumerate(elems_sorted):
                arr[i]['EID'] = e.eid
                arr[i]['PID'] = e.pid
                nids = e.node_ids
                for j in range(min(3, len(nids))):
                    arr[i]['G'][j] = nids[j] if nids[j] is not None else 0
                arr[i]['THETA'] = getattr(e, 'theta_mcid', 0.0) if not isinstance(getattr(e, 'theta_mcid', 0), int) else 0.0
                arr[i]['ZOFFS'] = getattr(e, 'zoffset', 0.0)
                arr[i]['DOMAIN_ID'] = 1

        elif etype in ('CROD', 'CONROD'):
            dt = _elem_dtype(2)
            arr = np.zeros(n, dtype=dt)
            for i, e in enumerate(elems_sorted):
                arr[i]['EID'] = e.eid
                arr[i]['PID'] = getattr(e, 'pid', 0)
                nids = e.node_ids
                for j in range(min(2, len(nids))):
                    arr[i]['G'][j] = nids[j]
                arr[i]['DOMAIN_ID'] = 1

        elif etype == 'CBAR':
            dt = _elem_dtype(2)
            arr = np.zeros(n, dtype=dt)
            for i, e in enumerate(elems_sorted):
                arr[i]['EID'] = e.eid
                arr[i]['PID'] = e.pid
                nids = e.node_ids
                for j in range(min(2, len(nids))):
                    arr[i]['G'][j] = nids[j]
                arr[i]['DOMAIN_ID'] = 1

        elif etype == 'CBEAM':
            dt = _elem_dtype(2)
            arr = np.zeros(n, dtype=dt)
            for i, e in enumerate(elems_sorted):
                arr[i]['EID'] = e.eid
                arr[i]['PID'] = e.pid
                nids = e.node_ids
                for j in range(min(2, len(nids))):
                    arr[i]['G'][j] = nids[j]
                arr[i]['DOMAIN_ID'] = 1

        elif etype == 'CBUSH':
            dt = _elem_dtype(2)
            arr = np.zeros(n, dtype=dt)
            for i, e in enumerate(elems_sorted):
                arr[i]['EID'] = e.eid
                arr[i]['PID'] = e.pid
                nids = e.node_ids
                for j in range(min(2, len(nids))):
                    arr[i]['G'][j] = nids[j] if nids[j] is not None else 0
                arr[i]['DOMAIN_ID'] = 1

        elif etype == 'CHEXA':
            dt = _elem_dtype(8)
            arr = np.zeros(n, dtype=dt)
            for i, e in enumerate(elems_sorted):
                arr[i]['EID'] = e.eid
                arr[i]['PID'] = e.pid
                nids = e.node_ids
                for j in range(min(8, len(nids))):
                    arr[i]['G'][j] = nids[j] if nids[j] is not None else 0
                arr[i]['DOMAIN_ID'] = 1

        elif etype == 'CPENTA':
            dt = _elem_dtype(6)
            arr = np.zeros(n, dtype=dt)
            for i, e in enumerate(elems_sorted):
                arr[i]['EID'] = e.eid
                arr[i]['PID'] = e.pid
                nids = e.node_ids
                for j in range(min(6, len(nids))):
                    arr[i]['G'][j] = nids[j] if nids[j] is not None else 0
                arr[i]['DOMAIN_ID'] = 1

        elif etype == 'CTETRA':
            dt = _elem_dtype(4)
            arr = np.zeros(n, dtype=dt)
            for i, e in enumerate(elems_sorted):
                arr[i]['EID'] = e.eid
                arr[i]['PID'] = e.pid
                nids = e.node_ids
                for j in range(min(4, len(nids))):
                    arr[i]['G'][j] = nids[j] if nids[j] is not None else 0
                arr[i]['DOMAIN_ID'] = 1
        else:
            # Desteklenmeyen eleman tipi - atla
            continue

        _ds(h5, path, arr, 0)
        _log(f'    INPUT/ELEMENT/{etype}: {n} eleman')


def _write_input_properties(h5, op2, _log):
    """OP2 modelindeki ozellikleri /NASTRAN/INPUT/PROPERTY/{type}'a yazar."""
    properties = getattr(op2, 'properties', None)
    if not properties:
        return

    by_type = {}
    for pid, prop in properties.items():
        ptype = prop.type
        by_type.setdefault(ptype, []).append(prop)

    for ptype, props in sorted(by_type.items()):
        props_sorted = sorted(props, key=lambda p: p.pid)
        n = len(props_sorted)
        path = f'/NASTRAN/INPUT/PROPERTY/{ptype}'

        if ptype == 'PROD':
            arr = np.zeros(n, dtype=PROD_DTYPE)
            for i, p in enumerate(props_sorted):
                arr[i]['PID'] = p.pid
                arr[i]['MID'] = p.mid
                arr[i]['A'] = p.A
                arr[i]['J'] = p.j
                arr[i]['C'] = p.c
                arr[i]['NSM'] = p.nsm
                arr[i]['DOMAIN_ID'] = 1

        elif ptype == 'PBAR':
            arr = np.zeros(n, dtype=PBAR_DTYPE)
            for i, p in enumerate(props_sorted):
                arr[i]['PID'] = p.pid
                arr[i]['MID'] = p.mid
                arr[i]['A'] = p.A
                arr[i]['I1'] = p.i1
                arr[i]['I2'] = p.i2
                arr[i]['J'] = p.j
                arr[i]['NSM'] = p.nsm
                arr[i]['DOMAIN_ID'] = 1

        elif ptype == 'PBEAM':
            arr = np.zeros(n, dtype=PBEAM_DTYPE)
            for i, p in enumerate(props_sorted):
                arr[i]['PID'] = p.pid
                arr[i]['MID'] = p.mid
                arr[i]['A'] = p.A if hasattr(p, 'A') else getattr(p, 'area', [0.0])[0]
                arr[i]['I1'] = getattr(p, 'i1', getattr(p, 'i1a', 0.0))
                arr[i]['I2'] = getattr(p, 'i2', getattr(p, 'i2a', 0.0))
                arr[i]['I12'] = getattr(p, 'i12', getattr(p, 'i12a', 0.0))
                arr[i]['J'] = p.j
                arr[i]['NSM'] = getattr(p, 'nsm', getattr(p, 'nsm', [0.0])[0] if isinstance(getattr(p, 'nsm', 0), list) else getattr(p, 'nsm', 0.0))
                arr[i]['DOMAIN_ID'] = 1

        elif ptype == 'PSHELL':
            arr = np.zeros(n, dtype=PSHELL_DTYPE)
            for i, p in enumerate(props_sorted):
                arr[i]['PID'] = p.pid
                arr[i]['MID1'] = p.mid1 if p.mid1 is not None else 0
                arr[i]['T'] = p.t if p.t is not None else 0.0
                arr[i]['MID2'] = p.mid2 if p.mid2 is not None else -1
                arr[i]['BK'] = p.twelveIt3 if hasattr(p, 'twelveIt3') else 1.0
                arr[i]['MID3'] = p.mid3 if p.mid3 is not None else -1
                arr[i]['TS'] = p.tst if hasattr(p, 'tst') else 0.833333
                arr[i]['NSM'] = p.nsm
                arr[i]['Z1'] = p.z1 if p.z1 is not None else 0.0
                arr[i]['Z2'] = p.z2 if p.z2 is not None else 0.0
                arr[i]['MID4'] = p.mid4 if p.mid4 is not None else -1
                arr[i]['DOMAIN_ID'] = 1

        elif ptype == 'PSOLID':
            arr = np.zeros(n, dtype=PSOLID_DTYPE)
            for i, p in enumerate(props_sorted):
                arr[i]['PID'] = p.pid
                arr[i]['MID'] = p.mid
                arr[i]['CORDM'] = getattr(p, 'cordm', 0)
                arr[i]['IN'] = getattr(p, 'integ', 0) or 0
                arr[i]['STRESS'] = getattr(p, 'stress', 0) or 0
                arr[i]['ISOP'] = getattr(p, 'isop', 0) or 0
                arr[i]['FCTN'] = b'SMEC'
                arr[i]['DOMAIN_ID'] = 1

        elif ptype == 'PBUSH':
            arr = np.zeros(n, dtype=PBUSH_DTYPE)
            for i, p in enumerate(props_sorted):
                arr[i]['PID'] = p.pid
                Ki = getattr(p, 'Ki', None)
                Bi = getattr(p, 'Bi', None)
                GEi = getattr(p, 'GEi', None)
                if Ki is not None:
                    for j in range(min(6, len(Ki))):
                        if Ki[j] is not None:
                            arr[i]['K'][j] = Ki[j]
                if Bi is not None:
                    for j in range(min(6, len(Bi))):
                        if Bi[j] is not None:
                            arr[i]['B'][j] = Bi[j]
                if GEi is not None:
                    for j in range(min(6, len(GEi))):
                        if GEi[j] is not None:
                            arr[i]['GE'][j] = GEi[j]
                arr[i]['DOMAIN_ID'] = 1
        else:
            continue

        _ds(h5, path, arr, 0)
        _log(f'    INPUT/PROPERTY/{ptype}: {n} ozellik')


def _write_input_materials(h5, op2, _log):
    """OP2 modelindeki malzemeleri /NASTRAN/INPUT/MATERIAL/{type}'a yazar."""
    materials = getattr(op2, 'materials', None)
    if not materials:
        return

    by_type = {}
    for mid, mat in materials.items():
        mtype = mat.type
        by_type.setdefault(mtype, []).append(mat)

    for mtype, mats in sorted(by_type.items()):
        mats_sorted = sorted(mats, key=lambda m: m.mid)
        n = len(mats_sorted)
        path = f'/NASTRAN/INPUT/MATERIAL/{mtype}'

        if mtype == 'MAT1':
            arr = np.zeros(n, dtype=MAT1_DTYPE)
            for i, m in enumerate(mats_sorted):
                arr[i]['MID'] = m.mid
                arr[i]['E'] = m.e if m.e is not None else 0.0
                arr[i]['G'] = m.g if m.g is not None else 0.0
                arr[i]['NU'] = m.nu if m.nu is not None else 0.0
                arr[i]['RHO'] = m.rho
                arr[i]['A'] = m.a if m.a is not None else 0.0
                arr[i]['TREF'] = m.tref
                arr[i]['GE'] = m.ge
                arr[i]['ST'] = getattr(m, 'St', 0.0) or 0.0
                arr[i]['SC'] = getattr(m, 'Sc', 0.0) or 0.0
                arr[i]['SS'] = getattr(m, 'Ss', 0.0) or 0.0
                arr[i]['MCSID'] = getattr(m, 'mcsid', 0)
                arr[i]['DOMAIN_ID'] = 1
        else:
            continue

        _ds(h5, path, arr, 0)
        _log(f'    INPUT/MATERIAL/{mtype}: {n} malzeme')


def _write_input_domains(h5):
    """INPUT domains tablosu (model-level domain)."""
    arr = np.zeros(1, dtype=INPUT_DOMAIN_DTYPE)
    arr[0]['ID'] = 1
    arr[0]['SE'] = 0
    _ds(h5, '/NASTRAN/INPUT/DOMAINS', arr, 0)


# ═══════════════════════════════════════════════════════════════
#  Nodal sonuc yazici
# ═══════════════════════════════════════════════════════════════

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
    _save(h5, f'/NASTRAN/RESULT/NODAL/{name}', rows_list, idx_list, version=1)


# ═══════════════════════════════════════════════════════════════
#  Plate stress/strain yazici
# ═══════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════
#  QUAD_CN corner stress yazici (STRESS(CORNER) ciktisi)
# ═══════════════════════════════════════════════════════════════

def _write_quad_cn_stress(h5, result_dict, dom, category):
    """CQUAD4 corner stress: center + 4 kose = 5 satir/element."""
    rows_list, idx_list, pos = [], [], 0
    for sc in sorted(result_dict):
        res = result_dict[sc]
        en = res.element_node
        ntimes = res.data.shape[0]
        nnodes = getattr(res, 'nnodes_per_element', None)
        if nnodes is None:
            nnodes = getattr(res, 'nnodes', 1)
        if nnodes <= 1:
            continue  # center-only, QUAD_CN degil
        rpe = 2 * nnodes  # top+bot per node => 2*5=10 for QUAD4 corner
        n_elem = len(en) // rpe
        npts = nnodes  # 5 (center + 4 corners)
        total_rows = n_elem * npts * 2  # top & bottom per point

        for it in range(ntimes):
            did = dom.get_id(sc, it, res)
            d = res.data[it]
            n_out = n_elem * npts * 2
            arr = np.zeros(n_out, dtype=QUAD_CN_STRESS_DTYPE)
            row = 0
            for ie in range(n_elem):
                base = ie * rpe
                eid = en[base, 0]
                for ip in range(npts):
                    top_idx = base + ip * 2
                    bot_idx = top_idx + 1
                    grid_id = en[top_idx, 1]
                    term_top = b'Z1' if ip == 0 else b'Z1'
                    term_bot = b'Z2' if ip == 0 else b'Z2'
                    # Top surface
                    arr[row]['EID'] = eid
                    arr[row]['TERM'] = term_top
                    arr[row]['GRID'] = grid_id
                    arr[row]['FD1'] = d[top_idx, 0]
                    arr[row]['X1'] = d[top_idx, 1]
                    arr[row]['Y1'] = d[top_idx, 2]
                    arr[row]['XY1'] = d[top_idx, 3]
                    arr[row]['DOMAIN_ID'] = did
                    row += 1
                    # Bottom surface
                    arr[row]['EID'] = eid
                    arr[row]['TERM'] = term_bot
                    arr[row]['GRID'] = grid_id
                    arr[row]['FD2'] = d[bot_idx, 0]
                    arr[row]['X2'] = d[bot_idx, 1]
                    arr[row]['Y2'] = d[bot_idx, 2]
                    arr[row]['XY2'] = d[bot_idx, 3]
                    arr[row]['DOMAIN_ID'] = did
                    row += 1
            rows_list.append(arr[:row])
            idx_list.append((did, pos, row))
            pos += row
    _save(h5, f'/NASTRAN/RESULT/ELEMENTAL/{category}/QUAD_CN',
          rows_list, idx_list)


# ═══════════════════════════════════════════════════════════════
#  1D element stress/strain yazici
# ═══════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════
#  Solid element stress/strain yazici
# ═══════════════════════════════════════════════════════════════

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
#  Eigenvalue summary yazici
# ═══════════════════════════════════════════════════════════════

def _write_eigenvalue_summary(h5, op2, dom, _log):
    """Modal analiz varsa /NASTRAN/RESULT/SUMMARY/EIGENVALUE yazar."""
    eig_dict = op2.eigenvectors
    if not eig_dict:
        return

    rows_list = []
    idx_list = []
    pos = 0

    for sc in sorted(eig_dict):
        res = eig_dict[sc]
        modes = getattr(res, 'modes', None)
        eigrs = getattr(res, 'eigrs', None)
        if modes is None or eigrs is None:
            continue

        n = len(modes)
        arr = np.zeros(n, dtype=EIGENVALUE_DTYPE)

        for i in range(n):
            did = dom.get_id(sc, i, res)
            eig = float(eigrs[i])
            omega = np.sqrt(abs(eig)) if eig >= 0 else -np.sqrt(abs(eig))
            freq = abs(omega) / (2.0 * np.pi)

            arr[i]['MODE'] = int(modes[i])
            arr[i]['ORDER'] = int(modes[i])
            arr[i]['EIGEN'] = eig
            arr[i]['OMEGA'] = omega
            arr[i]['FREQ'] = freq
            arr[i]['MASS'] = 0.0
            arr[i]['STIFF'] = 0.0
            arr[i]['DOMAIN_ID'] = did

        rows_list.append(arr)
        idx_list.append((1, pos, n))
        pos += n

    _save(h5, '/NASTRAN/RESULT/SUMMARY/EIGENVALUE', rows_list, idx_list)
    if rows_list:
        total = sum(len(a) for a in rows_list)
        _log(f'    SUMMARY/EIGENVALUE: {total} mod')


# ═══════════════════════════════════════════════════════════════
#  BEAM stress/force yazicilari
# ═══════════════════════════════════════════════════════════════

def _write_beam_stress(h5, path, result_dict, dom, dtype=BEAM_STRESS_DTYPE):
    """CBEAM stress/strain: her eleman icin birden fazla station."""
    rows_list, idx_list, pos = [], [], 0
    for sc in sorted(result_dict):
        res = result_dict[sc]
        en = res.element_node
        ntimes = res.data.shape[0]
        for it in range(ntimes):
            did = dom.get_id(sc, it, res)
            n = len(en)
            d = res.data[it]
            arr = np.zeros(n, dtype=dtype)
            arr['EID'] = en[:, 0]
            arr['NID'] = en[:, 1]
            ncols = d.shape[1]
            col_names = ['LONG', 'LS1', 'LS2', 'LS3', 'LS4', 'SMAX', 'SMIN']
            for ci, fname in enumerate(col_names):
                if ci < ncols:
                    arr[fname] = d[:, ci]
            arr['DOMAIN_ID'] = did
            rows_list.append(arr)
            idx_list.append((did, pos, n))
            pos += n
    _save(h5, path, rows_list, idx_list)


def _write_beam_force(h5, path, result_dict, dom):
    """CBEAM force: end-A ve end-B birlikte."""
    rows_list, idx_list, pos = [], [], 0
    for sc in sorted(result_dict):
        res = result_dict[sc]
        if hasattr(res, 'element_node') and res.element_node is not None:
            en = res.element_node
            ntimes = res.data.shape[0]
            npts_per_elem = 2  # End-A, End-B
            n_elem = len(en) // npts_per_elem
            for it in range(ntimes):
                did = dom.get_id(sc, it, res)
                d = res.data[it]
                arr = np.zeros(n_elem, dtype=BEAM_FORCE_DTYPE)
                for ie in range(n_elem):
                    ia = ie * npts_per_elem
                    ib = ia + 1
                    arr[ie]['EID'] = en[ia, 0]
                    arr[ie]['NIDA'] = en[ia, 1]
                    if d.shape[1] >= 6:
                        arr[ie]['BM1A'] = d[ia, 0]
                        arr[ie]['BM2A'] = d[ia, 1]
                        arr[ie]['TS1A'] = d[ia, 2]
                        arr[ie]['TS2A'] = d[ia, 3]
                        arr[ie]['AFA'] = d[ia, 4]
                        arr[ie]['TRQA'] = d[ia, 5]
                    arr[ie]['NIDB'] = en[ib, 1]
                    if d.shape[1] >= 6:
                        arr[ie]['BM1B'] = d[ib, 0]
                        arr[ie]['BM2B'] = d[ib, 1]
                        arr[ie]['TS1B'] = d[ib, 2]
                        arr[ie]['TS2B'] = d[ib, 3]
                        arr[ie]['AFB'] = d[ib, 4]
                        arr[ie]['TRQB'] = d[ib, 5]
                    arr[ie]['DOMAIN_ID'] = did
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

        # ── Root SCHEMA attribute (Patran bunu kontrol eder) ──
        h5.attrs['SCHEMA'] = MSC_SCHEMA_VERSION

        # ════════════════════════════════════════════════════
        #  INPUT bolumu - model geometrisi
        # ════════════════════════════════════════════════════
        _log('  INPUT bolumu yaziliyor...')
        _write_input_domains(h5)
        _write_input_grids(h5, op2, _log)
        _write_input_elements(h5, op2, _log)
        _write_input_properties(h5, op2, _log)
        _write_input_materials(h5, op2, _log)

        # ════════════════════════════════════════════════════
        #  RESULT bolumu - analiz sonuclari
        # ════════════════════════════════════════════════════
        _log('  RESULT bolumu yaziliyor...')

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

            # Plate
            for elem, attr in [('QUAD4', f'cquad4_{cl}'),
                                ('TRIA3', f'ctria3_{cl}')]:
                rdict = getattr(op2, attr, {})
                if rdict:
                    _log(f'    Elemental/{category}/{elem}: {len(rdict)} subcase')
                    _write_plate_stress(h5, elem, rdict, dom, category)

            # 1D
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

            # BEAM stress/strain
            beam_attr = f'cbeam_{cl}'
            beam_rdict = getattr(op2, beam_attr, {})
            if beam_rdict:
                _log(f'    Elemental/{category}/BEAM: {len(beam_rdict)} subcase')
                _write_beam_stress(h5, f'/NASTRAN/RESULT/ELEMENTAL/{category}/BEAM',
                                   beam_rdict, dom)

            # Solid
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

        # BEAM force
        beam_force_rdict = getattr(op2, 'cbeam_force', {})
        if beam_force_rdict:
            _log(f'    ElementForce/BEAM: {len(beam_force_rdict)} subcase')
            _write_beam_force(h5, '/NASTRAN/RESULT/ELEMENTAL/ELEMENT_FORCE/BEAM',
                              beam_force_rdict, dom)

        # Eigenvalue summary (modal analiz)
        _write_eigenvalue_summary(h5, op2, dom, _log)

        # RESULT DOMAINS tablosu
        domains_arr = dom.to_array()
        if len(domains_arr) > 0:
            _ds(h5, '/NASTRAN/RESULT/DOMAINS', domains_arr, 0)
        _log(f'    Toplam {len(dom._records)} domain yazildi')


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
                self.after(0, self._log, f"  Okunuyor: {op2_path}")
                op2_model = OP2()
                op2_model.read_op2(op2_path)
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
