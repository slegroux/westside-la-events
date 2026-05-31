"""One-off: fetch CC0 / Public-Domain stock photo *candidates* into staging.

Source: Wikimedia Commons (open API, no key). We filter to CC0 / Public-Domain
files only -> commercial use OK, no attribution required. We pull several
candidates per theme; a human (Claude) then eyeballs a contact sheet and keeps
the best few. Kept images are optimized separately and self-hosted.
"""
import json
import os
import time
import requests

STAGING = "static/stock/_staging"
# Wikimedia requires a descriptive UA with contact info.
UA = "westside-la-events/1.0 (https://westside-events; stock photo curation)"
API = "https://commons.wikimedia.org/w/api.php"

# theme -> Commons search string. filetype:bitmap avoids diagrams/SVGs.
THEMES = {
    "music":     "live music concert performance filetype:bitmap",
    "nightlife": "bar lounge cocktail nightlife filetype:bitmap",
    "art":       "art gallery exhibition museum filetype:bitmap",
    "theater":   "theatre stage performance filetype:bitmap",
    "food":      "farmers market produce food filetype:bitmap",
    "comedy":    "comedy stand-up microphone stage filetype:bitmap",
    "sports":    "sports running outdoor recreation filetype:bitmap",
    "wellness":  "yoga wellness fitness studio filetype:bitmap",
    "family":    "family children park playground filetype:bitmap",
    "learning":  "library books lecture reading filetype:bitmap",
    "film":      "cinema movie theater screening filetype:bitmap",
    "tech":      "technology conference computer filetype:bitmap",
    "other":     "Santa Monica Los Angeles beach filetype:bitmap",
}
PER_THEME = 8


def _is_free(license_short):
    lc = (license_short or "").lower()
    return "cc0" in lc or "public domain" in lc or lc in ("pd", "no restrictions")


def fetch_theme(theme, query):
    out_dir = os.path.join(STAGING, theme)
    os.makedirs(out_dir, exist_ok=True)
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,           # File:
        "gsrlimit": 40,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|size|mime",
        "iiurlwidth": 1280,          # downscaled thumb -> efficient download
    }
    r = requests.get(API, params=params, headers={"User-Agent": UA}, timeout=40)
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    kept = []
    for page in pages.values():
        if len(kept) >= PER_THEME:
            break
        info = (page.get("imageinfo") or [{}])[0]
        mime = info.get("mime", "")
        if mime not in ("image/jpeg", "image/png"):
            continue
        if (info.get("width") or 0) < 900:
            continue
        ext = info.get("extmetadata", {})
        lic = (ext.get("LicenseShortName", {}) or {}).get("value", "")
        if not _is_free(lic):
            continue
        dl_url = info.get("thumburl") or info.get("url")
        if not dl_url:
            continue
        try:
            ir = requests.get(dl_url, headers={"User-Agent": UA}, timeout=40)
            ct = ir.headers.get("content-type", "")
            if ir.status_code != 200 or not ct.startswith("image/") or len(ir.content) < 12000:
                continue
        except Exception:
            continue
        idx = len(kept)
        fext = "png" if "png" in ct else "jpg"
        fname = f"{idx:02d}.{fext}"
        with open(os.path.join(out_dir, fname), "wb") as f:
            f.write(ir.content)
        kept.append({
            "file": f"{theme}/{fname}",
            "source": "wikimedia_commons",
            "license": lic,
            "title": page.get("title"),
            "descriptionurl": info.get("descriptionurl"),
            "origin_url": dl_url,
            "width": info.get("width"),
            "height": info.get("height"),
        })
        time.sleep(0.2)
    return kept


def main():
    os.makedirs(STAGING, exist_ok=True)
    manifest = {}
    for theme, query in THEMES.items():
        try:
            kept = fetch_theme(theme, query)
        except Exception as e:
            print(f"{theme:10} ERROR {e}")
            kept = []
        manifest[theme] = kept
        print(f"{theme:10} {len(kept)} candidates")
        time.sleep(1.0)
    with open(os.path.join(STAGING, "candidates.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print("staged ->", STAGING)


if __name__ == "__main__":
    main()
