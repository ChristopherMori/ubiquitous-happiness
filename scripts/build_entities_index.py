from pathlib import Path
from lib_slug import slugify

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
ENTITIES_DIR = DOCS / 'entities'
VIDEO_PAGES = DOCS / 'videopages'
INDEX_MD = DOCS / 'entities_index.md'

def write_entity_page(name: str, slugs: list, titles: dict):
    lines = [f"# {name}", "", "**Mentioned in:**"]
    for slug in sorted(set(slugs), key=lambda s: titles.get(s, s).lower()):
        title = titles.get(slug, slug.replace('-', ' ').title())
        lines.append(f"- [{title}](../videopages/{slug}.md)")
    lines.append("")
    (ENTITIES_DIR / f"{slugify(name)}.md").write_text("\n".join(lines), encoding='utf-8')

def write_global_index(entity_index: dict):
    lines = ["# Entity Index", ""]
    for name in sorted(entity_index.keys(), key=str.lower):
        lines.append(f"- [{name}](entities/{slugify(name)}.md)")
    lines.append("")
    INDEX_MD.write_text("\n".join(lines), encoding='utf-8')

def run(entity_index: dict, titles: dict):
    ENTITIES_DIR.mkdir(parents=True, exist_ok=True)
    for name, slugs in entity_index.items():
        write_entity_page(name, slugs, titles)
    write_global_index(entity_index)

if __name__ == "__main__":
    pass
