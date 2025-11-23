# Codebase Refactoring Analysis

This document identifies opportunities to simplify and refactor the LA Events Aggregator codebase.

## Executive Summary

The codebase is well-structured but has several areas where code duplication, complexity, and maintainability can be improved. Key findings:

- **High Priority**: Scraper registration system, date parsing utilities, filter query building
- **Medium Priority**: Price extraction patterns, error handling consistency, configuration management
- **Low Priority**: Code organization, documentation improvements

---

## 1. Scraper Registration System (HIGH PRIORITY)

### Current State
**File**: `run_scrapers.py` (lines 30-133)

The scraper registration requires:
1. Manual import of each scraper class (50+ imports)
2. Manual mapping in `SCRAPER_MAP` dictionary
3. Maintenance when adding/removing scrapers

```python
# 50+ manual imports
from src.scrapers.santa_monica import SantaMonicaScraper
from src.scrapers.timeout import TimeoutScraper
# ... 48 more imports

# Manual mapping
SCRAPER_MAP = {
    'santa_monica': SantaMonicaScraper,
    'timeout': TimeoutScraper,
    # ... 48 more mappings
}
```

### Refactoring Solution

**Option 1: Auto-discovery via decorator/registry pattern**
```python
# src/scrapers/registry.py
SCRAPER_REGISTRY = {}

def register_scraper(name: str):
    """Decorator to register scrapers automatically."""
    def decorator(cls):
        SCRAPER_REGISTRY[name] = cls
        return cls
    return decorator

# In each scraper file:
@register_scraper('santa_monica')
class SantaMonicaScraper(BaseScraper):
    # ...

# In run_scrapers.py:
from src.scrapers.registry import SCRAPER_REGISTRY
# No manual imports needed!
```

**Option 2: Auto-discovery via module inspection**
```python
# src/scrapers/__init__.py
import importlib
import pkgutil
from .base import BaseScraper

def discover_scrapers():
    """Automatically discover all scraper classes."""
    scrapers = {}
    package = __import__(__name__, fromlist=[''])
    
    for _, module_name, _ in pkgutil.iter_modules(package.__path__):
        if module_name.startswith('_'):
            continue
        module = importlib.import_module(f'{__name__}.{module_name}')
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and 
                issubclass(attr, BaseScraper) and 
                attr != BaseScraper):
                # Extract name from class (e.g., SantaMonicaScraper -> santa_monica)
                name = _class_to_name(attr)
                scrapers[name] = attr
    return scrapers
```

**Benefits**:
- No manual imports needed
- Adding a scraper = create file, no registration step
- Single source of truth
- Reduces `run_scrapers.py` from 425 lines to ~300 lines

---

## 2. Date Parsing Utilities (HIGH PRIORITY)

### Current State

Date parsing logic is duplicated across multiple scrapers:
- `src/scrapers/kcrw.py`: Custom date parsing
- `src/scrapers/iic_la.py`: `_parse_dates()` method
- `src/scrapers/raymond_kabbaz.py`: `_parse_datetime()` method
- `src/scrapers/parks_ca.py`: `_parse_date_text()`, `_extract_date_from_text()`
- `src/scrapers/brightside.py`: `_parse_time_into_date()` method
- Many more scrapers with similar patterns

### Refactoring Solution

**Create centralized date parsing utilities**:
```python
# src/utils/date_parser.py
from datetime import datetime
from dateutil import parser as date_parser
import re
from typing import Optional, Tuple

class DateParser:
    """Centralized date parsing utilities for scrapers."""
    
    @staticmethod
    def parse_date(date_text: str, fuzzy: bool = True) -> Optional[datetime]:
        """Parse date from various text formats."""
        if not date_text:
            return None
        
        try:
            return date_parser.parse(date_text, fuzzy=fuzzy)
        except:
            pass
        
        # Try common patterns
        patterns = [
            r'\w{3,9}\s+\d{1,2},?\s+\d{4}',  # "November 14, 2024"
            r'\d{1,2}\s+\w{3,9}\s+\d{4}',    # "14 November 2024"
            r'\d{1,2}/\d{1,2}/\d{2,4}',      # "11/14/2024"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, date_text)
            if match:
                try:
                    return date_parser.parse(match.group(0))
                except:
                    pass
        
        return None
    
    @staticmethod
    def parse_date_range(date_text: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Parse date range from text like 'Sep 29 - Dec 13, 2025'."""
        # Implementation similar to iic_la._parse_dates()
        pass
    
    @staticmethod
    def parse_time_into_date(time_str: str, base_date: datetime) -> datetime:
        """Parse time string and combine with base date."""
        # Implementation similar to brightside._parse_time_into_date()
        pass
```

