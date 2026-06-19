"""
Knowledge Base Module

Manages vector database (LanceDB) and relational database (PostgreSQL) for pattern matching and data storage.
"""

from .lance_db import LanceDBManager
from .pattern_matcher import PatternMatcher

__all__ = ['LanceDBManager', 'PatternMatcher']
