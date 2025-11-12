"""
Database models for the LA Events Aggregator.
"""
from datetime import datetime
from typing import Optional


class Event:
    """Event model representing a single event."""

    def __init__(
        self,
        id: Optional[int] = None,
        title: str = "",
        description: str = "",
        venue_name: str = "",
        address: str = "",
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        event_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        category: str = "",
        source: str = "",
        url: str = "",
        image_url: str = "",
        source_logo_url: str = "",
        price: Optional[float] = None,
        is_free: bool = False,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ):
        self.id = id
        self.title = title
        self.description = description
        self.venue_name = venue_name
        self.address = address
        self.latitude = latitude
        self.longitude = longitude
        self.event_date = event_date
        self.end_date = end_date
        self.category = category
        self.source = source
        self.url = url
        self.image_url = image_url
        self.source_logo_url = source_logo_url
        self.price = price
        self.is_free = is_free
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()

    def to_dict(self) -> dict:
        """Convert event to dictionary."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'venue_name': self.venue_name,
            'address': self.address,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'event_date': self.event_date.isoformat() if self.event_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'category': self.category,
            'source': self.source,
            'url': self.url,
            'image_url': self.image_url,
            'source_logo_url': self.source_logo_url,
            'price': self.price,
            'is_free': self.is_free,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    @staticmethod
    def from_dict(data: dict) -> 'Event':
        """Create Event from dictionary."""
        return Event(
            id=data.get('id'),
            title=data.get('title', ''),
            description=data.get('description', ''),
            venue_name=data.get('venue_name', ''),
            address=data.get('address', ''),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            event_date=datetime.fromisoformat(data['event_date']) if data.get('event_date') else None,
            end_date=datetime.fromisoformat(data['end_date']) if data.get('end_date') else None,
            category=data.get('category', ''),
            source=data.get('source', ''),
            url=data.get('url', ''),
            image_url=data.get('image_url', ''),
            source_logo_url=data.get('source_logo_url', ''),
            price=data.get('price'),
            is_free=data.get('is_free', False),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None
        )
