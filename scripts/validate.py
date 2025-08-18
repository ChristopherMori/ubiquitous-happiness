from pathlib import Path
import json
import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPTS = ROOT / 'docs' / 'assets' / 'transcripts'
SCHEMA = ROOT / 'scripts' / 'config' / 'metadata.schema.json'
KNOWN_EXTS = {'.txt', '.srt', '.vtt', '.json', '.tsv'}

def has_any_transcript(folder: Path) -> bool:
    for ext in KNOWN_EXTS:
        if any(folder.glob(f"*{ext}")):
            return True
    return False

def main():
    schema = json.loads(SCHEMA.read_text(encoding='utf-8'))
    validator = Draft202012Validator(schema)
    errors = []

    if not TRANSCRIPTS.exists():
        raise SystemExit("No transcripts directory found at docs/assets/transcripts")

    for folder in sorted(TRANSCRIPTS.iterdir()):
        if not folder.is_dir():
            continue
        meta_path = folder / 'metadata.yml'
        if not meta_path.exists():
            errors.append(f"{folder.name}: missing metadata.yml")
            continue
        try:
            data = yaml.safe_load(meta_path.read_text(encoding='utf-8')) or {}
        except Exception as e:
            errors.append(f"{folder.name}: metadata.yml parse error: {e}")
            continue

        for e in validator.iter_errors(data):
            errors.append(f"{folder.name}: {e.message}")

        if not has_any_transcript(folder):
            errors.append(f"{folder.name}: no transcript files found (.txt/.srt/.vtt/.json/.tsv)")

    if errors:
        raise SystemExit("Validation failed:\n" + "\n".join(errors))

if __name__ == "__main__":
    main()
