"""
Configuration module.

Loads settings from environment variables using pydantic-settings.
Single source of truth for all application configuration.
"""

from src.config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
