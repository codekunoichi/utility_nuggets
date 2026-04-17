"""Data models for Jira project audit records."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ProjectRecord:
    """Holds all gathered and computed information for a single Jira project."""

    project_key: str
    project_name: str
    project_type: str
    project_lead: str
    unresolved_issue_count: int
    issues_created_last_n_days: int
    issues_resolved_last_n_days: int
    last_issue_created_at: Optional[datetime]
    last_issue_updated_at: Optional[datetime]
    oldest_unresolved_issue_age_days: Optional[int]
    flow_ratio: Optional[float]
    activity_bucket: str   # "active" | "slow" | "stale" | "overloaded" | "dormant"
    notes: str

    def to_dict(self) -> dict:
        """Serialize to a plain dict suitable for CSV/JSON output."""
        flow_str: str
        if self.flow_ratio is None:
            flow_str = ""
        elif self.flow_ratio == float("inf"):
            flow_str = "inf"
        else:
            flow_str = str(round(self.flow_ratio, 2))

        return {
            "project_key": self.project_key,
            "project_name": self.project_name,
            "project_type": self.project_type,
            "project_lead": self.project_lead,
            "unresolved_issue_count": self.unresolved_issue_count,
            "issues_created_last_30_days": self.issues_created_last_n_days,
            "issues_resolved_last_30_days": self.issues_resolved_last_n_days,
            "last_issue_created_at": (
                self.last_issue_created_at.isoformat()
                if self.last_issue_created_at
                else ""
            ),
            "last_issue_updated_at": (
                self.last_issue_updated_at.isoformat()
                if self.last_issue_updated_at
                else ""
            ),
            "oldest_unresolved_issue_age_days": (
                self.oldest_unresolved_issue_age_days
                if self.oldest_unresolved_issue_age_days is not None
                else ""
            ),
            "flow_ratio": flow_str,
            "activity_bucket": self.activity_bucket,
            "notes": self.notes,
        }
