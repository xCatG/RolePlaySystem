"""Tests for user roles and permissions."""

import pytest

from role_play.common.models import UserRole


class TestUserRole:
    """Test UserRole enum and its methods."""
    
    def test_role_values(self):
        """Test that role values are as expected."""
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.SCRIPTER.value == "scripter"
        assert UserRole.USER.value == "user"
        assert UserRole.GUEST.value == "guest"
    
    def test_from_str_valid(self):
        """Test converting valid strings to UserRole."""
        assert UserRole.from_str("admin") == UserRole.ADMIN
        assert UserRole.from_str("ADMIN") == UserRole.ADMIN
        assert UserRole.from_str("scripter") == UserRole.SCRIPTER
        assert UserRole.from_str("user") == UserRole.USER
        assert UserRole.from_str("guest") == UserRole.GUEST
    
    def test_from_str_invalid(self):
        """Test converting invalid strings defaults to GUEST."""
        assert UserRole.from_str(None) == UserRole.GUEST
        assert UserRole.from_str("") == UserRole.GUEST
        assert UserRole.from_str("invalid") == UserRole.GUEST
        assert UserRole.from_str("superadmin") == UserRole.GUEST
    
    def test_has_permission_admin(self):
        """Test ADMIN has all permissions."""
        admin = UserRole.ADMIN
        assert admin.has_permission(UserRole.ADMIN) is True
        assert admin.has_permission(UserRole.SCRIPTER) is True
        assert admin.has_permission(UserRole.USER) is True
        assert admin.has_permission(UserRole.GUEST) is True
    
    def test_has_permission_scripter(self):
        """Test SCRIPTER permissions."""
        scripter = UserRole.SCRIPTER
        assert scripter.has_permission(UserRole.ADMIN) is False
        assert scripter.has_permission(UserRole.SCRIPTER) is True
        assert scripter.has_permission(UserRole.USER) is True
        assert scripter.has_permission(UserRole.GUEST) is True
    
    def test_has_permission_user(self):
        """Test USER permissions."""
        user = UserRole.USER
        assert user.has_permission(UserRole.ADMIN) is False
        assert user.has_permission(UserRole.SCRIPTER) is False
        assert user.has_permission(UserRole.USER) is True
        assert user.has_permission(UserRole.GUEST) is True
    
    def test_has_permission_guest(self):
        """Test GUEST permissions."""
        guest = UserRole.GUEST
        assert guest.has_permission(UserRole.ADMIN) is False
        assert guest.has_permission(UserRole.SCRIPTER) is False
        assert guest.has_permission(UserRole.USER) is False
        assert guest.has_permission(UserRole.GUEST) is True
    
    def test_is_authenticated(self):
        """Test is_authenticated property."""
        assert UserRole.ADMIN.is_authenticated is True
        assert UserRole.SCRIPTER.is_authenticated is True
        assert UserRole.USER.is_authenticated is True
        assert UserRole.GUEST.is_authenticated is False
    
    def test_role_hierarchy(self):
        """Test role hierarchy for permission inheritance."""
        # Create users with different roles
        roles = [UserRole.GUEST, UserRole.USER, UserRole.SCRIPTER, UserRole.ADMIN]
        
        # Test that each role has permissions for all lower roles
        for i, role in enumerate(roles):
            for j, required_role in enumerate(roles):
                if i >= j:  # Higher index = higher privilege
                    assert role.has_permission(required_role) is True
                else:
                    assert role.has_permission(required_role) is False
