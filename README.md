# Load-Ext

H5 (HDF5) dosyalarının branch yapısını analiz eden Python aracı.

## 🎯 Özellikler

- ✅ **Basit Branch Listeleme**: Tüm grup ve dataset'leri listele
- ✅ **Detaylı Analiz**: Boyut, tip ve attribute bilgileri
- ✅ **Tree Görünümü**: Hierarchical ağaç yapısı
- ✅ **İstatistikler**: Toplam grup/dataset sayısı, derinlik
- ✅ **Pattern Arama**: İsme göre dataset bulma

## 📦 Kurulum

```bash
pip install -r requirements.txt
```

## 🚀 Kullanım

### 1. Örnek H5 Dosyası Oluştur

```bash
python create_sample_h5.py
```

Bu komut `ornek_dosya.h5` adında örnek bir dosya oluşturur.

### 2. Basit Analiz

```bash
# Basit liste
python h5_branch_analyzer.py ornek_dosya.h5 simple

# Detaylı bilgiler
python h5_branch_analyzer.py ornek_dosya.h5 detailed

# Tree yapısı
python h5_branch_analyzer.py ornek_dosya.h5 tree

# İstatistikler
python h5_branch_analyzer.py ornek_dosya.h5 stats

# Hepsi
python h5_branch_analyzer.py ornek_dosya.h5 all
```

### 3. Python Kodunda Kullanım

```python
from h5_branch_analyzer import (
    list_all_branches,
    list_branches_detailed,
    print_branch_tree,
    print_statistics,
    find_datasets_by_pattern
)

# Basit liste
list_all_branches("dosya.h5")

# Detaylı analiz
list_branches_detailed("dosya.h5")

# Tree görünümü
print_branch_tree("dosya.h5")

# İstatistikler
print_statistics("dosya.h5")

# PMT içeren dataset'leri bul
pmt_datasets = find_datasets_by_pattern("dosya.h5", "PMT")
print(pmt_datasets)
```

### 4. Demo (Tüm Özellikler)

```bash
python example_usage.py ornek_dosya.h5
```

## 📋 Örnek Çıktı

### Tree Görünümü
```
============================================================
H5 File Tree: ornek_dosya.h5
============================================================

├── 📁 ExtSimEv/
│   ├── 📊 Data_PMT [(1000, 10)] (float64)
│   └── 📊 Data_SPTR [(1000, 5)] (float64)
├── 📁 AnaEv/
│   ├── 📊 VolInfo [(500, 3)] (float64)
│   └── 📊 DummyParts [(500, 20)] (int64)
├── 📁 Processing/
│   ├── 📁 Filtered/
│   │   └── 📊 FilteredPMT [(800, 10)] (float64)
│   └── 📊 CalibratedData [(800, 10)] (float64)
└── 📁 Metadata/
    ├── 📊 RunNumber [()] (int64)
    ├── 📊 TotalEvents [()] (int64)
    └── 📊 ProcessedEvents [()] (int64)
```

### İstatistikler
```
============================================================
H5 File Statistics: ornek_dosya.h5
============================================================
Total Groups:   5
Total Datasets: 8
Total Elements: 38,503
Max Depth:      2
============================================================
```

## 🔍 Kod Açıklaması

### Orijinal Kod (Temel)

```python
def list_all_branches(h5_file_path):
    """H5 dosyasındaki tüm branch'leri listele"""
    def recursive_list(name, obj):
        if isinstance(obj, h5py.Group):
            print(f"Group: {name}")
        elif isinstance(obj, h5py.Dataset):
            print(f"Dataset: {name}")

    with h5py.File(h5_file_path, 'r') as f:
        f.visititems(recursive_list)
```

Bu temel kod:
- ✅ `h5py.File.visititems()` kullanarak recursive tarama yapar
- ✅ Her grup ve dataset'i ziyaret eder
- ✅ `h5py.Group` ve `h5py.Dataset` tiplerini kontrol eder

### Geliştirilen Özellikler

1. **Detaylı Bilgiler**: Shape, dtype, size, attributes
2. **Tree Yapısı**: Hierarchical görünüm
3. **İstatistikler**: Toplam sayılar ve derinlik
4. **Pattern Arama**: İsme göre filtreleme

## 📚 H5 Dosya Yapısı

HDF5 dosyaları hierarchical veri formatıdır:

- **Groups** (📁): Klasörler gibi, diğer grup ve dataset'leri içerebilir
- **Datasets** (📊): Gerçek veriyi içerir (numpy array benzeri)
- **Attributes**: Metadata bilgileri (her grup/dataset'e eklenebilir)

## 🤝 Katkıda Bulunma

Pull request'ler memnuniyetle karşılanır!

## 📝 Lisans

MIT