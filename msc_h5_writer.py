"""
MSC Nastran Native HDF5 (NH5RDB) Writer
========================================
pyNastran OP2 verisini MSC Nastran'in native HDF5 formatina yazar.

Agac yapisi:
    /NASTRAN/RESULT/DOMAINS
    /NASTRAN/RESULT/NODAL/{DISPLACEMENT,EIGENVECTOR,...}
    /NASTRAN/RESULT/ELEMENTAL/STRESS/{QUAD4,BAR,HEXA,...}
    /NASTRAN/RESULT/ELEMENTAL/STRAIN/{QUAD4,BAR,...}
    /NASTRAN/RESULT/ELEMENTAL/ELEMENT_FORCE/{BAR,ROD,...}
    /INDEX/NASTRAN/RESULT/...
"""

import numpy as np
import h5py


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

# --- Nodal sonuclar ---
NODAL_DTYPE = np.dtype([
    ('ID', '<i8'), ('X', '<f8'), ('Y', '<f8'), ('Z', '<f8'),
    ('RX', '<f8'), ('RY', '<f8'), ('RZ', '<f8'), ('DOMAIN_ID', '<i8'),
])

# --- Plate stress/strain (center-only, flat) ---
PLATE_STRESS_DTYPE = np.dtype([
    ('EID', '<i8'),
    ('FD1', '<f8'), ('X1', '<f8'), ('Y1', '<f8'), ('XY1', '<f8'),
    ('FD2', '<f8'), ('X2', '<f8'), ('Y2', '<f8'), ('XY2', '<f8'),
    ('DOMAIN_ID', '<i8'),
])

# --- BAR stress/strain ---
BAR_STRESS_DTYPE = np.dtype([
    ('EID', '<i8'),
    ('X1A', '<f8'), ('X2A', '<f8'), ('X3A', '<f8'), ('X4A', '<f8'),
    ('AX', '<f8'), ('MAXA', '<f8'), ('MINA', '<f8'), ('MST', '<f8'),
    ('X1B', '<f8'), ('X2B', '<f8'), ('X3B', '<f8'), ('X4B', '<f8'),
    ('MAXB', '<f8'), ('MINB', '<f8'), ('MSC', '<f8'),
    ('DOMAIN_ID', '<i8'),
])

# --- ROD / CONROD stress/strain ---
ROD_STRESS_DTYPE = np.dtype([
    ('EID', '<i8'), ('A', '<f8'), ('MSA', '<f8'),
    ('T', '<f8'), ('MST', '<f8'), ('DOMAIN_ID', '<i8'),
])

# --- BUSH stress/strain ---
BUSH_STRESS_DTYPE = np.dtype([
    ('EID', '<i8'), ('TX', '<f8'), ('TY', '<f8'), ('TZ', '<f8'),
    ('RX', '<f8'), ('RY', '<f8'), ('RZ', '<f8'), ('DOMAIN_ID', '<i8'),
])

# --- Solid elementler (nested compound type) ---
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

# --- Element force dtype'lari ---
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

# --- QUAD4 force (flat, center-only) ---
QUAD4_FORCE_DTYPE = np.dtype([
    ('EID', '<i8'),
    ('MX', '<f8'), ('MY', '<f8'), ('MXY', '<f8'),
    ('BMX', '<f8'), ('BMY', '<f8'), ('BMXY', '<f8'),
    ('TX', '<f8'), ('TY', '<f8'),
    ('DOMAIN_ID', '<i8'),
])


# ═══════════════════════════════════════════════════════════════
#  Kolon eşleme tablolari  (alan_adi, pyNastran_kolon_indeksi)
# ═══════════════════════════════════════════════════════════════

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
    """Her (subcase, zaman_adimi) cifti icin benzersiz DOMAIN_ID atar."""

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
#  Yardimci: dataset + INDEX yaz
# ═══════════════════════════════════════════════════════════════

def _save(h5, path, data_list, index_list):
    """Verileri birlestir, dataset ve INDEX tablosu olustur."""
    if not data_list:
        return
    data = np.concatenate(data_list)
    h5.create_dataset(path, data=data)
    idx = np.array(index_list, dtype=INDEX_DTYPE)
    h5.create_dataset(f'/INDEX{path}', data=idx)


# ═══════════════════════════════════════════════════════════════
#  Nodal sonuc yazici
# ═══════════════════════════════════════════════════════════════

def _write_nodal(h5, name, result_dict, dom):
    rows_list = []
    idx_list = []
    pos = 0

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
            fields = ['X', 'Y', 'Z', 'RX', 'RY', 'RZ']
            for c in range(ncols):
                arr[fields[c]] = res.data[it, :, c]
            arr['DOMAIN_ID'] = did

            rows_list.append(arr)
            idx_list.append((did, pos, n))
            pos += n

    _save(h5, f'/NASTRAN/RESULT/NODAL/{name}', rows_list, idx_list)


# ═══════════════════════════════════════════════════════════════
#  Plate stress/strain yazici (QUAD4, TRIA3 center-only)
# ═══════════════════════════════════════════════════════════════

def _write_plate_stress(h5, msc_name, result_dict, dom, category):
    rows_list = []
    idx_list = []
    pos = 0

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
            top = d[top_i]
            bot = d[bot_i]

            arr = np.zeros(n_elem, dtype=PLATE_STRESS_DTYPE)
            arr['EID'] = eids
            arr['FD1'] = top[:, 0]
            arr['X1'] = top[:, 1]
            arr['Y1'] = top[:, 2]
            arr['XY1'] = top[:, 3]
            arr['FD2'] = bot[:, 0]
            arr['X2'] = bot[:, 1]
            arr['Y2'] = bot[:, 2]
            arr['XY2'] = bot[:, 3]
            arr['DOMAIN_ID'] = did

            rows_list.append(arr)
            idx_list.append((did, pos, n_elem))
            pos += n_elem

    _save(h5, f'/NASTRAN/RESULT/ELEMENTAL/{category}/{msc_name}',
          rows_list, idx_list)


