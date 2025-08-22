#!/usr/bin/env python3
# scripts/generate_pages.py
import json, yaml
import os, re, shutil
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
TRANSCRIPTS_ROOT = os.environ.get("TRANSCRIPTS_ROOT") and Path(os.environ["TRANSCRIPTS_ROOT"]) or None

def read_yaml(p): 
    return yaml.safe_load(p.read_text(encoding="utf-8"))

def read_transcript(folder: Path):
    p_md = folder / "transcript.md"
    if p_md.exists():
        return p_md.read_text(encoding="utf-8")
    p_txt = folder / "transcript.txt"
    return p_txt.read_text(encoding="utf-8") if p_txt.exists() else ""

def _copy_if_exists(src: Path, dest: Path):
    try:
        if src.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            return True
    except Exception:
        pass
    return False

def maybe_import_transcripts(vid: str, dest_folder: Path):
    """If TRANSCRIPTS_ROOT is set, try to locate files named like
    *[<vid>].ext and copy them into dest_folder with canonical names.
    """
    if not TRANSCRIPTS_ROOT or not TRANSCRIPTS_ROOT.exists():
        return
    # Search recursively for files that end with [<vid>].ext (robust against unicode titles)
    exts = ("txt", "md", "srt", "vtt", "json", "tsv")
    patterns = [re.compile(r"\[" + re.escape(vid) + r"\]\." + ext + r"$", re.IGNORECASE) for ext in exts]
    found: dict[str, Path] = {}
    for p in TRANSCRIPTS_ROOT.rglob("*"):
        if not p.is_file():
            continue
        name = p.name
        for ext, pat in zip(exts, patterns):
            if pat.search(name):
                found[ext] = p
                break
    if not found:
        return
    # Prefer md over txt for main transcript body
    if "md" in found:
        _copy_if_exists(found["md"], dest_folder / "transcript.md")
    if "txt" in found and not (dest_folder / "transcript.md").exists():
        _copy_if_exists(found["txt"], dest_folder / "transcript.txt")
    for ext in ("srt", "vtt", "json", "tsv"):
        if ext in found:
            _copy_if_exists(found[ext], dest_folder / f"transcript.{ext}")

def rel_from_page(path_in_docs: Path) -> str:
    rel = path_in_docs.relative_to(DOCS)
    return f"../{rel.as_posix()}"

def front_matter(title: str) -> str:
    fm = yaml.safe_dump({"title": title}, sort_keys=False).strip()
    return f"---\n{fm}\n---\n"

def build_page(meta, folder: Path, nav: Dict[str, Tuple[str, str]] | None = None, related: List[Tuple[str, str]] | None = None) -> str:
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
        lines += ["## Entities", ""]
        for key, label in [("people", "People"), ("places", "Places"), ("orgs", "Organizations")]:
            names = ents.get(key) or []
            if not names:
                continue
            count = len(names)
            # Collapsible section per category using pymdownx.details (Material)
            lines += [f"??? info \"{label} ({count})\"", ""]
            for name in names:
                lines += [f"    - {name}"]
            lines += [""]

    dlinks = []
    for ext,label in [(".srt","SRT"),(".vtt","VTT"),(".json","JSON"),(".tsv","TSV")]:
        p = folder / f"transcript{ext}"
        if p.exists():
            dlinks.append(f"[{label}]({rel_from_page(p)})")
    if dlinks:
        lines += ["**Download transcripts:** " + " · ".join(dlinks), ""]

    # Related videos
    if related:
        lines += ["## Related videos", ""]
        for rid, rtitle in related[:5]:
            lines += [f"- [{rtitle}](video-pages/{rid}.md)"]
        lines += [""]

    # Newer/Older navigation
    if nav:
        newer = nav.get("newer")
        older = nav.get("older")
        nav_line_parts: List[str] = []
        if newer:
            nav_line_parts.append(f"← Newer: [{newer[1]}](video-pages/{newer[0]}.md)")
        if older:
            nav_line_parts.append(f"Older: [{older[1]}](video-pages/{older[0]}.md) →")
        if nav_line_parts:
            lines += ["---", "", " · ".join(nav_line_parts), ""]

    # Comments section (Utterances by default). Set COMMENTS_PROVIDER=none to disable.
    provider = os.environ.get("COMMENTS_PROVIDER", "utterances").lower()
    if provider != "none":
        # Default to this repo; can be overridden via COMMENTS_REPO env var
        repo = os.environ.get("COMMENTS_REPO", "christophermori/ubiquitous-happiness")
        theme = os.environ.get("COMMENTS_THEME", "github-light")
        if provider == "utterances" and repo:
            script_block = (
                '<script src="https://utteranc.es/client.js" '
                f'repo="{repo}" '
                'issue-term="pathname" '
                'label="comments" '
                f'theme="{theme}" '
                'crossorigin="anonymous" '
                'async></script>'
            )
            lines += [
                "## Comments",
                "",
                script_block,
                "",
            ]

    return "\n".join(lines).rstrip() + "\n"

