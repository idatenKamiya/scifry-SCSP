#!/usr/bin/env python3
"""
Download real PCR/qPCR protocols from protocols.io API v4
Uses actual protocol URIs from the PCR/qPCR domain
"""

import os
import requests
import json

# Use the client access token
PROTOCOLS_TOKEN = "<REDACTED_PROTOCOLS_IO_ACCESS_TOKEN>"
HEADERS = {"Authorization": f"Bearer {PROTOCOLS_TOKEN}"}

# The specific URIs for PCR/qPCR protocols
URIS = [
    "opentrons-pipeline-pcr-preparation-rm7vzx6y8gx1",
    "ot-2-pcr-sample-preparation-protocol-n92ldpyznl5b",
    "bsci-414-lab-4-plate-setup-for-covid-rt-qpcr-5qpvoyn49g4o",
    "qpcr-power-sybr-green-protocol-8epv5rxw6g1b",
    "qpcr-sybr-green-bp2l6zjwrgqe",
    "10.17504/protocols.io.yxmvm341bl3p/v1",
    "standard-operating-procedure-for-real-time-pcr-rea-pnqdmdw",
    "pcr-protocol-for-taqman-reg-genotyping-assays-sfzebp6",
    "kompetitive-allele-specific-pcr-kasp-with-biorad-s-ckqduvs6",
    "aav-titration-by-qpcr-using-sybr-green-technology-bawrifd6",
    "PCR-HSP60-96-well-plate-36wgqjoxvk57",
    "automated-96-well-pcr-purification-dm6gpr19jvzp",
    "pcr-master-mix-aliquoting-bp2l641mdvqe",
    "preparing-1x-pcr-master-mix-14egn737zv5d"
]

def setup_directories():
    dirs = [
        "data/protocols_io_raw/json",
        "data/protocols_io_raw/steps"
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        print(f"✓ Created: {d}")

def download_protocols():
    setup_directories()

    print(f"\n📥 Downloading {len(URIS)} protocols from protocols.io...")

    success_count = 0
    for i, uri in enumerate(URIS, 1):
        safe_name = uri.replace('/', '_').replace(':', '_')
        print(f"  [{i}/{len(URIS)}] {safe_name[:50]}...", end=" ")

        try:
            # 1. Fetch full protocol metadata & content
            meta_url = f"https://www.protocols.io/api/v4/protocols/{uri}?last_version=1&content_format=markdown"
            meta_res = requests.get(meta_url, headers=HEADERS, timeout=10)

            if meta_res.status_code == 200:
                with open(f"data/protocols_io_raw/json/{safe_name}.json", 'w') as f:
                    json.dump(meta_res.json(), f, indent=2)

                # 2. Fetch specific steps
                steps_url = f"https://www.protocols.io/api/v4/protocols/{uri}/steps?last_version=1&content_format=markdown"
                steps_res = requests.get(steps_url, headers=HEADERS, timeout=10)

                if steps_res.status_code == 200:
                    with open(f"data/protocols_io_raw/steps/{safe_name}.steps.json", 'w') as f:
                        json.dump(steps_res.json(), f, indent=2)
                    print("✓")
                    success_count += 1
                else:
                    print(f"✗ (steps: {steps_res.status_code})")
            else:
                print(f"✗ (meta: {meta_res.status_code})")

        except Exception as e:
            print(f"✗ ({str(e)[:30]})")

    return success_count

if __name__ == "__main__":
    print("=" * 70)
    print("FETCH PROTOCOLS.IO REAL PROTOCOLS")
    print("=" * 70)

    count = download_protocols()

    print("\n" + "=" * 70)
    print(f"✓ Downloaded {count}/{len(URIS)} protocols")
    print(f"  Saved to: data/protocols_io_raw/json/ and steps/")
    print("=" * 70)