**Benefits**:
- Single implementation to maintain
- Consistent date parsing across all scrapers
- Easier to add new date formats
- Reduces code duplication by ~500+ lines

---

## 3. Price Extraction Utilities (MEDIUM PRIORITY)

### Current State

Price extraction logic is repeated in multiple scrapers:
- `src/scrapers/santa_monica.py`: Price regex patterns
- `src/scrapers/kcrw.py`: Price extraction in `_fetch_event_details()`
- Many scrapers check for "free" events with similar patterns

### Refactoring Solution

**Create centralized price extraction**:
```python
# src/utils/price_extractor.py
import re
from typing import Optional, Tuple

class PriceExtractor:
    """Extract price information from text."""
    
    @staticmethod
    def extract_price(text: str) -> Tuple[Optional[float], bool, str]:
        """
        Extract price information from text.
        
        Returns:
            Tuple of (price, is_free, price_note)
        """
        if not text:
            return None, False, ""
        
        text_lower = text.lower()
        
        # Check for free events
        if re.search(r'\bfree\b', text_lower):
            free_context = re.search(
                r'(?:admission|entry|event|price|cost|ticket)?\s*(?:is\s*)?free',
                text_lower
            )
            if free_context:
                return None, True, ""
        
        # Price patterns
        patterns = [
            r'\$(\d+)(?:-\$?(\d+))?',           # $25 or $25-$75
            r'(?:from\s+)?\$(\d+)',             # from $25
            r'(?:ticket(?:s)?|admission)[:is\s]+\$(\d+)',  # tickets: $25
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    price = float(match.group(1))
                    return price, False, ""
                except (ValueError, TypeError, IndexError):
                    continue
        
        return None, False, "Check website for pricing"
```

**Benefits**:
- Consistent price extraction
- Single place to update price patterns
- Reduces duplication

---

## 4. Database Query Building (HIGH PRIORITY)

### Current State

**File**: `src/web/app.py` (lines 772-926)

The `_get_filter_tallies()` function has complex, duplicated SQL query building logic:
- Date filter conditions repeated 3 times (lines 800-822, 874-893, and in `search_events()`)
- Similar WHERE clause building in multiple places
- Geographic filtering logic duplicated

### Refactoring Solution

**Create query builder utility**:
```python
# src/utils/query_builder.py
from typing import List, Optional, Tuple
from datetime import datetime, timedelta

class EventQueryBuilder:
    """Build SQL queries for event filtering."""
    
    def __init__(self):
        self.conditions = []
        self.params = []
        self.base_conditions = ["source IS NOT NULL", "category IS NOT NULL"]
    
    def add_date_filter(self, date_filter: str, specific_date: str = None):
        """Add date filtering conditions."""
        if date_filter == 'specific_date' and specific_date:
            try:
                date_obj = datetime.strptime(specific_date, '%Y-%m-%d')
                end_date = date_obj + timedelta(days=1)
                self.conditions.append("event_date >= ? AND event_date < ?")
                self.params.extend([date_obj, end_date])
            except ValueError:
                self.conditions.append("event_date >= datetime('now')")
        elif date_filter == 'today':
            self.conditions.append("date(substr(event_date, 1, 19)) = date('now', 'localtime')")
        # ... other date filters
        return self
    
    def add_geographic_filter(self):
        """Add Westside geographic filtering."""
        if config.ENABLE_GEOGRAPHIC_FILTERING:
            self.base_conditions.append(
                f"(latitude IS NULL OR (latitude >= {config.WESTSIDE_BOUNDS['min_lat']} "
                f"AND latitude <= {config.WESTSIDE_BOUNDS['max_lat']}))"
            )
            self.base_conditions.append(
                f"(longitude IS NULL OR (longitude >= {config.WESTSIDE_BOUNDS['min_lng']} "
                f"AND longitude <= {config.WESTSIDE_BOUNDS['max_lng']}))"
            )
        return self
    
    def add_category_filter(self, categories: List[str]):
        """Add category filtering."""
        if categories:
            placeholders = ','.join('?' * len(categories))
            self.conditions.append(f"category IN ({placeholders})")
            self.params.extend(categories)
        return self
    
    def build_where_clause(self) -> Tuple[str, List]:
        """Build final WHERE clause."""
        all_conditions = self.base_conditions + self.conditions
        where_clause = " AND ".join(all_conditions)
        return where_clause, self.params
```

