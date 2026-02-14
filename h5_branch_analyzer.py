"""
H5 Dosya Branch Analyzer
H5 dosyalarının tüm dallarını (groups ve datasets) analiz eder.
"""

import h5py
import numpy as np
from typing import Optional, Dict, List


def list_all_branches(h5_file_path: str) -> None:
    """
    H5 dosyasındaki tüm branch'leri (grup ve dataset'leri) listele

    Args:
        h5_file_path: H5 dosyasının yolu
    """
    def recursive_list(name, obj):
        if isinstance(obj, h5py.Group):
            print(f"Group: {name}")
        elif isinstance(obj, h5py.Dataset):
            print(f"Dataset: {name}")

    with h5py.File(h5_file_path, 'r') as f:
        f.visititems(recursive_list)


def list_branches_detailed(h5_file_path: str) -> None:
    """
    H5 dosyasındaki tüm branch'leri detaylı şekilde listele
    (boyut, tip, attribute bilgileri ile birlikte)

    Args:
        h5_file_path: H5 dosyasının yolu
    """
    def recursive_list(name, obj):
        if isinstance(obj, h5py.Group):
            attrs = dict(obj.attrs) if len(obj.attrs) > 0 else {}
            print(f"📁 Group: {name}")
            if attrs:
                print(f"   Attributes: {attrs}")
        elif isinstance(obj, h5py.Dataset):
            print(f"📊 Dataset: {name}")
            print(f"   Shape: {obj.shape}")
            print(f"   Dtype: {obj.dtype}")
            print(f"   Size: {obj.size} elements")
            attrs = dict(obj.attrs) if len(obj.attrs) > 0 else {}
            if attrs:
                print(f"   Attributes: {attrs}")

    with h5py.File(h5_file_path, 'r') as f:
        print(f"\n{'='*60}")
        print(f"H5 File Analysis: {h5_file_path}")
        print(f"{'='*60}\n")
        f.visititems(recursive_list)


def get_branch_tree(h5_file_path: str) -> Dict:
    """
    H5 dosyasının hierarchical tree yapısını dictionary olarak döndür

    Args:
        h5_file_path: H5 dosyasının yolu

    Returns:
        Dict: Hierarchical tree yapısı
    """
    tree = {}

    def build_tree(name, obj):
        parts = name.split('/')
        current = tree

        for i, part in enumerate(parts):
            if part not in current:
                current[part] = {}

            if i == len(parts) - 1:
                if isinstance(obj, h5py.Dataset):
                    current[part] = {
                        '_type': 'dataset',
                        '_shape': obj.shape,
                        '_dtype': str(obj.dtype),
                        '_size': obj.size
                    }
                elif isinstance(obj, h5py.Group):
                    if '_type' not in current[part]:
                        current[part]['_type'] = 'group'
            else:
                current = current[part]

    with h5py.File(h5_file_path, 'r') as f:
        f.visititems(build_tree)

    return tree


def print_branch_tree(h5_file_path: str, max_depth: Optional[int] = None) -> None:
    """
    H5 dosyasının tree yapısını güzel formatta yazdır

    Args:
        h5_file_path: H5 dosyasının yolu
        max_depth: Maksimum derinlik (None = sınırsız)
    """
    def print_tree(node, prefix="", depth=0):
        if max_depth is not None and depth >= max_depth:
            return

        for i, (key, value) in enumerate(node.items()):
            is_last = i == len(node) - 1
            current_prefix = "└── " if is_last else "├── "
            next_prefix = "    " if is_last else "│   "

            if isinstance(value, dict) and '_type' in value:
                if value['_type'] == 'dataset':
                    print(f"{prefix}{current_prefix}📊 {key} "
                          f"[{value.get('_shape', 'N/A')}] ({value.get('_dtype', 'N/A')})")
                elif value['_type'] == 'group':
                    print(f"{prefix}{current_prefix}📁 {key}/")
                    # Print children
                    children = {k: v for k, v in value.items() if not k.startswith('_')}
                    if children:
                        print_tree(children, prefix + next_prefix, depth + 1)
            elif isinstance(value, dict):
                print(f"{prefix}{current_prefix}📁 {key}/")
                print_tree(value, prefix + next_prefix, depth + 1)

    tree = get_branch_tree(h5_file_path)
    print(f"\n{'='*60}")
    print(f"H5 File Tree: {h5_file_path}")
    print(f"{'='*60}\n")
    print_tree(tree)
    print()


def get_branch_statistics(h5_file_path: str) -> Dict[str, int]:
    """
    H5 dosyasının istatistiklerini döndür

    Args:
        h5_file_path: H5 dosyasının yolu

    Returns:
        Dict: İstatistikler (group sayısı, dataset sayısı, vs.)
    """
    stats = {
        'total_groups': 0,
        'total_datasets': 0,
        'total_elements': 0,
        'max_depth': 0
    }

    def count_items(name, obj):
        depth = len(name.split('/'))
        stats['max_depth'] = max(stats['max_depth'], depth)

        if isinstance(obj, h5py.Group):
            stats['total_groups'] += 1
        elif isinstance(obj, h5py.Dataset):
            stats['total_datasets'] += 1
            stats['total_elements'] += obj.size

    with h5py.File(h5_file_path, 'r') as f:
        f.visititems(count_items)

    return stats


def print_statistics(h5_file_path: str) -> None:
    """
    H5 dosyasının istatistiklerini yazdır

    Args:
        h5_file_path: H5 dosyasının yolu
    """
    stats = get_branch_statistics(h5_file_path)

    print(f"\n{'='*60}")
    print(f"H5 File Statistics: {h5_file_path}")
    print(f"{'='*60}")
    print(f"Total Groups:   {stats['total_groups']}")
    print(f"Total Datasets: {stats['total_datasets']}")
    print(f"Total Elements: {stats['total_elements']:,}")
    print(f"Max Depth:      {stats['max_depth']}")
    print(f"{'='*60}\n")


def find_datasets_by_pattern(h5_file_path: str, pattern: str) -> List[str]:
    """
    Belirli bir pattern'e uyan dataset'leri bul

    Args:
        h5_file_path: H5 dosyasının yolu
        pattern: Aranacak pattern (örn: "PMT", "Data")

    Returns:
        List[str]: Bulunan dataset yolları
    """
    found = []

    def search(name, obj):
        if isinstance(obj, h5py.Dataset) and pattern.lower() in name.lower():
            found.append(name)

    with h5py.File(h5_file_path, 'r') as f:
        f.visititems(search)

    return found


if __name__ == "__main__":
    # Örnek kullanım
    import sys

    if len(sys.argv) < 2:
        print("Kullanım: python h5_branch_analyzer.py <h5_file_path> [mode]")
        print("Modlar:")
        print("  simple   - Basit liste (default)")
        print("  detailed - Detaylı bilgiler")
        print("  tree     - Ağaç yapısı")
        print("  stats    - İstatistikler")
        print("  all      - Hepsi")
        sys.exit(1)

    h5_file = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "simple"

    try:
        if mode == "simple":
            print("\n=== Simple Branch List ===\n")
            list_all_branches(h5_file)
        elif mode == "detailed":
            list_branches_detailed(h5_file)
        elif mode == "tree":
            print_branch_tree(h5_file)
        elif mode == "stats":
            print_statistics(h5_file)
        elif mode == "all":
            list_branches_detailed(h5_file)
            print_branch_tree(h5_file)
            print_statistics(h5_file)
        else:
            print(f"Bilinmeyen mod: {mode}")
            sys.exit(1)
    except Exception as e:
        print(f"Hata: {e}")
        sys.exit(1)
