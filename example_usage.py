"""
H5 Branch Analyzer - Örnek Kullanım
"""

from h5_branch_analyzer import (
    list_all_branches,
    list_branches_detailed,
    print_branch_tree,
    print_statistics,
    find_datasets_by_pattern
)


def demo_all_features(h5_file_path: str):
    """
    Tüm özellikleri demo et

    Args:
        h5_file_path: H5 dosyasının yolu
    """
    print("\n" + "="*70)
    print("H5 BRANCH ANALYZER - TÜM ÖZELLİKLER DEMOsu")
    print("="*70)

    # 1. Basit liste
    print("\n\n1️⃣  BASİT BRANCH LİSTESİ")
    print("-" * 70)
    list_all_branches(h5_file_path)

    # 2. Detaylı liste
    print("\n\n2️⃣  DETAYLI BRANCH LİSTESİ")
    print("-" * 70)
    list_branches_detailed(h5_file_path)

    # 3. Tree yapısı
    print("\n\n3️⃣  AĞAÇ YAPISI")
    print("-" * 70)
    print_branch_tree(h5_file_path)

    # 4. İstatistikler
    print("\n\n4️⃣  İSTATİSTİKLER")
    print("-" * 70)
    print_statistics(h5_file_path)

    # 5. Pattern arama
    print("\n\n5️⃣  PATTERN ARAMA (örnek: 'PMT')")
    print("-" * 70)
    pmt_datasets = find_datasets_by_pattern(h5_file_path, "PMT")
    if pmt_datasets:
        print("PMT içeren dataset'ler:")
        for ds in pmt_datasets:
            print(f"  - {ds}")
    else:
        print("PMT içeren dataset bulunamadı")

    # 6. Pattern arama - Data
    print("\n\n6️⃣  PATTERN ARAMA (örnek: 'Data')")
    print("-" * 70)
    data_datasets = find_datasets_by_pattern(h5_file_path, "Data")
    if data_datasets:
        print("'Data' içeren dataset'ler:")
        for ds in data_datasets:
            print(f"  - {ds}")
    else:
        print("'Data' içeren dataset bulunamadı")

    print("\n" + "="*70)
    print("DEMO TAMAMLANDI")
    print("="*70 + "\n")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Kullanım: python example_usage.py <h5_file_path>")
        print("\nÖrnek:")
        print("  python example_usage.py ornek_dosya.h5")
        sys.exit(1)

    h5_file = sys.argv[1]

    try:
        demo_all_features(h5_file)
    except FileNotFoundError:
        print(f"❌ Hata: '{h5_file}' dosyası bulunamadı!")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Hata: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
