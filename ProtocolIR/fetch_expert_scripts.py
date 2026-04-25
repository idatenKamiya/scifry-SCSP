#!/usr/bin/env python3
"""
Download real Opentrons expert scripts from GitHub repositories.
These are production-quality scripts from COVID-19 protocols, SoundAg, and other communities.
"""

import os
import requests

EXPERT_SCRIPTS = {
    # Opentrons COVID-19 Official Protocols
    "opentrons_covid19_station-C-qpcr-map.py": "https://raw.githubusercontent.com/Opentrons/covid19/master/protocols/station-C-qpcr-map.py",
    "opentrons_covid19_V15-StationB-8samples.py": "https://raw.githubusercontent.com/Opentrons/covid19/master/protocols/V15-StationB-8samples.py",
    "opentrons_covid19_V5_3-20_spike-StationA-8samples.py": "https://raw.githubusercontent.com/Opentrons/covid19/master/protocols/V5_3-20_spike-StationA-8samples.py",

    # SoundAg 384-well qPCR Protocol
    "soundag_multidispense_384w_qPCR_setup_v2.py": "https://raw.githubusercontent.com/SoundAg/automation-OT2/main/multidispense_384w_qPCR_setup_v2.py",

    # Liam Hawkins qPCR Quantification
    "liamhawkins_3_plate_qPCR_quantification_protocol.py": "https://raw.githubusercontent.com/liamhawkins/opentrons_protocols/master/3_plate_qPCR_quantification_protocol.py",

    # Aldatu RNA Protocols
    "aldatu_Pretoria_RNA_Dil_ReportableRange.py": "https://raw.githubusercontent.com/aldatubio/opentrons/main/protocols/Pretoria/Pretoria_RNA_Dil_ReportableRange.py",
    "aldatu_Pretoria_RNA_Aliquots_ReportableRange.py": "https://raw.githubusercontent.com/aldatubio/opentrons/main/protocols/Pretoria/Pretoria_RNA_Aliquots_ReportableRange.py",
}

def setup_directories():
    target_dir = "data/expert_scripts"
    os.makedirs(target_dir, exist_ok=True)
    print(f"✓ Created: {target_dir}")
    return target_dir

def download_expert_scripts():
    target_dir = setup_directories()

    print(f"\n📥 Downloading {len(EXPERT_SCRIPTS)} expert Opentrons scripts...")

    success_count = 0
    for i, (filename, url) in enumerate(EXPERT_SCRIPTS.items(), 1):
        print(f"  [{i}/{len(EXPERT_SCRIPTS)}] {filename[:50]}...", end=" ")

        try:
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                with open(os.path.join(target_dir, filename), 'w', encoding='utf-8') as f:
                    f.write(response.text)
                print("✓")
                success_count += 1
            else:
                print(f"✗ (HTTP {response.status_code})")

        except Exception as e:
            print(f"✗ ({str(e)[:30]})")

    return success_count

if __name__ == "__main__":
    print("=" * 70)
    print("FETCH EXPERT OPENTRONS SCRIPTS")
    print("=" * 70)

    count = download_expert_scripts()

    print("\n" + "=" * 70)
    print(f"✓ Downloaded {count}/{len(EXPERT_SCRIPTS)} expert scripts")
    print(f"  Saved to: data/expert_scripts/")
    print("=" * 70)
