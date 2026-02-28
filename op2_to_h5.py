"""
OP2 to HDF5 Converter
=====================
MSC Nastran OP2 dosyalarini HDF5 (.h5) formatina donusturur.

Kullanim:
    python op2_to_h5.py              # GUI ile dosya/klasor secimi
    python op2_to_h5.py -i a.op2     # Tek dosya
    python op2_to_h5.py -i a.op2 b.op2 -o /cikti/klasoru
    python op2_to_h5.py -d /op2/klasoru -o /cikti/klasoru
"""

import argparse
import os
import sys
import glob
import traceback

from pyNastran.op2.op2_geom import OP2Geom
from msc_h5_writer import write_msc_h5


def select_op2_files_gui():
    """Tkinter ile OP2 dosyalarini sectirir."""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    files = filedialog.askopenfilenames(
        title="OP2 Dosyalarini Secin",
        filetypes=[("OP2 Dosyalari", "*.op2"), ("Tum Dosyalar", "*.*")],
    )
    root.destroy()

    if not files:
        print("Dosya secilmedi, cikiliyor.")
        sys.exit(0)

    return list(files)


def select_output_directory_gui():
    """Tkinter ile cikti klasorunu sectirir."""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    directory = filedialog.askdirectory(title="Cikti Klasorunu Secin")
    root.destroy()

    if not directory:
        print("Klasor secilmedi, cikiliyor.")
        sys.exit(0)

    return directory


def convert_op2_to_h5(op2_path, output_dir):
    """
    Tek bir OP2 dosyasini okuyup HDF5 formatina donusturur.

    Parameters
    ----------
    op2_path : str
        Giris OP2 dosyasinin yolu.
    output_dir : str
        Cikti HDF5 dosyasinin yazilacagi klasor.

    Returns
    -------
    str or None
        Basarili ise cikti dosya yolu, degilse None.
    """
    basename = os.path.splitext(os.path.basename(op2_path))[0]
    h5_path = os.path.join(output_dir, basename + ".h5")

    print(f"  Okunuyor : {op2_path}")

    try:
        op2_model = OP2Geom()
        op2_model.read_op2(op2_path)
    except Exception:
        print(f"  HATA: OP2 dosyasi okunamadi -> {op2_path}")
        traceback.print_exc()
        return None

    print(f"  Yaziliyor (MSC Nastran formati): {h5_path}")

    try:
        write_msc_h5(op2_model, h5_path, log=print)
    except Exception:
        print(f"  HATA: HDF5 dosyasi yazilamadi -> {h5_path}")
        traceback.print_exc()
        return None

    print(f"  Basarili : {h5_path}")
    return h5_path


def main():
    parser = argparse.ArgumentParser(
        description="MSC Nastran OP2 dosyalarini HDF5 (.h5) formatina donusturur."
    )
    parser.add_argument(
        "-i", "--input",
        nargs="*",
        help="Donusturulecek OP2 dosya yollari.",
    )
    parser.add_argument(
        "-d", "--directory",
        help="OP2 dosyalarinin bulundugu klasor (klasordeki tum .op2 dosyalari alinir).",
    )
    parser.add_argument(
        "-o", "--output",
        help="Cikti klasoru. Belirtilmezse GUI ile sorulur veya kaynak klasor kullanilir.",
    )

    args = parser.parse_args()

    # --- OP2 dosyalarini belirle ---
    op2_files = []

    if args.input:
        op2_files = args.input
    elif args.directory:
        pattern = os.path.join(args.directory, "*.op2")
        op2_files = sorted(glob.glob(pattern))
        if not op2_files:
            print(f"HATA: '{args.directory}' klasorunde .op2 dosyasi bulunamadi.")
            sys.exit(1)
    else:
        # GUI ile sec
        op2_files = select_op2_files_gui()

    # Dosya kontrolu
    missing = [f for f in op2_files if not os.path.isfile(f)]
    if missing:
        for m in missing:
            print(f"HATA: Dosya bulunamadi -> {m}")
        sys.exit(1)

    # --- Cikti klasorunu belirle ---
    if args.output:
        output_dir = args.output
    elif args.input or args.directory:
        # CLI modunda cikti belirtilmemisse kaynak ile ayni klasor
        output_dir = os.path.dirname(os.path.abspath(op2_files[0]))
    else:
        # GUI ile sec
        output_dir = select_output_directory_gui()

    os.makedirs(output_dir, exist_ok=True)

    # --- Donusum ---
    print(f"\n{'='*60}")
    print(f"  OP2 -> H5 Donusturucu")
    print(f"  Dosya sayisi : {len(op2_files)}")
    print(f"  Cikti klasoru: {output_dir}")
    print(f"{'='*60}\n")

    success = 0
    failed = 0

    for i, op2_path in enumerate(op2_files, 1):
        print(f"[{i}/{len(op2_files)}] {os.path.basename(op2_path)}")
        result = convert_op2_to_h5(op2_path, output_dir)
        if result:
            success += 1
        else:
            failed += 1
        print()

    # --- Ozet ---
    print(f"{'='*60}")
    print(f"  Toplam : {len(op2_files)}")
    print(f"  Basarili: {success}")
    print(f"  Basarisiz: {failed}")
    print(f"{'='*60}")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