**Benefits**:
- Single source of truth for query building
- Eliminates duplication in `_get_filter_tallies()` and `search_events()`
- Easier to test and maintain
- Reduces `app.py` by ~150 lines

---

## 5. Filter Tally Logic Duplication (MEDIUM PRIORITY)

### Current State

**File**: `src/web/app.py` (lines 772-926)

The `_get_filter_tallies()` function has:
- Date filter logic duplicated 3 times (lines 800-822, 874-893, and in `_fetch_events()`)
- Similar query building for categories, sources, and free events

### Refactoring Solution

**Extract to database method**:
```python
# src/data/database.py
def get_filter_tallies(
    self,
    date_filter: str = 'upcoming',
    category: List[str] = None,
    source: List[str] = None,
    free_only: bool = False,
    specific_date: str = None
) -> Tuple[dict, List[Tuple[str, int]], int]:
    """
    Get category counts, source counts, and free events count.
    
    Returns:
        Tuple of (category_counts_dict, source_counts_list, free_events_count)
    """
    # Use EventQueryBuilder to build queries
    # Single implementation, reused by app.py
    pass
```

**Benefits**:
- Moves business logic to database layer
- Eliminates duplication
- Easier to test

---

## 6. Configuration Management (MEDIUM PRIORITY)

### Current State

**File**: `config.py` (427 lines)

The `EVENT_SOURCES` dictionary is very large (315+ lines) and contains:
- Source metadata (name, URL, enabled status)
- Notes and implementation details
- Mixed concerns (configuration vs documentation)

### Refactoring Solution

**Option 1: Split into separate files**
```
config/
  __init__.py          # Main config
  sources.py           # EVENT_SOURCES dict
  api_keys.py          # API key configuration
  geographic.py        # Geographic bounds
```

**Option 2: Use YAML/JSON for sources**
```yaml
# config/sources.yaml
santa_monica:
  name: Santa Monica
  url: https://www.smgov.net/events
  enabled: true
  uses_api: false

timeout:
  name: Timeout LA
  url: https://www.timeout.com/los-angeles/things-to-do/...
  enabled: true
  uses_api: false
```

**Benefits**:
- Easier to read and edit
- Separates configuration from code
- Can be edited by non-developers

---

## 7. Web App Organization (LOW PRIORITY)

### Current State

**File**: `src/web/app.py` (1759 lines)

This file contains:
- Route handlers
- HTML component builders
- Filter logic
- Analytics tracking
- Error handlers
- Static file serving

### Refactoring Solution

**Split into modules**:
```
src/web/
  app.py              # Main app setup, lifespan
  routes/
    __init__.py
    home.py           # Home page route
    events.py         # Event listing routes
    filters.py        # Filter routes
    favorites.py      # Favorite routes
    api.py            # API routes
  components/
    __init__.py
    layout.py         # page_head, page_header, page_footer
    events.py         # event_card, events_list, skeleton_card
    filters.py        # filter_section, filter_tallies
  utils.py            # Helper functions (get_favorites, etc.)
```

**Benefits**:
- Better organization
- Easier to navigate
- Smaller, focused files

---

## 8. Error Handling Consistency (MEDIUM PRIORITY)

### Current State

Error handling is inconsistent across scrapers:
- Some use try/except with logging
- Some use try/except with print statements
- Some return empty lists on error
- Some return None

