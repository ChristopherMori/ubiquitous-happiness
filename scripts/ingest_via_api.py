#!/usr/bin/env python3
# scripts/ingest_via_api.py
import os, sys, json, time, re
from pathlib import Path
import requests, yaml

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
VID_ROOT = DOCS / "videos"
DATA = ROOT / "data"
VID_ROOT.mkdir(parents=True, exist_ok=True)
DATA.mkdir(parents=True, exist_ok=True)

API_KEY = os.environ.get("YT_API_KEY") or ""
BASE = "https://www.googleapis.com/youtube/v3"

def req(path, **params):
    params["key"] = API_KEY
    r = requests.get(f"{BASE}/{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def slugify(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", (s or "")).strip().lower()
    s = re.sub(r"[\s_]+", "-", s)
    return s[:120] or "video"

def iso8601_duration_to_hms(iso: str) -> str:
    if not iso: return ""
    hours = minutes = seconds = 0
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if m:
        hours = int(m.group(1) or 0)
        minutes = int(m.group(2) or 0)
        seconds = int(m.group(3) or 0)
    total = hours*3600 + minutes*60 + seconds
    h, rem = divmod(total, 3600)
    m2, s2 = divmod(rem, 60)
    return f"{h}:{m2:02d}:{s2:02d}" if h else f"{m2}:{s2:02d}"

def load_catalog():
    p = DATA / "catalog.json"
    if p.exists(): return json.loads(p.read_text(encoding="utf-8"))
    return {"videos": []}

def save_catalog(cat):
    (DATA / "catalog.json").write_text(json.dumps(cat, indent=2, ensure_ascii=False), encoding="utf-8")

def get_uploads_playlist_id(handle: str) -> str:
    j = req("channels", part="contentDetails", forHandle=handle)
    items = j.get("items", [])
    if not items:
        raise SystemExit(f"No channel found for handle {handle}")
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

def iter_playlist_items(playlist_id: str):
    page = None
    while True:
        j = req("playlistItems", part="snippet,contentDetails", playlistId=playlist_id,
                maxResults=50, pageToken=page or "")
        for it in j.get("items", []):
            sn = it.get("snippet", {})
            cd = it.get("contentDetails", {})
            vid = cd.get("videoId") or (sn.get("resourceId") or {}).get("videoId")
            if vid:
                yield {
                    "videoId": vid,
                    "title": sn.get("title"),
                    "publishedAt": sn.get("publishedAt"),
                    "thumbs": sn.get("thumbnails") or {},
                    "description": sn.get("description") or "",
                    "channelTitle": sn.get("channelTitle") or "",
                    "tags": sn.get("tags") or []
                }
        page = j.get("nextPageToken")
        if not page: break
        time.sleep(0.15)

def chunked(seq, n):
    buf=[]
    for x in seq:
        buf.append(x)
        if len(buf)>=n:
            yield buf; buf=[]
    if buf: yield buf

def videos_list(ids):
    if not ids: return {}
    j = req("videos",
            part="snippet,contentDetails,statistics,topicDetails",
            id=",".join(ids))
    by_id = {}
    for it in j.get("items", []):
        by_id[it["id"]] = it
    return by_id

def pick_thumb_url(thumbs: dict) -> str:
    order = ["maxres","standard","high","medium","default"]
    for k in order:
        u = (thumbs.get(k) or {}).get("url")
        if u: return u
    return ""

def download_thumb(url: str, out: Path):
    if not url: return
    r = requests.get(url, timeout=30)
    if r.ok:
        out.write_bytes(r.content)

def write_metadata(folder: Path, meta: dict):
    (folder / "metadata.yml").write_text(
        yaml.safe_dump(meta, sort_keys=False, allow_unicode=True),
        encoding="utf-8"
    )

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/ingest_via_api.py @UAPGerb")
        sys.exit(2)
    if not API_KEY:
        print("Set YT_API_KEY env var")
        sys.exit(2)

    handle = sys.argv[1]
    uploads_pl = get_uploads_playlist_id(handle)
    rows = list(iter_playlist_items(uploads_pl))

    id_seq = [r["videoId"] for r in rows]
    details = {}
    for chunk in chunked(id_seq, 50):
        details.update(videos_list(chunk))
        time.sleep(0.15)

    catalog = load_catalog()
    seen = {v["id"] for v in catalog["videos"]}

    added=0
    for r in rows:
        vid = r["videoId"]
        d = details.get(vid, {})
        sn = d.get("snippet", {})
        cd = d.get("contentDetails", {})
        title = sn.get("title") or r["title"] or f"video-{vid}"
        slug = slugify(title)
        folder = VID_ROOT / f"{vid}-{slug}"
        folder.mkdir(parents=True, exist_ok=True)

        raw = {"fromPlaylist": r, "videosList": d}
        (folder / "youtube.info.json").write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")

        duration_iso = (cd or {}).get("duration","")
        duration = iso8601_duration_to_hms(duration_iso)

        meta = {
            "title": title,
            "youtube_id": vid,
            "date_published": (sn.get("publishedAt") or r["publishedAt"] or "")[:10],
            "duration": duration,
            "channel": sn.get("channelTitle") or r["channelTitle"],
            "tags": sn.get("tags") or r["tags"],
            "categories": sn.get("categoryId") and [sn["categoryId"]] or [],
            "description": sn.get("description") or r["description"] or "",
            "links": {"youtube": f"https://youtu.be/{vid}"}
        }
        write_metadata(folder, meta)

        turl = pick_thumb_url((sn.get("thumbnails") or {}) or r["thumbs"])
        if turl:
            out = folder / "thumb.jpg"
            if not out.exists():
                try: download_thumb(turl, out)
                except Exception: pass

        if vid not in seen:
            # Store rel_path relative to docs/ for portability
            rel_path = (folder.relative_to(DOCS)).as_posix()
            catalog["videos"].append({
                "id": vid,
                "slug": slug,
                "rel_path": rel_path,
                "title": title,
                "date_published": meta["date_published"],
                "duration": duration
            })
            added += 1

    id_to_entry = {v["id"]: v for v in catalog["videos"]}
    ordered = []
    for vid in id_seq:
        if vid in id_to_entry:
            ordered.append(id_to_entry[vid])
    catalog["videos"] = ordered
    save_catalog(catalog)
    print(f"New videos stubbed: {added}")

if __name__ == "__main__":
    main()
