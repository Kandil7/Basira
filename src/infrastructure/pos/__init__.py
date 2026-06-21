"""
POS connector module — Point of Sale system integration.

Provides adapters for connecting to various POS systems.
"""

from src.infrastructure.pos.base import POSConnector, POSConfig, POSTransaction

__all__ = ["POSConnector", "POSConfig", "POSTransaction"]
