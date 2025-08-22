# UAP Gerb Archive

A simple MkDocs-based archive that fetches YouTube metadata via the YouTube Data API, writes per-video folders under `docs/videos/<id>-<slug>/`, and generates Markdown pages under `docs/video-pages/`.

## Setup

- Install Python 3.10+.
- Create a virtualenv and install deps:
  
  ```bash
  python -m venv .venv
  .venv\Scripts\activate  # Windows PowerShell
  pip install -r requirements.txt
  ```

- Set your YouTube API key in the environment:
  
  ```bash
  $env:YT_API_KEY="YOUR_KEY"  # Windows PowerShell
  ```

- (Optional, enables entity extraction):
  ```bash
  python -m spacy download en_core_web_sm
  ```

## Usage

1) Ingest channel uploads metadata and thumbnails:

```bash
python scripts/ingest_via_api.py "@UAPGerb"
```

This creates/updates `data/catalog.json` and fills `docs/videos/` with per-video folders and metadata.

2) Generate Markdown pages (and update nav/entities):

```bash
python scripts/build.py
```

This writes pages to `docs/video-pages/`, generates `docs/video-index.md` and `docs/entities.md`, and updates `mkdocs.yml` navigation.

3) Serve the site with MkDocs:

```bash
mkdocs serve
```

### Importing transcripts (SRT/VTT/TXT/JSON/TSV)

If you have local transcript exports named like `Anything [<YouTubeID>].ext` (for example: `My Video [QJ215I85d5M].srt`), you can bulk-import them:

```bash
# Example PowerShell path pointing to your transcript root
python scripts/import_transcripts.py "C:\\Users\\enisi\\Documents\\UAPGERB\\transcripts" --overwrite
python scripts/build.py
```

The importer copies files into each `docs/videos/<id>-<slug>/` folder and renames them to canonical names:
- `transcript.txt`
- `transcript.srt`
- `transcript.vtt`
- `transcript.json`
- `transcript.tsv`

After import, re-run `python scripts/build.py` so pages show transcripts and download links.

## GitHub Actions

`.github/workflows/ingest_api.yml` ingests and rebuilds pages/nav on a schedule or manually, and commits changes.

`.github/workflows/gh-pages.yml` optionally ingests on push if `YT_API_KEY` is set, then builds and deploys the site.

Ensure your repository's Pages settings are configured to deploy from the `gh-pages` branch if using the included deploy workflow.

## Migrating old catalogs

If you previously stored absolute `path` entries in `data/catalog.json`, run:

```bash
python scripts/fix_catalog_paths.py
```

This converts to the new `rel_path` format relative to `docs/`.
