from pathlib import Path
import yaml
from lib_slug import slugify
from lib_transcript import choose_inline_transcript, find_transcript_files
from lib_entities import extract_entities_optional, merge_entities, load_alias_map, load_stopwords

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
TRANSCRIPTS = DOCS / 'assets' / 'transcripts'
VIDEO_PAGES = DOCS / 'videopages'
CONFIG = ROOT / 'scripts' / 'config'

def _download_links(files_map):
    links = []
    for ext in ['.txt', '.srt', '.vtt', '.tsv', '.json']:
        for f in files_map.get(ext, []):
            rel_from_docs = f.relative_to(DOCS).as_posix()
            rel_from_videopage = f"../{rel_from_docs}"
            label = ext[1:].upper()
            links.append((label, rel_from_videopage))
    return links

def _entity_link(name: str) -> str:
    return f"../entities/{slugify(name)}.md"

def generate_page(slug: str):
    folder = TRANSCRIPTS / slug
    meta = yaml.safe_load((folder / 'metadata.yml').read_text(encoding='utf-8')) or {}
    title = meta['title']
    youtube_id = meta['youtube_id']
    description = (meta.get('description') or '').strip()

    inline = choose_inline_transcript(folder) or "Transcript unavailable."
    files_map = find_transcript_files(folder)

    alias_map = load_alias_map(CONFIG / 'entity_aliases.yml')
    stopwords = load_stopwords(CONFIG / 'entity_stopwords.yml')

    inferred = extract_entities_optional(inline, stopwords, alias_map)
    entities = merge_entities(meta, inferred)

    expected = slugify(title)
    if expected != slug:
        print(f"[warn] Folder '{slug}' differs from slugified title '{expected}'. Consider renaming.")

    lines = []
    lines.append(f"# {title}\n")
    lines.append(
        f"<iframe title=\"{title}\" width=\"560\" height=\"315\" "
        f"src=\"https://www.youtube-nocookie.com/embed/{youtube_id}\" "
        f"frameborder=\"0\" allowfullscreen loading=\"lazy\"></iframe>\n"
    )
    if description:
        lines.append(f"> {description}\n")

    lines.append("## Transcript")
    lines.append("??? info \"Click to expand transcript\"")
    lines.append("    ~~~")
    for ln in inline.splitlines():
        lines.append(f"    {ln}")
    lines.append("    ~~~\n")

    downloads = _download_links(files_map)
    if downloads:
        lines.append("## Downloads")
        for label, rel in downloads:
            lines.append(f"- [{label}]({rel})")
        lines.append("")

    lines.append("## Metadata")
    if meta.get('date_published'):
        lines.append(f"- **Date Published**: {meta['date_published']}")
    if meta.get('duration'):
        lines.append(f"- **Duration**: {meta['duration']}")

    def render_bucket(label, names):
        names = names or []
        if not names:
            return
        lines.append(f"- **{label}**:")
        for n in names:
            lines.append(f"  - [{n}]({_entity_link(n)})")

    render_bucket("People", entities.get('people'))
    render_bucket("Places", entities.get('places'))
    render_bucket("Organizations", entities.get('organizations'))
    lines.append("")

    out = VIDEO_PAGES / f"{slug}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding='utf-8')

    return entities, title

def run():
    titles = {}
    inv_index = {}
    if not TRANSCRIPTS.exists():
        print("[warn] No transcripts directory at docs/assets/transcripts")
        return inv_index, titles

    for folder in sorted(TRANSCRIPTS.iterdir()):
        if not folder.is_dir():
            continue
        slug = folder.name
        mp = folder / 'metadata.yml'
        if not mp.exists():
            print(f"[warn] Skipping {slug}: missing metadata.yml")
            continue

        entities, title = generate_page(slug)
        titles[slug] = title
        for bucket, names in entities.items():
            for name in names or []:
                inv_index.setdefault(name, []).append(slug)

    return inv_index, titles

if __name__ == "__main__":
    run()
