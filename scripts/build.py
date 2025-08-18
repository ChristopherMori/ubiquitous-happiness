from pathlib import Path
import subprocess
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
MKDOCS = ROOT / 'mkdocs.yml'

def update_videos_nav(titles: dict):
    cfg = yaml.safe_load(MKDOCS.read_text(encoding='utf-8'))
    items = [{title: f"videopages/{slug}.md"} for slug, title in sorted(titles.items(), key=lambda kv: kv[1].lower())]

    nav = cfg.get('nav', [])
    new_nav, replaced = [], False
    for entry in nav:
        if isinstance(entry, dict) and 'Videos' in entry:
            new_nav.append({'Videos': items})
            replaced = True
        else:
            new_nav.append(entry)
    if not replaced:
        new_nav.append({'Videos': items})
    cfg['nav'] = new_nav
    MKDOCS.write_text(yaml.dump(cfg, sort_keys=False), encoding='utf-8')

def run(cmd):
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)

def main():
    run([sys.executable, str(ROOT / 'scripts' / 'validate.py')])

    from generate_pages import run as gen_pages
    entity_index, titles = gen_pages()

    from build_entities_index import run as build_entities
    build_entities(entity_index, titles)

    update_videos_nav(titles)

if __name__ == "__main__":
    main()
