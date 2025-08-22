#!/usr/bin/env python3
# scripts/generate_pages.py
import json, yaml
from pathlib import Path
from typing import Dict, List, Tuple

try:
    import spacy  # type: ignore
    _NLP = spacy.load("en_core_web_sm")
except Exception:
    _NLP = None

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
VID_ROOT = DOCS / "videos"
PAGES = DOCS / "video-pages"
PAGES.mkdir(parents=True, exist_ok=True)

def read_yaml(p): 
    return yaml.safe_load(p.read_text(encoding="utf-8"))

def read_transcript(folder: Path):
    p_md = folder / "transcript.md"
    if p_md.exists():
        return p_md.read_text(encoding="utf-8")
    p_txt = folder / "transcript.txt"
    return p_txt.read_text(encoding="utf-8") if p_txt.exists() else ""

def rel_from_page(path_in_docs: Path) -> str:
    rel = path_in_docs.relative_to(DOCS)
    return f"../{rel.as_posix()}"

def front_matter(title: str) -> str:
    fm = yaml.safe_dump({"title": title}, sort_keys=False).strip()
    return f"---\n{fm}\n---\n"

def build_page(meta, folder: Path) -> str:
    vid = meta["youtube_id"]
    desc = (meta.get("description") or "").strip()
    txt  = read_transcript(folder)

    thumb = None
    for ext in (".jpg", ".png", ".webp", ".jpeg"):
        p = folder / f"thumb{ext}"
        if p.exists():
            thumb = rel_from_page(p)
            break

    lines = []
    lines.append(front_matter(meta["title"]))
    lines += [f"# {meta['title']}", ""]
    if thumb:
        lines += [f"![thumbnail]({thumb})", ""]
    lines += [
        f'<iframe width="720" height="405" src="https://www.youtube.com/embed/{vid}" frameborder="0" allowfullscreen></iframe>',
        "",
        f"**Published:** {meta.get('date_published','')}  ·  **Duration:** {meta.get('duration','')}  ·  **Channel:** {meta.get('channel','')}",
        ""
    ]

    if desc:
        lines += ['??? note "Description"', "    " + desc.replace("\n", "\n    "), ""]

    ch = folder / "chapters.json"
    if ch.exists():
        chapters = json.loads(ch.read_text(encoding="utf-8"))
        if chapters:
            lines += ["## Chapters"]
            for c in chapters:
                start = int(c.get("start_time") or 0)
                title = (c.get("title") or "").strip()
                lines += [f"- [{title}](https://youtu.be/{vid}?t={start})"]
            lines += [""]

    if txt:
        lines += ["## Transcript", '??? info "Show transcript"', "    " + txt.replace("\n", "\n    "), ""]
    else:
        lines += ["## Transcript", "> _Transcript coming soon (pending local Whisper run)._", ""]

    ents = extract_entities(txt) if txt else {"people": [], "places": [], "orgs": []}
    if any(ents.values()):
        lines += ["## Entities"]
        if ents["people"]:
            lines += ["- People:"]
            for name in ents["people"]:
                lines += [f"  - {name}"]
        if ents["places"]:
            lines += ["- Places:"]
            for name in ents["places"]:
                lines += [f"  - {name}"]
        if ents["orgs"]:
            lines += ["- Organizations:"]
            for name in ents["orgs"]:
                lines += [f"  - {name}"]
        lines += [""]

    dlinks = []
    for ext,label in [(".srt","SRT"),(".vtt","VTT"),(".json","JSON"),(".tsv","TSV")]:
        p = folder / f"transcript{ext}"
        if p.exists():
            dlinks.append(f"[{label}]({rel_from_page(p)})")
    if dlinks:
        lines += ["**Download transcripts:** " + " · ".join(dlinks), ""]

    return "\n".join(lines).rstrip() + "\n"

def extract_entities(text: str) -> Dict[str, List[str]]:
    if not _NLP:
        return {"people": [], "places": [], "orgs": []}
    doc = _NLP(text)
    people = set()
    places = set()
    orgs = set()
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            people.add(ent.text.strip())
        elif ent.label_ in ("GPE", "LOC", "FAC"):
            places.add(ent.text.strip())
        elif ent.label_ == "ORG":
            orgs.add(ent.text.strip())
    def _norm_list(s):
        return sorted({x for x in s if x and not x.isnumeric()})
    return {"people": _norm_list(people), "places": _norm_list(places), "orgs": _norm_list(orgs)}

def build_index(catalog) -> str:
    lines = ["# UAP Gerb – Video Index", ""]
    lines += [f"_Total videos: {len(catalog['videos'])}_", ""]
    for v in catalog["videos"]:
        folder = resolve_folder_from_entry(v)
        if not folder:
            continue
        meta = read_yaml(folder / "metadata.yml")
        has_transcript = (folder / "transcript.md").exists() or (folder / "transcript.txt").exists()
        tick = "✅" if has_transcript else "🕓"
        lines += [f"- {tick} **[{meta['title']}]({'video-pages/' + v['id'] + '.md'})** — {meta.get('date_published','')}"]
    return "\n".join(lines).rstrip() + "\n"

def build_entities_index(catalog) -> str:
    aggregate: Dict[str, Dict[str, List[Tuple[str, str]]]] = {
        "people": {},
        "places": {},
        "orgs": {},
    }
    for v in catalog["videos"]:
        folder = resolve_folder_from_entry(v)
        if not folder:
            continue
        meta = read_yaml(folder / "metadata.yml")
        txt = read_transcript(folder)
        if not txt:
            continue
        ents = extract_entities(txt)
        for kind in ("people", "places", "orgs"):
            for name in ents[kind]:
                aggregate[kind].setdefault(name, []).append((meta.get("title", v["id"]), v["id"]))

    lines = ["# Entities", ""]
    for kind, header in [("people", "People"), ("places", "Places"), ("orgs", "Organizations")]:
        block = aggregate[kind]
        if not block:
            continue
        lines += [f"## {header}"]
        for name in sorted(block.keys(), key=lambda s: s.lower()):
            refs = block[name]
            links = ", ".join([f"[{title}](video-pages/{vid}.md)" for title, vid in refs])
            lines += [f"- **{name}**: {links}"]
        lines += [""]
    return "\n".join(lines).rstrip() + "\n"

def resolve_folder_from_entry(entry: dict):
    rel = entry.get("rel_path")
    if rel:
        p = DOCS / rel
        return p if p.exists() else None
    legacy_path = entry.get("path")
    if legacy_path:
        p = Path(legacy_path)
        return p if p.exists() else None
    vid = entry.get("id")
    if not vid:
        return None
    for child in VID_ROOT.glob(f"{vid}-*"):
        if child.is_dir():
            return child
    return None

def main():
    cat = json.loads((ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))
    for entry in cat["videos"]:
        folder = resolve_folder_from_entry(entry)
        if not folder:
            continue
        meta = read_yaml(folder / "metadata.yml")
        out_md = build_page(meta, folder)
        (PAGES / f"{entry['id']}.md").write_text(out_md, encoding="utf-8")

    index_md = build_index(cat)
    (DOCS / "video-index.md").write_text(index_md, encoding="utf-8")
    # Ensure a homepage exists at root so '/' is not a 404 when hosted
    # on GitHub Pages or any static host.
    (DOCS / "index.md").write_text(index_md, encoding="utf-8")
    (DOCS / "entities.md").write_text(build_entities_index(cat), encoding="utf-8")
    print(f"Built {len(cat['videos'])} pages + index")

if __name__ == "__main__":
    main()