def extract_entities(text: str) -> Dict[str, List[str]]:
    """Extract entities with heuristics and optional overrides to improve categorization.

    Heuristics applied:
      - Titles like Dr., Sgt, Lt, Maj, Gen → people
      - Organization keywords (Inc, LLC, University, Agency, Air Force, Navy, CIA, SAIC, etc.) → orgs
      - Place keywords (AFB, Base, County, Lake, City, specific locations) → places
      - Ignore very generic terms (UFO, UAP, etc.)
      - Optional overrides from data/entity_overrides.yml with keys: people, places, orgs, ignore
    """
    if not _NLP:
        return {"people": [], "places": [], "orgs": []}

    def _normalize(name: str) -> str:
        name = name.strip().strip('"\'\u201c\u201d').strip()
        name = re.sub(r"\s+", " ", name)
        return name

    OVERRIDES_P = ROOT / "data" / "entity_overrides.yml"
    overrides = {"people": set(), "places": set(), "orgs": set(), "ignore": set()}
    if OVERRIDES_P.exists():
        try:
            raw = yaml.safe_load(OVERRIDES_P.read_text(encoding="utf-8")) or {}
            for k in overrides.keys():
                vals = raw.get(k) or []
                overrides[k] = {v.lower() for v in vals if isinstance(v, str) and v.strip()}
        except Exception:
            pass

    TITLE_TOKENS = {"dr", "mr", "mrs", "ms", "sgt", "lt", "maj", "gen", "col", "cmdr", "capt", "prof", "sir"}
    ORG_KEYWORDS = {
        "inc", "corp", "llc", "company", "co.", "university", "college", "institute", "laboratories", "labs",
        "agency", "department", "ministry", "office", "committee", "foundation", "institute", "academy",
        "air force", "navy", "marine corps", "army", "usaf", "us navy", "us army", "cia", "nsa", "darpa", "nro",
        "saic", "battelle", "lockheed", "skunk works", "lockheed martin", "northrop", "northrop grumman", "boeing",
    }
    PLACE_KEYWORDS = {
        "afb", "air force base", "base", "county", "city", "lake", "mount", "mountain", "valley", "area",
        "edwards", "kingman", "kecksburg", "coyame", "peru", "mexico", "italy", "arizona", "texas", "pennsylvania",
        "dugway proving ground", "magenta", "del rio",
    }
    GENERIC_IGNORE = {"ufo", "uap", "ufos", "uaps", "intro"}

    def looks_like_person(name: str) -> bool:
        t = name.lower()
        if any(t.startswith(x + " ") for x in TITLE_TOKENS):
            return True
        # Simple two-token proper name heuristic
        parts = name.split()
        return len(parts) in (2, 3) and all(p[:1].isupper() for p in parts if p)

    def looks_like_org(name: str) -> bool:
        t = name.lower()
        return any(k in t for k in ORG_KEYWORDS)

    def looks_like_place(name: str) -> bool:
        t = name.lower()
        return any(k in t for k in PLACE_KEYWORDS)

    doc = _NLP(text)
    bucket: Dict[str, set] = {"people": set(), "places": set(), "orgs": set()}
    raw_items: List[Tuple[str, str]] = []
    for ent in doc.ents:
        if ent.label_ not in ("PERSON", "ORG", "GPE", "LOC", "FAC", "NORP"):
            continue
        nm = _normalize(ent.text)
        if not nm or nm.isnumeric():
            continue
        raw_items.append((nm, ent.label_))

    # First pass: spaCy mapping
    for nm, label in raw_items:
        low = nm.lower()
        if low in overrides["ignore"] or low in GENERIC_IGNORE:
            continue
        if low in overrides["people"]:
            bucket["people"].add(nm)
            continue
        if low in overrides["places"]:
            bucket["places"].add(nm)
            continue
        if low in overrides["orgs"]:
            bucket["orgs"].add(nm)
            continue
        if label == "PERSON":
            bucket["people"].add(nm)
        elif label in ("GPE", "LOC", "FAC"):
            bucket["places"].add(nm)
        elif label in ("ORG", "NORP"):
            bucket["orgs"].add(nm)

    # Heuristic corrections
    def recategorize(names: set) -> Dict[str, set]:
        out = {"people": set(), "places": set(), "orgs": set()}
        for nm in names:
            low = nm.lower()
            if low in overrides["ignore"] or low in GENERIC_IGNORE:
                continue
            if low in overrides["people"]:
                out["people"].add(nm); continue
            if low in overrides["places"]:
                out["places"].add(nm); continue
            if low in overrides["orgs"]:
                out["orgs"].add(nm); continue
            if looks_like_person(nm):
                out["people"].add(nm)
            elif looks_like_org(nm):
                out["orgs"].add(nm)
            elif looks_like_place(nm):
                out["places"].add(nm)
        return out

    # Merge heuristic corrections across buckets to fix mislabels
    all_names = set().union(*bucket.values())
    corrected = recategorize(all_names)
    people = corrected["people"] or bucket["people"]
    places = corrected["places"] or bucket["places"]
    orgs = corrected["orgs"] or bucket["orgs"]

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

