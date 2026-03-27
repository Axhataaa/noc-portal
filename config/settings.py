"""
NOC Portal — settings.py
Backward-compatibility shim.
All real configuration is now in config/config.py.
"""
from .config import Config   # re-export — existing imports still work

__all__ = ['Config']
