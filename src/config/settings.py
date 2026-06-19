"""
Application settings loaded from environment variables.

Uses pydantic-settings for type-safe configuration with validation.
All settings are loaded once at startup and cached.

Phase 3: Added Redis, PostgreSQL, and connection pool settings.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Application ───────────────────────────────────────────────────
    app_env: str = "development"
    app_log_level: str = "INFO"
    app_secret_key: str = "change-me-in-production"
    internal_api_key: str = "change-me"

    # ── Groq LLM (groq.com) ──────────────────────────────────────────
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    # ── Qdrant ────────────────────────────────────────────────────────
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "company_docs"

    # ── Odoo ──────────────────────────────────────────────────────────
    odoo_url: str = ""
    odoo_db: str = ""
    odoo_username: str = ""
    odoo_password: str = ""

    # ── n8n ───────────────────────────────────────────────────────────
    n8n_webhook_base: str = ""
    n8n_api_key: str = ""

    # ── Redis (Session Store & Cache) ─────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    redis_session_ttl: int = 3600  # 1 hour
    redis_max_connections: int = 20

    # ── PostgreSQL (Audit Log & Persistence) ──────────────────────────
    database_url: str = "postgresql+asyncpg://basira:basira@localhost:5432/basira"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # ── Connection Pooling ────────────────────────────────────────────
    odoo_pool_size: int = 5
    odoo_pool_timeout: int = 30
    qdrant_pool_size: int = 5

    @property
    def qdrant_url(self) -> str:
        """Full Qdrant URL including port."""
        return f"http://{self.qdrant_host}:{self.qdrant_port}"

    @property
    def odoo_xmlrpc_url(self) -> str:
        """Odoo XML-RPC endpoint URL."""
        return f"{self.odoo_url}/xmlrpc/2/common"

    @property
    def odoo_object_url(self) -> str:
        """Odoo object XML-RPC endpoint URL."""
        return f"{self.odoo_url}/xmlrpc/2/object"

    @property
    def redis_host(self) -> str:
        """Extract host from Redis URL."""
        # redis://localhost:6379/0 -> localhost
        from urllib.parse import urlparse
        parsed = urlparse(self.redis_url)
        return parsed.hostname or "localhost"

    @property
    def redis_port(self) -> int:
        """Extract port from Redis URL."""
        from urllib.parse import urlparse
        parsed = urlparse(self.redis_url)
        return parsed.port or 6379


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings singleton."""
    return Settings()
