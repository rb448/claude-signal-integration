"""
Approval Models - State definitions and data structures.
"""

from enum import Enum


class ApprovalState(Enum):
    """Approval request states"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
