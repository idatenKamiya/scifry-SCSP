#!/usr/bin/env python3
"""
Fetch real lab protocols from protocols.io API to enhance training data.

Credentials can be set via:
1. Environment variables:
   export PROTOCOLS_IO_CLIENT_ID="your_client_id"
   export PROTOCOLS_IO_CLIENT_SECRET="your_client_secret"
   export PROTOCOLS_IO_ACCESS_TOKEN="your_access_token"

2. Or in .env.local file (auto-loaded):
   PROTOCOLS_IO_CLIENT_ID=...
   PROTOCOLS_IO_CLIENT_SECRET=...
   PROTOCOLS_IO_ACCESS_TOKEN=...

Run with: python3 data_fetcher.py
"""

import os
import json
import requests
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv(".env.local")  # Load from .env.local if it exists
except ImportError:
    pass  # python-dotenv not required

class ProtocolsIOFetcher:
    """Fetch PCR and DNA protocols from protocols.io API."""

    BASE_URL = "https://www.protocols.io/api/v3"

    def __init__(self):
        """Initialize with API credentials from environment variables."""
        self.access_token = os.getenv("PROTOCOLS_IO_ACCESS_TOKEN")
        self.client_id = os.getenv("PROTOCOLS_IO_CLIENT_ID")
        self.client_secret = os.getenv("PROTOCOLS_IO_CLIENT_SECRET")

        if not self.access_token and not (self.client_id and self.client_secret):
            raise ValueError(
                "Set PROTOCOLS_IO_ACCESS_TOKEN or both PROTOCOLS_IO_CLIENT_ID and PROTOCOLS_IO_CLIENT_SECRET"
            )

        self.headers = {"Authorization": f"Bearer {self.access_token}"}

    def search_protocols(self, query: str, limit: int = 10) -> list:
        """Search for protocols by keyword."""
        endpoint = f"{self.BASE_URL}/protocols"
        params = {
            "q": query,
            "limit": limit,
            "key_word": query,
            "sort": "relevance"
        }

        try:
            resp = requests.get(endpoint, params=params, headers=self.headers, timeout=10)
            resp.raise_for_status()
            return resp.json().get("items", [])
        except Exception as e:
            print(f"✗ Error searching protocols: {e}")
            return []

    def get_protocol_details(self, protocol_id: int) -> Optional[dict]:
        """Fetch full protocol details including steps."""
        endpoint = f"{self.BASE_URL}/protocols/{protocol_id}"

        try:
            resp = requests.get(endpoint, headers=self.headers, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"✗ Error fetching protocol {protocol_id}: {e}")
            return None

    def extract_protocol_text(self, protocol_data: dict) -> str:
        """Extract human-readable protocol text from API response."""
        title = protocol_data.get("title", "Unknown Protocol")
        abstract = protocol_data.get("abstract", "")

        # Extract steps
        steps = []
        for step in protocol_data.get("steps", []):
            step_text = step.get("description", "")
            if step_text:
                steps.append(step_text)

        protocol_text = f"# {title}\n\n"
        if abstract:
            protocol_text += f"## Overview\n{abstract}\n\n"

        protocol_text += "## Protocol Steps\n"
        for i, step in enumerate(steps, 1):
            protocol_text += f"{i}. {step}\n"

        return protocol_text

    def download_pcr_protocols(self, num_protocols: int = 5, output_dir: str = "data/protocols_io_raw") -> int:
        """Download PCR protocols and save as text files."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        print(f"Searching for PCR protocols...")
        protocols = self.search_protocols("PCR polymerase chain reaction", limit=num_protocols * 2)

        if not protocols:
            print("✗ No protocols found. Check credentials and API access.")
            return 0

        saved_count = 0
        for i, proto in enumerate(protocols[:num_protocols]):
            protocol_id = proto.get("id")
            title = proto.get("title", f"protocol_{i}")

            print(f"  Fetching: {title}...", end=" ")

            details = self.get_protocol_details(protocol_id)
            if not details:
                print("✗")
                continue

            text = self.extract_protocol_text(details)
            filename = f"{output_dir}/pcr_protocol_{i:02d}_{protocol_id}.txt"

            try:
                with open(filename, "w") as f:
                    f.write(text)
                print(f"✓ ({len(text)} chars)")
                saved_count += 1
            except Exception as e:
                print(f"✗ ({e})")

        return saved_count


def fetch_opentrons_examples(output_dir: str = "data/expert_scripts") -> int:
    """Download example Opentrons scripts from GitHub."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # List of well-maintained Opentrons protocol examples
    examples = [
        {
            "name": "pcr_setup.py",
            "url": "https://raw.githubusercontent.com/Opentrons/ot2-sample-data/main/protocols/PCR_Setup_Illumina.py",
            "description": "Illumina PCR setup"
        },
        {
            "name": "dna_extraction.py",
            "url": "https://raw.githubusercontent.com/Opentrons/ot2-sample-data/main/protocols/DNA_Extraction.py",
            "description": "DNA extraction protocol"
        },
        {
            "name": "plate_filling.py",
            "url": "https://raw.githubusercontent.com/Opentrons/ot2-sample-data/main/protocols/Plate_Filling.py",
            "description": "Plate filling with mixing"
        }
    ]

    saved_count = 0
    for example in examples:
        print(f"  Downloading: {example['name']} ({example['description']})...", end=" ")
        try:
            resp = requests.get(example["url"], timeout=10)
            resp.raise_for_status()

            filepath = f"{output_dir}/opentrons_{example['name']}"
            with open(filepath, "w") as f:
                f.write(resp.text)
            print(f"✓")
            saved_count += 1
        except Exception as e:
            print(f"✗ ({e})")

    return saved_count


def main():
    """Fetch protocols and examples."""
    print("=" * 70)
    print("PROTOCOLIR DATA FETCHER")
    print("=" * 70)

    # Check credentials
    access_token = os.getenv("PROTOCOLS_IO_ACCESS_TOKEN")
    client_id = os.getenv("PROTOCOLS_IO_CLIENT_ID")

    if not access_token and not client_id:
        print("\n✗ Missing credentials. Set environment variables:")
        print("  export PROTOCOLS_IO_ACCESS_TOKEN='your_token'")
        print("  OR")
        print("  export PROTOCOLS_IO_CLIENT_ID='your_id'")
        print("  export PROTOCOLS_IO_CLIENT_SECRET='your_secret'")
        return

    # Fetch from protocols.io
    print("\n📥 Fetching PCR protocols from protocols.io...")
    try:
        fetcher = ProtocolsIOFetcher()
        pcr_count = fetcher.download_pcr_protocols(num_protocols=5)
        print(f"✓ Downloaded {pcr_count} PCR protocols")
    except Exception as e:
        print(f"✗ Error: {e}")

    # Fetch Opentrons examples
    print("\n📥 Downloading Opentrons example scripts...")
    ot_count = fetch_opentrons_examples()
    print(f"✓ Downloaded {ot_count} Opentrons examples")

    print("\n" + "=" * 70)
    print("✓ Data collection complete!")
    print(f"  PCR protocols: data/protocols_io_raw/")
    print(f"  Expert scripts: data/expert_scripts/")
    print("\nNext: Use expanded data to train improved reward model")
    print("=" * 70)


if __name__ == "__main__":
    main()
