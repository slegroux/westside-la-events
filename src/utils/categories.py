"""
Category classification utility for automatically categorizing events.
Uses keyword matching to assign categories to events.
"""
from typing import List
import config


class CategoryClassifier:
    """Classifier for event categories based on keywords."""

    def __init__(self):
        """Initialize classifier with keyword mappings."""
        # Category priority weights (higher = more important when there's a tie)
        self.category_priorities = {
            'Date Night': 3.0,  # Highest priority for date-worthy events
            'Family': 2.5,      # Family events should override generic categories
            'Theater': 2.0,     # Theater is more specific than generic Music/Art
            'Comedy': 2.0,      # Comedy is more specific than generic Entertainment
            'Film': 2.0,        # Film is more specific than generic Art
            'Tech': 1.5,        # Tech events
            'Music': 1.5,       # Moderate priority
            'Art': 1.5,         # Moderate priority
            'Sports': 1.5,      # Moderate priority
            'Wellness': 1.5,    # Moderate priority
            'Education': 1.5,   # Moderate priority
            'Food & Drink': 1.0,  # Lower priority (often overlaps with Date Night)
            'Nightlife': 1.0,     # Lower priority (often overlaps with Date Night)
            'Community': 1.0,     # Lower priority (generic)
            'Other': 0.5        # Lowest priority
        }

        # Strong date night indicators get bonus weight
        self.date_night_strong_indicators = [
            'romantic', 'date night', 'couples', 'candlelit', 'candlelight',
            'intimate', 'romantic evening', 'prix fixe', 'adults only'
        ]

        # Venue-based category mappings (venues strongly associated with specific categories)
        self.venue_categories = {
            'Music': [
                'kia forum', 'forum', 'hollywood bowl', 'greek theatre', 'troubadour',
                'roxy', 'whisky a go go', 'el rey', 'teragram ballroom', 'echoplex',
                'echo', 'bootleg theater', 'lodge room', 'resident', 'concert hall',
                'music center', 'walt disney concert hall', 'shrine auditorium',
                'hollywood palladium', 'fonda theatre', 'wiltern', 'novo',
                'microsoft theater', 'staples center', 'crypto.com arena',
                'dodger stadium', 'rose bowl', 'banc of california stadium',
                'sofi stadium', 'rose bowl', 'hollywood forever cemetery'
            ],
            'Sports': [
                'staples center', 'crypto.com arena', 'dodger stadium', 'rose bowl',
                'banc of california stadium', 'sofi stadium', 'dignity health sports park',
                'ucla pauley pavilion', 'galen center', 'coliseum'
            ],
            'Theater': [
                'pantages', 'ahmanson', 'mark taper forum', 'geffen playhouse',
                'kirk douglas theatre', 'pasadena playhouse', 'actors gang'
            ],
            'Film': [
                'chinese theatre', 'egyptian theatre', 'vista theatre', 'aero theatre',
                'nuart theatre', 'new beverly cinema', 'arclight', 'vintage cinemas'
            ]
        }

        self.category_keywords = {
            'Music': [
                'concert', 'music', 'band', 'orchestra', 'symphony', 'jazz',
                'rock', 'pop', 'classical', 'opera', 'dj', 'performance',
                'festival', 'live music', 'singing', 'choir', 'recital'
            ],
            'Art': [
                'art', 'gallery', 'exhibition', 'museum', 'painting', 'sculpture',
                'installation', 'artist', 'contemporary art', 'modern art',
                'photography', 'drawing', 'print', 'multimedia', 'visual'
            ],
            'Food & Drink': [
                'food', 'restaurant', 'dining', 'wine', 'beer', 'cocktail',
                'tasting', 'taste', 'culinary', 'cuisine', 'chef', 'cooking',
                'brunch', 'dinner', 'lunch', 'breakfast', 'cafe', 'bar',
                'happy hour', 'foodie', 'food festival'
            ],
            'Sports': [
                'sports', 'game', 'match', 'tournament', 'athletic', 'football',
                'basketball', 'baseball', 'soccer', 'tennis', 'golf', 'running',
                'race', 'marathon', 'cycling', 'swim', 'fitness', 'workout',
                # Team indicators (with context to avoid false positives)
                ' vs ', ' vs. ', ' v. ',
                # LA Sports teams
                'lakers', 'clippers', 'dodgers', 'rams', 'chargers', 'kings',
                'galaxy', 'lafc', 'sparks', 'angels', 'ducks', 'bruins', 'trojans',
                # Common opponent teams (for better detection)
                'warriors', 'celtics', 'heat', 'bulls', 'knicks', 'nets', 'bucks',
                'mavericks', 'nuggets', 'suns', 'trail blazers', 'grizzlies'
            ],
            'Family': [
                'family', 'kids', 'children', 'child', 'youth', 'playground',
                'storytime', 'educational', 'learning', 'workshop for kids',
                'family-friendly', 'all ages', 'parents'
            ],
            'Theater': [
                'theater', 'theatre', 'play', 'drama', 'musical', 'performance',
                'stage', 'acting', 'actor', 'production', 'broadway', 'show'
            ],
            'Comedy': [
                'comedy', 'stand-up', 'comedian', 'improv', 'funny', 'laugh',
                'humor', 'comic'
            ],
            'Film': [
                'film', 'movie', 'cinema', 'screening', 'documentary', 'short film',
                'feature', 'director', 'filmmaker'
            ],
            'Nightlife': [
                'nightlife', 'club', 'dancing', 'dance party', 'night out',
                'late night', 'after dark', 'lounge', 'nightclub'
            ],
            'Wellness': [
                'wellness', 'yoga', 'meditation', 'health', 'fitness', 'mindfulness',
                'spa', 'healing', 'therapy', 'massage', 'relaxation', 'exercise'
            ],
            'Community': [
                'community', 'meeting', 'gathering', 'volunteer', 'charity',
                'fundraiser', 'nonprofit', 'social', 'neighborhood', 'local',
                'civic', 'public'
            ],
            'Education': [
                'lecture', 'talk', 'seminar', 'workshop', 'class', 'course',
                'training', 'educational', 'learning', 'discussion', 'panel',
                'conference', 'symposium', 'presentation'
            ],
            'Date Night': [
                'romantic', 'date night', 'couples', 'wine tasting', 'wine', 'rooftop',
                'candlelit', 'candlelight', 'dinner and', 'evening', 'intimate',
                'upscale', 'cocktails', 'lounge', 'sunset', 'live jazz', 'acoustic',
                '21+', 'adults only', 'sophisticated', 'elegant', 'prix fixe',
                'date', 'romantic evening', 'cozy', 'ambient', 'live music and',
                'wine and', 'wine bar', 'wine club', 'dinner show', 'nightcap', 'moonlight',
                'cocktail bar', 'speakeasy', 'jazz night', 'date spot', 'perfect for couples',
                'romantic atmosphere', 'dimly lit', 'cozy atmosphere'
            ],
            'Tech': [
                'tech', 'technology', 'startup', 'ai', 'artificial intelligence', 'machine learning',
                'ml', 'software', 'developer', 'programming', 'coding', 'hackathon',
                'blockchain', 'crypto', 'web3', 'saas', 'product', 'vc', 'venture capital',
                'founder', 'entrepreneur', 'innovation', 'digital', 'app', 'platform',
                'data science', 'cloud', 'cybersecurity', 'tech meetup', 'networking',
                'pitch', 'demo day', 'techstars', 'y combinator', 'accelerator', 'incubator',
                'silicon beach', 'tech industry', 'engineering', 'design thinking', 'ux',
                'ui', 'product management', 'agile', 'devops', 'api', 'open source'
            ]
        }

    def classify(self, title: str, description: str = '', venue: str = '') -> str:
        """
        Classify an event into a category using weighted scoring.

        Args:
            title: Event title
            description: Event description
            venue: Venue name

        Returns:
            Category name or 'Other' if no match found
        """
        # Combine all text and convert to lowercase
        text = f"{title} {description} {venue}".lower()
        venue_lower = venue.lower()

        # Check venue-based categorization first (strong signal)
        # Give venue matches a high score to ensure they take priority
        venue_bonus = {}
        for category, venue_names in self.venue_categories.items():
            for venue_name in venue_names:
                if venue_name in venue_lower:
                    # Venue match gets a strong bonus (equivalent to 5 keyword matches)
                    venue_bonus[category] = 5.0
                    break  # Only need one match per category

        # Score each category with keyword matches
        raw_scores = {}
        for category, keywords in self.category_keywords.items():
            score = sum(1 for keyword in keywords if keyword.lower() in text)
            # Add venue bonus if this category has one
            if category in venue_bonus:
                score += venue_bonus[category]
            if score > 0:
                raw_scores[category] = score

        # Apply priority weighting to raw scores
        weighted_scores = {}
        for category, raw_score in raw_scores.items():
            priority = self.category_priorities.get(category, 1.0)
            weighted_scores[category] = raw_score * priority

        # Apply Date Night bonus for strong indicators
        if 'Date Night' in weighted_scores:
            has_strong_indicator = any(
                indicator in text for indicator in self.date_night_strong_indicators
            )
            if has_strong_indicator:
                # Add significant bonus for strong date night indicators
                weighted_scores['Date Night'] += 5.0

        # Return category with highest weighted score
        if weighted_scores:
            return max(weighted_scores.items(), key=lambda x: x[1])[0]

        return 'Other'

    def classify_multiple(
        self,
        title: str,
        description: str = '',
        venue: str = '',
        threshold: int = 2
    ) -> List[str]:
        """
        Classify an event into multiple categories.

        Args:
            title: Event title
            description: Event description
            venue: Venue name
            threshold: Minimum keyword matches to include category

        Returns:
            List of category names
        """
        text = f"{title} {description} {venue}".lower()

        categories = []
        for category, keywords in self.category_keywords.items():
            score = sum(1 for keyword in keywords if keyword.lower() in text)
            if score >= threshold:
                categories.append(category)

        return categories if categories else ['Other']

    def add_keyword(self, category: str, keyword: str):
        """
        Add a keyword to a category.

        Args:
            category: Category name
            keyword: Keyword to add
        """
        if category not in self.category_keywords:
            self.category_keywords[category] = []
        if keyword.lower() not in [k.lower() for k in self.category_keywords[category]]:
            self.category_keywords[category].append(keyword.lower())


# Global classifier instance
_classifier = None


def get_classifier() -> CategoryClassifier:
    """Get or create the global category classifier instance."""
    global _classifier
    if _classifier is None:
        _classifier = CategoryClassifier()
    return _classifier


def classify_event(title: str, description: str = '', venue: str = '') -> str:
    """
    Convenience function to classify an event.

    Args:
        title: Event title
        description: Event description
        venue: Venue name

    Returns:
        Category name
    """
    classifier = get_classifier()
    return classifier.classify(title, description, venue)
