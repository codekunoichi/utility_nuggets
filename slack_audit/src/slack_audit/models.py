"""Data models for Slack channel audit records."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ChannelRecord:
    """Holds all gathered and computed information for a single Slack channel."""

    channel_id: str
    channel_name: str
    channel_type: str          # "public" or "private"
    purpose: str
    topic: str
    member_count: int
    created_at: Optional[datetime]
    last_message_at: Optional[datetime]
    messages_last_n_days: int
    activity_bucket: str       # "active" | "slow" | "stale" | "unclear-purpose"
    notes: str

    def to_dict(self) -> dict:
        """Serialize to a plain dict suitable for CSV/JSON output."""
        return {
            "channel_name": self.channel_name,
            "channel_id": self.channel_id,
            "channel_type": self.channel_type,
            "purpose": self.purpose,
            "topic": self.topic,
            "member_count": self.member_count,
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "last_message_at": self.last_message_at.isoformat() if self.last_message_at else "",
            "messages_last_30_days": self.messages_last_n_days,
            "activity_bucket": self.activity_bucket,
            "notes": self.notes,
        }
