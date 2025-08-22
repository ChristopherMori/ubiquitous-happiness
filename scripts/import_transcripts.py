#!/usr/bin/env python3
"""
Import external transcript files into the correct docs/videos/<id>-<slug>/ folders.

Usage (Windows PowerShell example):
  python scripts/import_transcripts.py "C:\\Users\\enisi\\Documents\\UAPGERB\\transcripts"

It will:
  - Scan for files named like: Anything [<YouTubeID>].{txt,srt,vtt,json,tsv}
  - For each ID present in data/catalog.json, copy into docs/videos/<id>-<slug>/
  - Rename to canonical names: transcript.txt, transcript.srt, transcript.vtt, transcript.json, transcript.tsv
  - Skip files for IDs not present in catalog
  - Preserve existing files unless --overwrite is passed

After import, run:  python scripts/build.py
"""
from __future__ import annotations
import argparse
import re
import shutil
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
VID_ROOT = DOCS / "videos"
CATALOG_JSON = ROOT / "data" / "catalog.json"

ID_RE = re.compile(r"\[(?P<id>[A-Za-z0-9_-]{6,})\]\.(?P<ext>txt|srt|vtt|json|tsv)$", re.IGNORECASE)

def load_catalog():
    if not CATALOG_JSON.exists():
        return {"videos": []}
    return json.loads(CATALOG_JSON.read_text(encoding="utf-8"))

def map_id_to_folder() -> dict[str, Path]:
    cat = load_catalog()
    out = {}
    for v in cat.get("videos", []):
        rid = v.get("id")
        rel = v.get("rel_path")
        if rid and rel:
            p = DOCS / rel
            if p.exists():
                out[rid] = p
    return out

def find_transcript_candidates(root: Path) -> list[Path]:
    files: list[Path] = []
    for p in root.rglob("*"):
        if p.is_file():
            m = ID_RE.search(p.name)
            if m:
                files.append(p)
    return files

def canonical_name(ext: str) -> str:
    return f"transcript.{ext.lower()}"

def import_one(src: Path, dest_dir: Path, overwrite: bool) -> tuple[bool, str]:
    m = ID_RE.search(src.name)
    assert m
    ext = m.group("ext").lower()
    dest = dest_dir / canonical_name(ext)
    if dest.exists() and not overwrite:
        return False, f"exists: {dest.relative_to(ROOT)}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return True, f"copied: {src} -> {dest.relative_to(ROOT)}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source_root", type=str, help="Path containing transcript folders")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing transcript files")
    args = ap.parse_args()

    source = Path(args.source_root)
    if not source.exists():
        raise SystemExit(f"Source not found: {source}")

    id_to_folder = map_id_to_folder()
    if not id_to_folder:
        raise SystemExit("No videos found in catalog or docs/videos")

    candidates = find_transcript_candidates(source)
    if not candidates:
        print("No transcript candidates found.")
        return

    imported = 0
    skipped = 0
    missing = set()

    for p in candidates:
        m = ID_RE.search(p.name)
        if not m:
            continue
        vid = m.group("id")
        dest_dir = id_to_folder.get(vid)
        if not dest_dir:
            missing.add(vid)
            skipped += 1
            continue
        ok, msg = import_one(p, dest_dir, args.overwrite)
        print(msg)
        imported += 1 if ok else 0
        skipped += 0 if ok else 1

    if missing:
        print("\nIDs not found in catalog (skipped):", ", ".join(sorted(missing)))
    print(f"\nImported: {imported}, Skipped: {skipped}")

if __name__ == "__main__":
    main()