def should_preserve_homepage(idx_path: Path) -> bool:
    """Detect a custom homepage we shouldn't overwrite.
    Preserves if the file exists and contains either 'template: home' or 'custom_home: true'.
    """
    if not idx_path.exists():
        return False
    try:
        txt = idx_path.read_text(encoding="utf-8")
    except Exception:
        return False
    return ("template: home" in txt) or ("custom_home: true" in txt)

def resolve_thumb(folder: Path) -> Path | None:
    for ext in (".jpg", ".png", ".webp", ".jpeg"):
        p = folder / f"thumb{ext}"
        if p.exists():
            return p
    return None

def build_latest_grid(catalog, limit: int = 12, columns: int = 3) -> str:
    """Return HTML for a thumbnail grid of the latest N videos."""
    rows = []
    row = []
    count = 0
    for v in catalog["videos"]:
        if count >= limit:
            break
        folder = resolve_folder_from_entry(v)
        if not folder:
            continue
        thumb = resolve_thumb(folder)
        if not thumb:
            continue
        title = read_yaml(folder / "metadata.yml").get("title", v["id"]).strip()
        page = f"video-pages/{v['id']}.md"
        img = rel_from_page(thumb).replace("../", "")  # from index.md root
        cell = (
            f'<td style="vertical-align:top; padding:10px; text-align:center;">'
            f'<a href="{page}"><img src="{img}" alt="{title}" width="240" style="border-radius:6px;"/></a><br/>'
            f'<a href="{page}"><small>{title}</small></a>'
            f"</td>"
        )
        row.append(cell)
        count += 1
        if len(row) == columns:
            rows.append("<tr>" + "".join(row) + "</tr>")
            row = []
    if row:
        rows.append("<tr>" + "".join(row) + "</tr>")
    if not rows:
        return ""
    table = (
        '<table style="width:100%; border-collapse:separate; border-spacing:0 0;">' + "\n" +
        "\n".join(rows) + "\n" +
        "</table>"
    )
    return table

