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
                'race', 'marathon', 'cycling', 'swim', 'fitness', 'workout'
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
                'romantic', 'date night', 'couples', 'wine tasting', 'rooftop',
                'candlelit', 'candlelight', 'dinner and', 'evening', 'intimate',
                'upscale', 'cocktails', 'lounge', 'sunset', 'live jazz', 'acoustic',
                '21+', 'adults only', 'sophisticated', 'elegant', 'prix fixe',
                'date', 'romantic evening', 'cozy', 'ambient', 'live music and',
                'wine and', 'dinner show', 'nightcap', 'moonlight'
            ]
        }

    def classify(self, title: str, description: str = '', venue: str = '') -> str:
        """
        Classify an event into a category.

        Args:
            title: Event title
            description: Event description
            venue: Venue name

        Returns:
            Category name or 'Other' if no match found
        """
        # Combine all text and convert to lowercase
        text = f"{title} {description} {venue}".lower()

        # Score each category
        scores = {}
        for category, keywords in self.category_keywords.items():
            score = sum(1 for keyword in keywords if keyword.lower() in text)
            if score > 0:
                scores[category] = score

        # Return category with highest score
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]

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
