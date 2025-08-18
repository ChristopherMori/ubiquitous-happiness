from pathlib import Path
import json
import re

def find_transcript_files(folder: Path) -> dict:
    exts = ['.txt', '.vtt', '.srt', '.json', '.tsv']
    return {ext: sorted(folder.glob(f'*{ext}')) for ext in exts}

def choose_inline_transcript(folder: Path) -> str | None:
    files = find_transcript_files(folder)
    if files['.txt']:
        return Path(files['.txt'][0]).read_text(encoding='utf-8')
    if files['.vtt']:
        return vtt_to_text(Path(files['.vtt'][0]).read_text(encoding='utf-8'))
    if files['.srt']:
        return srt_to_text(Path(files['.srt'][0]).read_text(encoding='utf-8'))
    if files['.json']:
        return json_to_text(Path(files['.json'][0]).read_text(encoding='utf-8'))
    if files['.tsv']:
        return tsv_to_text(Path(files['.tsv'][0]).read_text(encoding='utf-8'))
    return None

def srt_to_text(s: str) -> str:
    blocks = re.split(r'\n\s*\n', s.strip())
    out = []
    for b in blocks:
        lines = [ln for ln in b.splitlines()
                 if not re.match(r'^\d+\s*$', ln.strip())
                 and '-->' not in ln]
        out.extend(lines)
    return '\n'.join([ln.strip() for ln in out if ln.strip()])

def vtt_to_text(s: str) -> str:
    out = []
    for ln in s.splitlines():
        t = ln.strip()
        if not t or t.upper() == 'WEBVTT':
            continue
        if '-->' in t:
            continue
        out.append(t)
    return '\n'.join(out)

def json_to_text(s: str) -> str:
    data = json.loads(s)
    items = data if isinstance(data, list) else data.get('transcript', [])
    lines = []
    for item in items:
        txt = item.get('text') or item.get('line') or ''
        if txt:
            lines.append(txt.strip())
    return '\n'.join(lines)

def tsv_to_text(s: str) -> str:
    out = []
    for ln in s.splitlines():
        parts = ln.split('\t')
        if parts:
            out.append(parts[-1].strip())
    return '\n'.join(out)
