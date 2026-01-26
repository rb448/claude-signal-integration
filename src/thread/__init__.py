"""
Thread-to-Project Mapping Module.

Provides persistent storage for Signal thread to project directory associations.
"""

from .mapper import ThreadMapper, ThreadMappingError

__all__ = ["ThreadMapper", "ThreadMappingError"]
