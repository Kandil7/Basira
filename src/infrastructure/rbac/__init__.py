"""
RBAC — Role-Based Access Control for API endpoints and agent operations.

Provides role-based permissions, endpoint protection, and agent operation authorization.
"""

from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class Role(Enum):
    """User roles."""
    ADMIN = "admin"           # Full access
    MANAGER = "manager"       # Analytics, reports, CX
    ANALYST = "analyst"       # Analytics only
    OPERATOR = "operator"     # Operations, internal tools
    VIEWER = "viewer"         # Read-only access
    API = "api"               # API-only access (n8n, integrations)


class Permission(Enum):
    """System permissions."""
    CHAT = "chat"
    ANALYTICS_READ = "analytics:read"
    ANALYTICS_WRITE = "analytics:write"
    CX_READ = "cx:read"
    CX_WRITE = "cx:write"
    PRICING_READ = "pricing:read"
    PRICING_WRITE = "pricing:write"
    SUPPLY_CHAIN_READ = "supply_chain:read"
    SUPPLY_CHAIN_WRITE = "supply_chain:write"
    DOCUMENTS_READ = "documents:read"
    DOCUMENTS_WRITE = "documents:write"
    ADMIN = "admin"
    METRICS = "metrics"


# Role → Permissions mapping
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: set(Permission),  # All permissions
    Role.MANAGER: {
        Permission.CHAT,
        Permission.ANALYTICS_READ,
        Permission.CX_READ,
        Permission.CX_WRITE,
        Permission.PRICING_READ,
        Permission.SUPPLY_CHAIN_READ,
        Permission.DOCUMENTS_READ,
        Permission.METRICS,
    },
    Role.ANALYST: {
        Permission.CHAT,
        Permission.ANALYTICS_READ,
        Permission.PRICING_READ,
        Permission.DOCUMENTS_READ,
    },
    Role.OPERATOR: {
        Permission.CHAT,
        Permission.ANALYTICS_READ,
        Permission.CX_READ,
        Permission.SUPPLY_CHAIN_READ,
        Permission.SUPPLY_CHAIN_WRITE,
        Permission.DOCUMENTS_READ,
        Permission.DOCUMENTS_WRITE,
    },
    Role.VIEWER: {
        Permission.CHAT,
    },
    Role.API: {
        Permission.CHAT,
        Permission.CX_READ,
        Permission.DOCUMENTS_READ,
    },
}


class User:
    """User with role and permissions."""

    def __init__(
        self,
        user_id: str,
        role: Role,
        name: str | None = None,
        extra_permissions: set[Permission] | None = None,
    ) -> None:
        self.user_id = user_id
        self.role = role
        self.name = name or user_id
        self._extra_permissions = extra_permissions or set()

    @property
    def permissions(self) -> set[Permission]:
        """Get all permissions for this user."""
        base = ROLE_PERMISSIONS.get(self.role, set())
        return base | self._extra_permissions

    def has_permission(self, permission: Permission) -> bool:
        """Check if user has a specific permission."""
        return permission in self.permissions

    def has_any_permission(self, permissions: list[Permission]) -> bool:
        """Check if user has any of the given permissions."""
        return any(p in self.permissions for p in permissions)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "role": self.role.value,
            "name": self.name,
            "permissions": [p.value for p in self.permissions],
        }


class RBACMiddleware:
    """
    RBAC middleware for FastAPI.

    Validates user permissions for API endpoints.
    """

    def __init__(self) -> None:
        self._users: dict[str, User] = {}
        self._endpoint_permissions: dict[str, set[Permission]] = {}

        # Register default users
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register default users."""
        self.add_user(User("admin", Role.ADMIN, "Administrator"))
        self.add_user(User("manager", Role.MANAGER, "Operations Manager"))
        self.add_user(User("analyst", Role.ANALYST, "Data Analyst"))
        self.add_user(User("operator", Role.OPERATOR, "Operations Staff"))
        self.add_user(User("viewer", Role.VIEWER, "Read-only User"))
        self.add_user(User("n8n", Role.API, "n8n Automation"))

    def add_user(self, user: User) -> None:
        """Add a user."""
        self._users[user.user_id] = user

    def get_user(self, user_id: str) -> User | None:
        """Get a user by ID."""
        return self._users.get(user_id)

    def register_endpoint(
        self,
        path: str,
        method: str,
        permissions: list[Permission],
    ) -> None:
        """
        Register required permissions for an endpoint.

        Args:
            path: API path (e.g., /api/v1/chat)
            method: HTTP method (GET, POST, etc.)
            permissions: Required permissions
        """
        key = f"{method.upper()}:{path}"
        self._endpoint_permissions[key] = set(permissions)

    def check_permission(
        self,
        user: User,
        permission: Permission,
    ) -> bool:
        """
        Check if user has a permission.

        Args:
            user: User to check
            permission: Required permission

        Returns:
            True if allowed
        """
        allowed = user.has_permission(permission)

        if not allowed:
            logger.warning(
                "rbac.denied",
                user=user.user_id,
                role=user.role.value,
                permission=permission.value,
            )

        return allowed

    def check_endpoint_access(
        self,
        user: User,
        path: str,
        method: str,
    ) -> bool:
        """
        Check if user can access an endpoint.

        Args:
            user: User to check
            path: API path
            method: HTTP method

        Returns:
            True if allowed
        """
        key = f"{method.upper()}:{path}"
        required = self._endpoint_permissions.get(key)

        if not required:
            # No permissions required
            return True

        # Admin has access to everything
        if user.role == Role.ADMIN:
            return True

        return user.has_any_permission(list(required))

    def get_user_permissions(self, user_id: str) -> list[str]:
        """Get permissions for a user."""
        user = self.get_user(user_id)
        if not user:
            return []
        return [p.value for p in user.permissions]

    def get_stats(self) -> dict[str, Any]:
        """Get RBAC statistics."""
        return {
            "total_users": len(self._users),
            "registered_endpoints": len(self._endpoint_permissions),
            "roles": {
                role.value: len([u for u in self._users.values() if u.role == role])
                for role in Role
            },
        }


# Global RBAC instance
rbac = RBACMiddleware()


# Register default endpoint permissions
rbac.register_endpoint("/api/v1/chat", "POST", [Permission.CHAT])
rbac.register_endpoint("/api/v1/reports/daily", "POST", [Permission.ANALYTICS_READ])
rbac.register_endpoint("/api/v1/kpis/branches", "POST", [Permission.ANALYTICS_READ])
rbac.register_endpoint("/api/v1/pricing/products", "POST", [Permission.PRICING_READ])
rbac.register_endpoint("/api/v1/pricing/recommendations", "POST", [Permission.PRICING_READ])
rbac.register_endpoint("/api/v1/supply-chain/suppliers", "POST", [Permission.SUPPLY_CHAIN_READ])
rbac.register_endpoint("/api/v1/supply-chain/replenishment", "POST", [Permission.SUPPLY_CHAIN_READ])
rbac.register_endpoint("/api/v1/internal/summarize", "POST", [Permission.DOCUMENTS_WRITE])
rbac.register_endpoint("/api/v1/internal/search", "POST", [Permission.DOCUMENTS_READ])
