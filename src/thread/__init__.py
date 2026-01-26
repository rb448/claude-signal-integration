"""
Thread-to-Project Mapping Module.

Provides persistent storage for Signal thread to project directory associations.
"""

from .mapper import ThreadMapper, ThreadMapping, ThreadMappingError
from .commands import ThreadCommands

__all__ = [
    "ThreadMapper",
    "ThreadMapping",
    "ThreadMappingError",
    "ThreadCommands"
]
