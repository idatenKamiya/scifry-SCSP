#!/usr/bin/env python3
"""Fetch a larger reproducible Opentrons protocol corpus from GitHub."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, List


API_ROOT = "https://api.github.com"
RAW_ROOT = "https://raw.githubusercontent.com"
DEFAULT_REPO = "Opentrons/Protocols"
DEFAULT_REF = "develop"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch large Opentrons protocol corpus.")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub owner/repo.")
    parser.add_argument("--ref", default=DEFAULT_REF, help="Git ref/branch to fetch.")
    parser.add_argument("--limit", type=int, default=250, help="Maximum protocol scripts to download.")
    parser.add_argument("--output", default="data/expert_scripts_large", help="Output directory for scripts.")
    parser.add_argument("--readme-output", default="data/protocols_io_raw/opentrons_library", help="Output directory for README text.")
    args = parser.parse_args()

    output = Path(args.output)
    readme_output = Path(args.readme_output)
    output.mkdir(parents=True, exist_ok=True)
    readme_output.mkdir(parents=True, exist_ok=True)

    tree = _github_json(f"{API_ROOT}/repos/{args.repo}/git/trees/{args.ref}?recursive=1")
    items = tree.get("tree", [])
    scripts = _select_protocol_scripts(items, args.limit)
    readmes = _select_readmes(items, {str(Path(path).parent).replace('\\', '/') for path in scripts})

    manifest = {
        "repo": args.repo,
        "ref": args.ref,
        "script_count": len(scripts),
        "readme_count": len(readmes),
        "scripts": scripts,
        "readmes": readmes,
    }

    print(f"Downloading {len(scripts)} Opentrons protocol scripts from {args.repo}@{args.ref}")
    downloaded_scripts = 0
    for path in scripts:
        text = _download_raw(args.repo, args.ref, path)
        if _looks_like_opentrons_protocol(text):
            target = output / _safe_name(path)
            target.write_text(text, encoding="utf-8")
            downloaded_scripts += 1

    print(f"Downloading {len(readmes)} protocol README files")
    downloaded_readmes = 0
    for path in readmes:
        text = _download_raw(args.repo, args.ref, path)
        if len(text.strip()) > 50:
            target = readme_output / (_safe_name(path) + ".txt")
            target.write_text(text, encoding="utf-8")
            downloaded_readmes += 1

    manifest["downloaded_scripts"] = downloaded_scripts
    manifest["downloaded_readmes"] = downloaded_readmes
    Path("DATA_LARGE_FETCH_REPORT.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if downloaded_scripts == 0:
        raise RuntimeError("No Opentrons protocol scripts were downloaded")

    print(f"Downloaded scripts: {downloaded_scripts}")
    print(f"Downloaded README texts: {downloaded_readmes}")
    print("Report: DATA_LARGE_FETCH_REPORT.json")
    return 0


def _github_json(url: str) -> Dict:
    request = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub request failed {exc.code}: {body[:800]}") from exc


def _download_raw(repo: str, ref: str, path: str) -> str:
    url = f"{RAW_ROOT}/{repo}/{ref}/{path}"
    request = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def _headers() -> Dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ProtocolIR-data-fetcher"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _select_protocol_scripts(items: Iterable[Dict], limit: int) -> List[str]:
    candidates = []
    for item in items:
        path = item.get("path", "")
        if item.get("type") != "blob":
            continue
        if not path.startswith("protocols/") or not path.endswith(".py"):
            continue
        if "test" in path.lower() or "__pycache__" in path:
            continue
        candidates.append(path)
    candidates.sort(key=_protocol_rank)
    return candidates[:limit]


def _select_readmes(items: Iterable[Dict], script_dirs: set[str]) -> List[str]:
    readmes = []
    for item in items:
        path = item.get("path", "")
        if item.get("type") != "blob":
            continue
        parent = str(Path(path).parent).replace("\\", "/")
        if parent in script_dirs and path.lower().endswith("readme.md"):
            readmes.append(path)
    return sorted(readmes)


def _protocol_rank(path: str) -> tuple[int, str]:
    lower = path.lower()
    domain_hit = any(
        term in lower
        for term in ["pcr", "qpcr", "dna", "rna", "ngs", "bead", "mag", "plate", "normalization"]
    )
    api_v2_hit = ".apiv2" in lower or "ot2" in lower
    return (0 if domain_hit else 1, 0 if api_v2_hit else 1, path)


def _safe_name(path: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", path)


def _looks_like_opentrons_protocol(text: str) -> bool:
    lower = text.lower()
    return "opentrons" in lower and ("def run(" in lower or "protocol_api" in lower)


if __name__ == "__main__":
    raise SystemExit(main())
