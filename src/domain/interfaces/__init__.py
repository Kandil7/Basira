"""Domain interfaces — abstract contracts for infrastructure implementations."""

from src.domain.interfaces.odoo_client import OdooClientInterface
from src.domain.interfaces.vector_store import VectorStoreInterface

__all__ = ["OdooClientInterface", "VectorStoreInterface"]
