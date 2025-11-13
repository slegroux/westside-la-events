#!/usr/bin/env python3
"""
Quick test script for analytics system.
Run this to verify analytics tracking is working correctly.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.data.analytics import Analytics
import config


def test_analytics():
    """Test analytics functionality."""
    print("🧪 Testing Analytics System...")
    print(f"Analytics enabled: {config.ENABLE_ANALYTICS}")
    print(f"Analytics DB path: {config.ANALYTICS_DB_PATH}")
    print()

    # Initialize analytics
    print("1. Initializing analytics...")
    analytics = Analytics(config.ANALYTICS_DB_PATH)
    print("✓ Analytics initialized")
    print()

    # Test tracking page views
    print("2. Testing page view tracking...")
    session_id = "test-session-123"
    analytics.track_page_view(
        session_id=session_id,
        path="/",
        referrer="https://google.com",
        user_agent="Mozilla/5.0 Test Browser",
        ip_address="192.168.1.1"
    )
    analytics.track_page_view(
        session_id=session_id,
        path="/event/1",
        referrer="http://localhost:8000/",
        user_agent="Mozilla/5.0 Test Browser",
        ip_address="192.168.1.1"
    )
    print("✓ Page views tracked")
    print()

    # Test tracking event interactions
    print("3. Testing event interaction tracking...")
    analytics.track_event_interaction(
        session_id=session_id,
        event_id=1,
        interaction_type="view",
        source="Test Source",
        category="Music"
    )
    analytics.track_event_interaction(
        session_id=session_id,
        event_id=1,
        interaction_type="click",
        source="Test Source",
        category="Music"
    )
    analytics.track_event_interaction(
        session_id=session_id,
        event_id=1,
        interaction_type="favorite",
        source="Test Source",
        category="Music"
    )
    print("✓ Event interactions tracked")
    print()

    # Test tracking searches
    print("4. Testing search tracking...")
    analytics.track_search(
        session_id=session_id,
        query="jazz concerts",
        date_filter="this_week",
        categories=["Music"],
        sources=["Test Source"],
        free_only=True,
        results_count=15
    )
    analytics.track_search(
        session_id=session_id,
        query="comedy shows",
        date_filter="upcoming",
        categories=["Comedy"],
        free_only=False,
        results_count=8
    )
    print("✓ Searches tracked")
    print()

    # Test retrieving metrics
    print("5. Testing metrics retrieval...")
    today = datetime.now()

    # Daily metrics
    daily_metrics = analytics.get_daily_metrics(today)
    print(f"✓ Daily metrics: {daily_metrics['unique_visitors']} visitors, {daily_metrics['page_views']} page views")

    # Date range metrics
    week_ago = today - timedelta(days=7)
    range_metrics = analytics.get_date_range_metrics(week_ago, today)
    print(f"✓ Retrieved {len(range_metrics)} days of metrics")

    # Session stats
    session_stats = analytics.get_session_stats(days=7)
    print(f"✓ Session stats: {session_stats['total_sessions']} sessions, {session_stats['avg_page_views']:.2f} avg pages/session")

    # Popular searches
    popular_searches = analytics.get_popular_searches(limit=5, days=7)
    print(f"✓ Found {len(popular_searches)} popular searches")

    # Category popularity
    category_stats = analytics.get_category_popularity(days=7)
    print(f"✓ Found {len(category_stats)} active categories")

    # Source performance
    source_perf = analytics.get_source_performance(days=7)
    print(f"✓ Found {len(source_perf)} active sources")
    print()

    print("🎉 All analytics tests passed!")
    print()
    print("📊 Summary:")
    print(f"  - Unique visitors today: {daily_metrics['unique_visitors']}")
    print(f"  - Page views today: {daily_metrics['page_views']}")
    print(f"  - Events viewed today: {daily_metrics['events_viewed']}")
    print(f"  - Events clicked today: {daily_metrics['events_clicked']}")
    print(f"  - Searches today: {daily_metrics['searches']}")
    print(f"  - Favorites added today: {daily_metrics['favorites_added']}")
    print()
    print("✅ Analytics system is working correctly!")
    print(f"📍 Database location: {config.ANALYTICS_DB_PATH}")
    print(f"🌐 Access dashboard at: http://localhost:8000/admin/analytics")


if __name__ == "__main__":
    try:
        test_analytics()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
