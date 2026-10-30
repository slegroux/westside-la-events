"""Root-level site files: robots.txt, sitemap.xml and the icons browsers request unprompted."""
from pathlib import Path

from starlette.responses import FileResponse, PlainTextResponse, Response

import config

STATIC = Path(__file__).resolve().parents[3] / 'static'


ROOT_PATHS = ('/robots.txt', '/sitemap.xml', '/favicon.ico', '/apple-touch-icon.png')


def setup_routes(app, rt):
    """Register robots.txt, sitemap.xml and root icon routes."""

    @rt('/robots.txt')
    def robots_txt():
        return PlainTextResponse(
            'User-agent: *\n'
            'Disallow: /admin/\n'
            'Disallow: /api/\n'
            f'Sitemap: {config.SITE_URL}/sitemap.xml\n'
        )

    @rt('/sitemap.xml')
    def sitemap_xml():
        # Only the home page: /event/{id} pages are thin and short-lived.
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f'<url><loc>{config.SITE_URL}/</loc><changefreq>daily</changefreq></url>'
            '</urlset>\n'
        )
        return Response(body, media_type='application/xml')

    @rt('/favicon.ico')
    def favicon_ico():
        return FileResponse(STATIC / 'favicon.ico', media_type='image/x-icon')

    @rt('/apple-touch-icon.png')
    def apple_touch_icon():
        return FileResponse(STATIC / 'images' / 'apple-touch-icon.png', media_type='image/png')

    # FastHTML mounts a static-file catch-all (`/{fname:path}.{ext}`) first; it
    # 404s on files absent from the project root, so these must precede it.
    ours = [r for r in app.routes if getattr(r, 'path', None) in ROOT_PATHS]
    for route in reversed(ours):
        app.routes.remove(route)
        app.routes.insert(0, route)
