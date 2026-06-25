"""
API utility routes for LA Events Aggregator.
Handles favicon, static file serving, scraper trigger, and database health.
"""
from fasthtml.common import *
from datetime import datetime
import logging

import config
from src.web.state import state as app_state


logger = logging.getLogger(__name__)


def setup_routes(rt, state):
    """Register API/utility routes."""

    @rt('/favicon.ico')
    def favicon():
        """Serve favicon or return 204 No Content if not found."""
        from pathlib import Path
        from starlette.responses import Response

        favicon_path = Path('static/favicon.ico')
        if favicon_path.exists():
            return FileResponse(favicon_path)

        # Return 204 No Content if favicon doesn't exist
        return Response(status_code=204)

    @rt('/static/{filepath:path}')
    def serve_static(filepath: str):
        """Serve static files with path traversal protection."""
        from pathlib import Path
        from starlette.responses import Response
        import os

        # Define the static directory (absolute path)
        static_dir = Path('static').resolve()

        # Resolve the requested file path
        requested_file = (static_dir / filepath).resolve()

        # Security check: ensure the resolved path is within static_dir
        try:
            requested_file.relative_to(static_dir)
        except ValueError:
            # Path traversal attempt detected
            return Response('Forbidden', status_code=403)

        # Check if file exists
        if not requested_file.exists() or not requested_file.is_file():
            return Response('Not Found', status_code=404)

        return FileResponse(requested_file)

    @rt('/api/run-scrapers')
    async def post(request):
        """
        API endpoint to trigger scrapers and sync database to Cloud Storage.
        Used by Cloud Scheduler for automated scraping.
        """
        import subprocess
        import os
        import sys
        from pathlib import Path
        from starlette.responses import JSONResponse

        # In production, require a Google-signed OIDC token from Cloud Scheduler.
        # Locally (ENVIRONMENT != 'production') we bypass auth so it's easy to
        # trigger a run from a dev shell.
        if os.getenv('ENVIRONMENT') == 'production':
            from google.oauth2 import id_token
            from google.auth.transport import requests as google_requests

            expected_sa = os.getenv(
                'SCRAPER_INVOKER_SA',
                'scheduler-invoker@westside-la-events.iam.gserviceaccount.com',
            )

            # Accept the token if its audience matches any configured value OR
            # this request's own URL. Cloud Run services are reachable under
            # multiple hostnames (legacy run.app + new *.a.run.app), and the
            # serving URL can change; pinning a single hardcoded audience meant
            # a URL change silently 401'd every scheduled scrape. SCRAPER_AUDIENCE
            # may be a comma-separated list of explicit overrides.
            accepted_audiences = {
                a.strip()
                for a in os.getenv('SCRAPER_AUDIENCE', '').split(',')
                if a.strip()
            }
            # The scheduler's token audience is the URL it targeted, which is
            # this request's URL (full path) or its base. Add both so we adapt
            # to whatever hostname actually served the request. Behind Cloud
            # Run the scheme may arrive as http (TLS terminated upstream) while
            # the token audience is https, so accept both schemes.
            netloc = request.url.netloc
            path = request.url.path
            for scheme in ('https', 'http'):
                accepted_audiences.add(f"{scheme}://{netloc}")
                accepted_audiences.add(f"{scheme}://{netloc}{path}")

            auth_header = request.headers.get('Authorization', '')
            bearer_prefix = 'Bearer '
            if not auth_header.startswith(bearer_prefix):
                return JSONResponse({'error': 'Unauthorized'}, status_code=401)
            token = auth_header[len(bearer_prefix):].strip()

            try:
                # Verify signature/expiry now; check the audience ourselves
                # against the accepted set below (verify_oauth2_token only takes
                # a single audience string).
                claims = id_token.verify_oauth2_token(
                    token, google_requests.Request()
                )
            except ValueError as e:
                logger.warning(f"OIDC token verification failed: {e}")
                return JSONResponse({'error': 'Unauthorized'}, status_code=401)

            if claims.get('aud') not in accepted_audiences:
                logger.warning(
                    f"OIDC token had wrong audience: aud={claims.get('aud')} "
                    f"not in {sorted(accepted_audiences)}"
                )
                return JSONResponse({'error': 'Unauthorized'}, status_code=401)

            if claims.get('email') != expected_sa or not claims.get('email_verified'):
                logger.warning(
                    f"OIDC token had wrong subject: email={claims.get('email')}"
                )
                return JSONResponse({'error': 'Unauthorized'}, status_code=401)

        try:
            project_root = Path(__file__).resolve().parents[3]

            # GCSFuse mounts /app/data as a Cloud Storage bucket, but SQLite WAL
            # mode needs random-access writes to -shm files which GCSFuse cannot
            # handle (BufferedWriteHandler.OutOfOrderError).  Work around this by
            # scraping into a local /tmp directory and letting the existing gsutil
            # upload in run_scrapers.py push the result back to Cloud Storage.
            # Use SQLite's backup API instead of file copy so any uncheckpointed
            # WAL pages are included in the seed snapshot.
            from src.data.database import Database
            tmp_db = '/tmp/events.db'
            src_db = os.path.join(str(project_root), 'data', 'events.db')
            if os.path.exists(src_db):
                Database.snapshot_db(src_db, tmp_db)

            env = os.environ.copy()
            env['DATABASE_PATH'] = tmp_db

            # Run scrapers synchronously so Cloud Run keeps the instance alive
            # for the full duration.  A background Popen gets killed when Cloud
            # Run scales the instance to zero (~15 min of idle).
            # stdout captures summary for the response body.
            # stderr is inherited so structured JSON logs flow to
            # Cloud Logging with proper severity levels.
            result = subprocess.run(
                [sys.executable, 'run_scrapers.py'],
                stdout=subprocess.PIPE,
                stderr=None,  # inherit — logs go to Cloud Logging
                cwd=str(project_root),
                env=env,
                timeout=3300,  # 55 min (Cloud Run timeout is 3600)
            )

            status = 'success' if result.returncode == 0 else 'error'
            return JSONResponse({
                'status': status,
                'returncode': result.returncode,
                'message': result.stdout.decode('utf-8', errors='replace')[-2000:],
                'timestamp': datetime.now().isoformat()
            }, status_code=200 if result.returncode == 0 else 500)

        except subprocess.TimeoutExpired:
            return JSONResponse({
                'status': 'timeout',
                'message': 'Scrapers timed out after 55 minutes',
                'timestamp': datetime.now().isoformat()
            }, status_code=504)

        except Exception as e:
            return JSONResponse({
                'status': 'error',
                'message': f'Failed to run scrapers: {str(e)}'
            }, status_code=500)

    @rt('/api/health/database')
    async def get_database_health():
        """
        Health check endpoint for database freshness.
        Returns database statistics and age information.
        """
        from starlette.responses import JSONResponse

        try:
            from datetime import datetime, timezone
            import os

            db = state.db

            # Get total event count and most recent update
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM events")
                total_events = cursor.fetchone()[0]

                # Get most recent event update
                cursor.execute("SELECT MAX(updated_at) FROM events")
                most_recent_update = cursor.fetchone()[0]

            # Get database file modification time
            db_path = config.DATABASE_PATH
            db_mtime = None
            db_size = None
            if os.path.exists(db_path):
                db_mtime = datetime.fromtimestamp(os.path.getmtime(db_path), tz=timezone.utc)
                db_size = os.path.getsize(db_path)

            # Calculate age
            now = datetime.now(timezone.utc)
            if db_mtime:
                age_hours = (now - db_mtime).total_seconds() / 3600
            else:
                age_hours = None

            # Determine health status
            health_status = 'healthy'
            warnings = []

            if total_events == 0:
                health_status = 'error'
                warnings.append('Database is empty')
            elif age_hours and age_hours > 48:
                health_status = 'warning'
                warnings.append(f'Database is {age_hours:.1f} hours old (> 48 hours)')

            return JSONResponse({
                'status': health_status,
                'database': {
                    'total_events': total_events,
                    'most_recent_update': most_recent_update,
                    'file_modified': db_mtime.isoformat() if db_mtime else None,
                    'age_hours': round(age_hours, 2) if age_hours else None,
                    'size_bytes': db_size,
                    'size_mb': round(db_size / 1024 / 1024, 2) if db_size else None
                },
                'warnings': warnings,
                'timestamp': now.isoformat()
            })
        except Exception as e:
            from starlette.responses import JSONResponse
            return JSONResponse({
                'status': 'error',
                'message': str(e)
            }, status_code=500)