# ═══════════════════════════════════════════════════════════════
#  1D element stress/strain yazici (BAR, ROD, BUSH, CONROD)
# ═══════════════════════════════════════════════════════════════

def _write_1d_result(h5, path, dtype, col_map, result_dict, dom):
    rows_list = []
    idx_list = []
    pos = 0

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
#  Solid element stress/strain yazici (HEXA, PENTA, TETRA)
# ═══════════════════════════════════════════════════════════════

def _write_solid_stress(h5, path, npts, dtype, result_dict, dom):
    rows_list = []
    idx_list = []
    pos = 0
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
#  Ana donusum fonksiyonu
# ═══════════════════════════════════════════════════════════════

def write_msc_h5(op2, h5_path, log=None):
    """
    pyNastran OP2 modelini MSC Nastran native HDF5 formatina yazar.

    Parameters
    ----------
    op2 : pyNastran.op2.op2.OP2
        Okunmus OP2 modeli.
    h5_path : str
        Cikti HDF5 dosya yolu.
    log : callable, optional
        Log fonksiyonu.
    """
    def _log(msg):
        if log:
            log(msg)

    dom = _Domains()

    with h5py.File(h5_path, 'w') as h5:

        # ── Nodal sonuclar ──
        nodal_map = [
            ('DISPLACEMENT', op2.displacements),
            ('EIGENVECTOR', op2.eigenvectors),
            ('SPC_FORCE', op2.spc_forces),
            ('MPC_FORCE', op2.mpc_forces),
            ('VELOCITY', op2.velocities),
            ('ACCELERATION', op2.accelerations),
            ('APPLIED_LOAD', op2.load_vectors),
        ]
        for name, rdict in nodal_map:
            if rdict:
                _log(f'    Nodal/{name}: {len(rdict)} subcase')
                _write_nodal(h5, name, rdict, dom)

        # ── Elemental stress & strain ──
        for category in ('STRESS', 'STRAIN'):
            cat_lower = category.lower()

            # Plate elementler
            for elem, attr in [('QUAD4', f'cquad4_{cat_lower}'),
                                ('TRIA3', f'ctria3_{cat_lower}')]:
                rdict = getattr(op2, attr, {})
                if rdict:
                    _log(f'    Elemental/{category}/{elem}: {len(rdict)} subcase')
                    _write_plate_stress(h5, elem, rdict, dom, category)

            # 1D elementler
            for elem, attr, dtype, cols in [
                ('BAR', f'cbar_{cat_lower}', BAR_STRESS_DTYPE, BAR_STRESS_COLS),
                ('ROD', f'crod_{cat_lower}', ROD_STRESS_DTYPE, ROD_STRESS_COLS),
                ('CONROD', f'conrod_{cat_lower}', ROD_STRESS_DTYPE, ROD_STRESS_COLS),
                ('BUSH', f'cbush_{cat_lower}', BUSH_STRESS_DTYPE, BUSH_STRESS_COLS),
            ]:
                rdict = getattr(op2, attr, {})
                if rdict:
                    _log(f'    Elemental/{category}/{elem}: {len(rdict)} subcase')
                    path = f'/NASTRAN/RESULT/ELEMENTAL/{category}/{elem}'
                    _write_1d_result(h5, path, dtype, cols, rdict, dom)

            # Solid elementler
            for elem, attr, npts, dtype in [
                ('HEXA', f'chexa_{cat_lower}', 9, HEXA_STRESS_DTYPE),
                ('PENTA', f'cpenta_{cat_lower}', 7, PENTA_STRESS_DTYPE),
                ('TETRA', f'ctetra_{cat_lower}', 5, TETRA_STRESS_DTYPE),
            ]:
                rdict = getattr(op2, attr, {})
                if rdict:
                    _log(f'    Elemental/{category}/{elem}: {len(rdict)} subcase')
                    path = f'/NASTRAN/RESULT/ELEMENTAL/{category}/{elem}'
                    _write_solid_stress(h5, path, npts, dtype, rdict, dom)

        # ── Element kuvvetleri ──
        for elem, attr, dtype, cols in [
            ('BAR', 'cbar_force', BAR_FORCE_DTYPE, BAR_FORCE_COLS),
            ('ROD', 'crod_force', ROD_FORCE_DTYPE, ROD_FORCE_COLS),
            ('BUSH', 'cbush_force', BUSH_FORCE_DTYPE, BUSH_FORCE_COLS),
            ('QUAD4', 'cquad4_force', QUAD4_FORCE_DTYPE, QUAD4_FORCE_COLS),
        ]:
            rdict = getattr(op2, attr, {})
            if rdict:
                _log(f'    ElementForce/{elem}: {len(rdict)} subcase')
                path = f'/NASTRAN/RESULT/ELEMENTAL/ELEMENT_FORCE/{elem}'
                _write_1d_result(h5, path, dtype, cols, rdict, dom)

        # ── DOMAINS tablosu ──
        domains_arr = dom.to_array()
        if len(domains_arr) > 0:
            h5.create_dataset('/NASTRAN/RESULT/DOMAINS', data=domains_arr)

        _log(f'    Toplam {len(dom._records)} domain yazildi')
