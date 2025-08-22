#!/usr/bin/env python3
from pathlib import Path
import yaml
import json
from jsonschema import validate, ValidationError

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
MKDOCS_YML = ROOT / "mkdocs.yml"
CATALOG_JSON = ROOT / "data" / "catalog.json"
CATALOG_SCHEMA = ROOT / "data" / "catalog.schema.json"

def validate_catalog_file():
    if not CATALOG_JSON.exists():
        return
    try:
        catalog = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Invalid JSON in {CATALOG_JSON}: {exc}")
    if CATALOG_SCHEMA.exists():
        try:
            schema = json.loads(CATALOG_SCHEMA.read_text(encoding="utf-8"))
            validate(instance=catalog, schema=schema)
        except ValidationError as ve:
            path = "/".join([str(p) for p in ve.path])
            loc = f" at /{path}" if path else ""
            raise SystemExit(f"Catalog schema validation failed{loc}: {ve.message}")
        except Exception as exc:
            raise SystemExit(f"Failed to load/validate schema: {exc}")

def build_videos_nav():
    if not CATALOG_JSON.exists():
        return {"Videos": [{"No videos yet": "video-index.md"}]}
    cat = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
    items = []
    for v in cat.get("videos", []):
        title = v.get("title") or v.get("id")
        items.append({title: f"video-pages/{v['id']}.md"})
    if not items:
        items = [{"No videos yet": "video-index.md"}]
    return {"Videos": items}

def ensure_nav_entries():
    data = yaml.safe_load(MKDOCS_YML.read_text(encoding="utf-8"))
    nav = data.get("nav") or []
    # Ensure index and entities exist in nav
    def _has(title, path):
        for item in nav:
            if isinstance(item, dict) and title in item and item[title] == path:
                return True
        return False
    changed = False
    if not _has("Video Index", "video-index.md"):
        nav.insert(0, {"Video Index": "video-index.md"})
        changed = True

    # Ensure Videos section lists all video pages (only change if different)
    videos_entry = build_videos_nav()
    existing_videos = None
    for item in nav:
        if isinstance(item, dict) and "Videos" in item:
            existing_videos = item
            break
    if existing_videos != videos_entry:
        nav = [n for n in nav if not (isinstance(n, dict) and "Videos" in n)]
        nav.append(videos_entry)
        changed = True

    # Ensure Entities exists
    if not _has("Entities", "entities.md"):
        nav.append({"Entities": "entities.md"})
        changed = True

    if changed:
        data["nav"] = nav
        MKDOCS_YML.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

def main():
    # Generate pages and indices
    import subprocess, sys
    validate_catalog_file()
    subprocess.check_call([sys.executable, str(ROOT / "scripts" / "generate_pages.py")])
    ensure_nav_entries()

if __name__ == "__main__":
    main()