### Refactoring Solution

**Standardize error handling in BaseScraper**:
```python
# src/scrapers/base.py
def scrape(self) -> List[Event]:
    """Scrape events with standardized error handling."""
    try:
        return self._scrape_impl()
    except Exception as e:
        self.log(f"Scraper error: {e}", level='error')
        # Log to file if configured
        if config.LOG_FILE:
            self._log_to_file(e)
        return []  # Always return list, never None
```

**Benefits**:
- Consistent behavior
- Better error tracking
- Easier debugging

---

## 9. Scraper Base Class Enhancements (MEDIUM PRIORITY)

### Current State

Many scrapers have similar helper methods:
- `_parse_event_card()` - repeated pattern
- `_extract_category()` - similar logic
- `_fetch_event_details()` - similar structure

### Refactoring Solution

**Add common helpers to BaseScraper**:
```python
# src/scrapers/base.py
def extract_price_from_text(self, text: str) -> Tuple[Optional[float], bool]:
    """Extract price using PriceExtractor."""
    return PriceExtractor.extract_price(text)

def parse_date_from_text(self, text: str) -> Optional[datetime]:
    """Parse date using DateParser."""
    return DateParser.parse_date(text)

def extract_category_from_text(self, title: str, description: str, venue: str = "") -> str:
    """Extract category using existing classify_event utility."""
    return classify_event(title, description, venue)
```

**Benefits**:
- Less code in individual scrapers
- Consistent behavior
- Easier to update logic

---

## 10. Database Migration System (LOW PRIORITY)

### Current State

**File**: `src/data/database.py` (lines 106-125)

Migrations are done with try/except blocks:
```python
try:
    cursor.execute("ALTER TABLE events ADD COLUMN source_logo_url TEXT")
except sqlite3.OperationalError:
    pass  # Column already exists
```

### Refactoring Solution

**Create migration system**:
```python
# src/data/migrations.py
class Migration:
    def __init__(self, version: int, description: str):
        self.version = version
        self.description = description
    
    def up(self, conn):
        """Apply migration."""
        pass
    
    def down(self, conn):
        """Rollback migration."""
        pass

# Track migrations in database
# Apply migrations in order
```

**Benefits**:
- Explicit migration history
- Can rollback if needed
- Better documentation

---

## Implementation Priority

### Phase 1 (High Impact, Low Risk)
1. ✅ **Scraper Registration System** - Auto-discovery
2. ✅ **Date Parsing Utilities** - Centralize date parsing
3. ✅ **Database Query Builder** - Eliminate query duplication

### Phase 2 (Medium Impact, Medium Risk)
4. ✅ **Price Extraction Utilities** - Centralize price parsing
5. ✅ **Filter Tally Refactoring** - Move to database layer
6. ✅ **Error Handling Standardization** - Consistent patterns

### Phase 3 (Lower Priority)
7. ✅ **Configuration Management** - Split config files
8. ✅ **Web App Organization** - Split large files
9. ✅ **Base Class Enhancements** - Add common helpers
10. ✅ **Migration System** - Proper migration tracking

---

## Estimated Impact

### Code Reduction
- **Scraper registration**: ~50 lines removed
- **Date parsing**: ~500 lines removed (across scrapers)
- **Query building**: ~150 lines removed
- **Total**: ~700 lines of code eliminated

### Maintainability Improvements
- Single source of truth for common operations
- Easier to add new scrapers
- Consistent error handling
- Better testability

### Risk Assessment
- **Low Risk**: Scraper registration, date parsing, price extraction
- **Medium Risk**: Query builder, filter refactoring
- **Higher Risk**: Web app reorganization (requires careful testing)

---

## Testing Strategy

For each refactoring:
1. Write tests for new utilities before refactoring
2. Refactor one scraper/file at a time
3. Run full test suite after each change
4. Compare output before/after refactoring
5. Monitor production for any regressions

---

## Notes

- Keep backward compatibility during refactoring
- Consider feature flags for gradual rollout
- Document all changes in CHANGELOG.md
- Update documentation as code is refactored


