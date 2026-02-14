"""
Örnek H5 dosyası oluşturucu
Sizin örnekteki gibi bir yapı oluşturur:
- ExtSimEv/Data_PMT
- ExtSimEv/Data_SPTR
- AnaEv/VolInfo
- AnaEv/DummyParts
"""

import h5py
import numpy as np


def create_sample_h5(filename: str = "ornek_dosya.h5"):
    """
    Örnek H5 dosyası oluştur

    Args:
        filename: Oluşturulacak dosya adı
    """
    print(f"Örnek H5 dosyası oluşturuluyor: {filename}")

    with h5py.File(filename, 'w') as f:
        # ExtSimEv grubu
        ext_sim_group = f.create_group("ExtSimEv")
        ext_sim_group.attrs['description'] = 'External Simulation Events'
        ext_sim_group.attrs['version'] = '1.0'

        # ExtSimEv/Data_PMT dataset
        pmt_data = np.random.randn(1000, 10)  # 1000 events, 10 PMT channels
        ext_sim_group.create_dataset("Data_PMT", data=pmt_data)
        ext_sim_group["Data_PMT"].attrs['unit'] = 'photoelectrons'
        ext_sim_group["Data_PMT"].attrs['channels'] = 10

        # ExtSimEv/Data_SPTR dataset
        sptr_data = np.random.randn(1000, 5)  # 1000 events, 5 SPTR channels
        ext_sim_group.create_dataset("Data_SPTR", data=sptr_data)
        ext_sim_group["Data_SPTR"].attrs['unit'] = 'arbitrary'
        ext_sim_group["Data_SPTR"].attrs['channels'] = 5

        # AnaEv grubu
        ana_ev_group = f.create_group("AnaEv")
        ana_ev_group.attrs['description'] = 'Analysis Events'
        ana_ev_group.attrs['version'] = '2.0'

        # AnaEv/VolInfo dataset
        vol_info = np.random.randn(500, 3)  # 500 events, 3D position
        ana_ev_group.create_dataset("VolInfo", data=vol_info)
        ana_ev_group["VolInfo"].attrs['unit'] = 'mm'
        ana_ev_group["VolInfo"].attrs['coordinates'] = 'x,y,z'

        # AnaEv/DummyParts dataset
        dummy_parts = np.random.randint(0, 100, size=(500, 20))
        ana_ev_group.create_dataset("DummyParts", data=dummy_parts)
        ana_ev_group["DummyParts"].attrs['description'] = 'Particle IDs'

        # İlave bir grup ve alt grup ekle
        processing_group = f.create_group("Processing")
        processing_group.attrs['description'] = 'Data Processing Results'

        # Processing/Filtered alt grubu
        filtered_group = processing_group.create_group("Filtered")
        filtered_data = np.random.randn(800, 10)
        filtered_group.create_dataset("FilteredPMT", data=filtered_data)
        filtered_group["FilteredPMT"].attrs['filter'] = 'threshold > 0.5'

        # Processing/Calibrated
        calibrated_data = np.random.randn(800, 10) * 1.5 + 0.1
        processing_group.create_dataset("CalibratedData", data=calibrated_data)
        processing_group["CalibratedData"].attrs['calibration'] = 'linear'

        # Metadata grubu
        metadata_group = f.create_group("Metadata")
        metadata_group.attrs['experiment'] = 'Sample Experiment'
        metadata_group.attrs['date'] = '2025-01-15'
        metadata_group.attrs['detector'] = 'PMT Array v2.0'

        # Basit bir scalar dataset
        metadata_group.create_dataset("RunNumber", data=12345)
        metadata_group.create_dataset("TotalEvents", data=1000)
        metadata_group.create_dataset("ProcessedEvents", data=800)

    print(f"✅ Örnek H5 dosyası başarıyla oluşturuldu: {filename}")
    print(f"\nDosya yapısı:")
    print("  ├── ExtSimEv/")
    print("  │   ├── Data_PMT [1000, 10]")
    print("  │   └── Data_SPTR [1000, 5]")
    print("  ├── AnaEv/")
    print("  │   ├── VolInfo [500, 3]")
    print("  │   └── DummyParts [500, 20]")
    print("  ├── Processing/")
    print("  │   ├── Filtered/")
    print("  │   │   └── FilteredPMT [800, 10]")
    print("  │   └── CalibratedData [800, 10]")
    print("  └── Metadata/")
    print("      ├── RunNumber")
    print("      ├── TotalEvents")
    print("      └── ProcessedEvents")
    print(f"\nŞimdi analiz etmek için:")
    print(f"  python h5_branch_analyzer.py {filename} all")
    print(f"veya")
    print(f"  python example_usage.py {filename}")


if __name__ == "__main__":
    import sys

    filename = sys.argv[1] if len(sys.argv) > 1 else "ornek_dosya.h5"
    create_sample_h5(filename)
