#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DATA = ROOT / "data"

def main():
    cat_path = DATA / "catalog.json"
    if not cat_path.exists():
        print("No data/catalog.json found; nothing to migrate.")
        return

    catalog = json.loads(cat_path.read_text(encoding="utf-8"))
    changed = False
    for v in catalog.get("videos", []):
        if "rel_path" in v:
            continue
        legacy = v.get("path")
        if not legacy:
            continue
        p = Path(legacy)
        try:
            rel = p.relative_to(DOCS)
        except Exception:
            # If the path is absolute or outside docs, attempt best-effort mapping
            if str(p).replace("\\", "/").split("/docs/")[-1]:
                rel = Path(str(p).replace("\\", "/").split("/docs/")[-1])
            else:
                continue
        v["rel_path"] = rel.as_posix()
        if "path" in v:
            del v["path"]
        changed = True

    if changed:
        cat_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")
        print("catalog.json migrated: added rel_path and removed path")
    else:
        print("catalog.json already uses rel_path; no changes.")

if __name__ == "__main__":
    main()


