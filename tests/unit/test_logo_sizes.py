"""Guard against oversized source logos in static/logos.

Logos render at 24px tall (max 100px wide) on every event card, yet a single
6720px KINN logo once weighed 18.7 MB and was pulled by 188 cards. Raster logos
are stored at no more than 300x96 (3x the CSS box), which keeps each one well
under the limit below. LogoScraper.download_logo saves whatever the site
serves, so a newly scraped logo can trip this test: downscale it before
committing.
"""
from pathlib import Path

import pytest

LOGO_DIR = Path(__file__).resolve().parents[2] / "static" / "logos"
MAX_RASTER_BYTES = 64 * 1024
# Vector logos traced from artwork can be path-heavy; the largest today is
# ~200 KB. Anything well past that is likely an embedded bitmap.
MAX_SVG_BYTES = 256 * 1024

LOGOS = sorted(p for p in LOGO_DIR.iterdir() if p.is_file())


def test_logo_dir_not_empty():
    assert LOGOS, f"no logos found in {LOGO_DIR}"


@pytest.mark.parametrize("logo", LOGOS, ids=lambda p: p.name)
def test_logo_is_small(logo):
    limit = MAX_SVG_BYTES if logo.suffix == ".svg" else MAX_RASTER_BYTES
    size = logo.stat().st_size
    assert size <= limit, (
        f"{logo.name} is {size:,} bytes (limit {limit:,}); downscale it to fit "
        f"300x96, e.g. `sips -Z 300 {logo.name}` for PNG/JPEG or "
        f"`cwebp -resize` for WebP"
    )
