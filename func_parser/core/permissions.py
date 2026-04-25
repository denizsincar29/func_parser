"""Permission checking for func_parser."""
from __future__ import annotations

from typing import Dict, List, Set

from .errors import PermissionDeniedError

__all__ = ["PermissionChecker"]


class PermissionChecker:
    """Checks user permissions for commands."""

    # role → set of allowed permissions
    ROLE_PERMISSIONS: Dict[str, Set[str]] = {
        "admin": {"*"},       # admin can do everything
        "user": set(),
        "moderator": {"moderate"},
    }

    def __init__(self) -> None:
        self._role_permissions: Dict[str, Set[str]] = {
            role: set(perms) for role, perms in self.ROLE_PERMISSIONS.items()
        }
        self._user_permissions: Dict[str, Set[str]] = {}  # user_id → extra permissions

    def add_role(self, role: str, permissions: List[str]) -> None:
        """Add permissions to a role (creates the role if absent)."""
        self._role_permissions.setdefault(role, set()).update(permissions)

    def grant(self, user_id: str, permission: str) -> None:
        """Grant an individual permission to a specific user."""
        self._user_permissions.setdefault(user_id, set()).add(permission)

    def revoke(self, user_id: str, permission: str) -> None:
        """Revoke an individual permission from a specific user."""
        self._user_permissions.get(user_id, set()).discard(permission)

    def check(
        self,
        user_roles: List[str],
        required_permissions: List[str],
        user_id: str = "",
    ) -> bool:
        """Return True if the user has **all** of *required_permissions*."""
        if not required_permissions:
            return True
        user_perms: Set[str] = set()
        for role in user_roles:
            role_perms = self._role_permissions.get(role, set())
            if "*" in role_perms:
                return True  # admin shortcut
            user_perms.update(role_perms)
        user_perms.update(self._user_permissions.get(user_id, set()))
        return all(p in user_perms for p in required_permissions)

    def require(
        self,
        user_roles: List[str],
        required_permissions: List[str],
        user_id: str = "",
    ) -> None:
        """Raise :class:`PermissionDeniedError` if any required permission is missing."""
        for perm in required_permissions:
            if not self.check(user_roles, [perm], user_id):
                raise PermissionDeniedError(perm, user_id)