def inject_latest_grid_into_home(catalog):
    """Replace content between markers with a fresh latest grid."""
    idx = DOCS / "index.md"
    if not idx.exists():
        return
    txt = idx.read_text(encoding="utf-8")
    start = "<!-- latest-grid:start -->"
    end = "<!-- latest-grid:end -->"
    if start not in txt or end not in txt:
        return
    grid = build_latest_grid(catalog, limit=12, columns=3)
    replacement = f"{start}\n{grid}\n{end}"
    new_txt = re.sub(r"<!-- latest-grid:start -->[\s\S]*?<!-- latest-grid:end -->", replacement, txt, flags=re.MULTILINE)
    if new_txt != txt:
        idx.write_text(new_txt, encoding="utf-8")

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

    # Preload minimal metadata for navigation and related
    id_list: List[str] = [v["id"] for v in cat["videos"]]
    id_to_title: Dict[str, str] = {}
    id_to_tags: Dict[str, List[str]] = {}
    id_to_folder: Dict[str, Path] = {}

    for entry in cat["videos"]:
        folder = resolve_folder_from_entry(entry)
        if not folder:
            continue
        id_to_folder[entry["id"]] = folder
        meta = read_yaml(folder / "metadata.yml")
        id_to_title[entry["id"]] = (meta.get("title") or entry["id"]).strip()
        id_to_tags[entry["id"]] = [t.strip() for t in (meta.get("tags") or []) if isinstance(t, str) and t.strip()]

    # Compute newer/older navigation (catalog assumed newest -> oldest)
    nav_map: Dict[str, Dict[str, Tuple[str, str]]] = {}
    for idx, vid in enumerate(id_list):
        newer = (id_list[idx - 1], id_to_title[id_list[idx - 1]]) if idx > 0 else None
        older = (id_list[idx + 1], id_to_title[id_list[idx + 1]]) if idx < len(id_list) - 1 else None
        entry_nav: Dict[str, Tuple[str, str]] = {}
        if newer:
            entry_nav["newer"] = newer
        if older:
            entry_nav["older"] = older
        nav_map[vid] = entry_nav

    # Compute related by tag overlap
    related_map: Dict[str, List[Tuple[str, str]]] = {}
    tag_sets: Dict[str, set] = {vid: set(tags) for vid, tags in id_to_tags.items()}
    for i, vid in enumerate(id_list):
        scores: List[Tuple[int, int, str]] = []  # (-overlap, index, other_vid)
        for j, other in enumerate(id_list):
            if other == vid:
                continue
            overlap = len(tag_sets.get(vid, set()) & tag_sets.get(other, set()))
            if overlap > 0:
                scores.append((-overlap, j, other))
        scores.sort()
        top_related: List[Tuple[str, str]] = [(ov, id_to_title[ov]) for _, __, ov in scores[:5]]
        related_map[vid] = top_related

    # Build each page with navigation and related
    for entry in cat["videos"]:
        vid = entry["id"]
        folder = id_to_folder.get(vid)
        if not folder:
            continue
        meta = read_yaml(folder / "metadata.yml")
        # Opportunistically import transcripts if provided externally
        try:
            maybe_import_transcripts(meta.get("youtube_id", vid), folder)
        except Exception:
            pass
        out_md = build_page(meta, folder, nav=nav_map.get(vid), related=related_map.get(vid) or [])
        (PAGES / f"{vid}.md").write_text(out_md, encoding="utf-8")

    index_md = build_index(cat)
    (DOCS / "video-index.md").write_text(index_md, encoding="utf-8")
    # Write homepage only if not customized
    idx = DOCS / "index.md"
    if not should_preserve_homepage(idx):
        idx.write_text(index_md, encoding="utf-8")
    # Update latest grid in homepage if markers present
    inject_latest_grid_into_home(cat)
    (DOCS / "entities.md").write_text(build_entities_index(cat), encoding="utf-8")
    print(f"Built {len(cat['videos'])} pages + index")

if __name__ == "__main__":
    main()
