#!/usr/bin/env python3
"""
Quick test script to verify the setup is working correctly.
"""
import sys
from pathlib import Path

def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")
    try:
        import config
        from src.data.database import Database
        from src.data.models import Event
        from src.scrapers.base import BaseScraper
        from src.scrapers.santa_monica import SantaMonicaScraper
        from src.scrapers.timeout import TimeoutScraper
        from src.scrapers.kcrw import KCRWScraper
        from src.utils.geocoding import GeocodingService
        from src.utils.categories import CategoryClassifier
        from src.search.query import EventSearch
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def test_database():
    """Test database creation and operations."""
    print("\nTesting database...")
    try:
        from src.data.database import Database
        from src.data.models import Event
        from datetime import datetime

        # Create test database
        db = Database(':memory:')

        # Create test event
        event = Event(
            title="Test Event",
            description="This is a test event",
            venue_name="Test Venue",
            address="123 Test St, Los Angeles, CA",
            event_date=datetime.now(),
            category="Music",
            source="Test"
        )

        # Insert event
        event_id = db.insert_event(event)
        if not event_id:
            print("✗ Failed to insert event")
            return False

        # Retrieve event
        retrieved = db.get_event(event_id)
        if not retrieved:
            print("✗ Failed to retrieve event")
            return False

        if retrieved.title != "Test Event":
            print("✗ Event data mismatch")
            return False

        print("✓ Database operations successful")
        return True

    except Exception as e:
        print(f"✗ Database error: {e}")
        return False

def test_category_classifier():
    """Test category classification."""
    print("\nTesting category classifier...")
    try:
        from src.utils.categories import classify_event

        # Test music event
        category = classify_event("Live Jazz Concert", "Amazing jazz performance", "Music Hall")
        if category != "Music":
            print(f"✗ Expected 'Music', got '{category}'")
            return False

        # Test art event
        category = classify_event("Art Exhibition", "Contemporary art gallery show", "Museum")
        if category != "Art":
            print(f"✗ Expected 'Art', got '{category}'")
            return False

        print("✓ Category classifier working")
        return True

    except Exception as e:
        print(f"✗ Classifier error: {e}")
        return False

def test_config():
    """Test configuration."""
    print("\nTesting configuration...")
    try:
        import config

        # Check required settings
        if not hasattr(config, 'DATABASE_PATH'):
            print("✗ DATABASE_PATH not configured")
            return False

        if not hasattr(config, 'CATEGORIES'):
            print("✗ CATEGORIES not configured")
            return False

        if not hasattr(config, 'EVENT_SOURCES'):
            print("✗ EVENT_SOURCES not configured")
            return False

        print("✓ Configuration loaded successfully")

        # Check API keys
        if not config.GOOGLE_MAPS_API_KEY:
            print("⚠️  Warning: GOOGLE_MAPS_API_KEY not set (map view will not work)")

        if not config.GOOGLE_GEOCODING_API_KEY:
            print("⚠️  Warning: GOOGLE_GEOCODING_API_KEY not set (geocoding will not work)")

        return True

    except Exception as e:
        print(f"✗ Config error: {e}")
        return False

def test_file_structure():
    """Test that all required files and directories exist."""
    print("\nTesting file structure...")

    required_files = [
        'config.py',
        'requirements.txt',
        '.env.example',
        'README.md',
        'CLAUDE.md',
        'PLAN.md',
        'run_scrapers.py',
        'src/data/database.py',
        'src/data/models.py',
        'src/scrapers/base.py',
        'src/web/app.py',
        'static/css/style.css',
        'static/js/map.js'
    ]

    required_dirs = [
        'src/data',
        'src/scrapers',
        'src/utils',
        'src/search',
        'src/web',
        'static/css',
        'static/js'
    ]

    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)

    missing_dirs = []
    for dir_path in required_dirs:
        if not Path(dir_path).exists():
            missing_dirs.append(dir_path)

    if missing_files:
        print(f"✗ Missing files: {', '.join(missing_files)}")
        return False

    if missing_dirs:
        print(f"✗ Missing directories: {', '.join(missing_dirs)}")
        return False

    print("✓ All required files and directories exist")
    return True

def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("LA Events Aggregator - Setup Test")
    print("="*60)

    tests = [
        ("File Structure", test_file_structure),
        ("Imports", test_imports),
        ("Configuration", test_config),
        ("Database", test_database),
        ("Category Classifier", test_category_classifier)
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ {test_name} failed with exception: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")

    print("\n" + "="*60)
    print(f"Results: {passed}/{total} tests passed")
    print("="*60)

    if passed == total:
        print("\n✓ All tests passed! Your setup is ready.")
        print("\nNext steps:")
        print("1. Add Google API keys to .env file")
        print("2. Run scrapers: python run_scrapers.py")
        print("3. Start server: python src/web/app.py")
        return 0
    else:
        print("\n✗ Some tests failed. Please review the errors above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
