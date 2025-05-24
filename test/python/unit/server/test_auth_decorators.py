"""Tests for authentication decorators."""

import pytest
from fastapi import HTTPException

from role_play.common.models import UserRole
from role_play.server.auth_decorators import (
    AuthRequired,
    auth_required,
    admin_only,
    check_permissions,
    public,
    require_role,
    scripter_only,
    scripter_or_admin,
)


class TestAuthRequired:
    """Test AuthRequired decorator class."""
    
    def test_default_auth_required(self):
        """Test default auth_required allows any authenticated user."""
        decorator = AuthRequired()
        assert decorator.required_roles == {UserRole.USER, UserRole.SCRIPTER, UserRole.ADMIN}
    
    def test_single_role(self):
        """Test AuthRequired with single role."""
        decorator = AuthRequired(UserRole.ADMIN)
        assert decorator.required_roles == {UserRole.ADMIN}
    
    def test_multiple_roles_set(self):
        """Test AuthRequired with set of roles."""
        roles = {UserRole.ADMIN, UserRole.SCRIPTER}
        decorator = AuthRequired(roles)
        assert decorator.required_roles == roles
    
    def test_multiple_roles_list(self):
        """Test AuthRequired with list of roles."""
        roles = [UserRole.ADMIN, UserRole.SCRIPTER]
        decorator = AuthRequired(roles)
        assert decorator.required_roles == set(roles)
    
    def test_decorator_metadata(self):
        """Test that decorator adds proper metadata to function."""
        @auth_required
        def test_func():
            pass
        
        assert hasattr(test_func, '_auth_required')
        assert test_func._auth_required is True
        assert hasattr(test_func, '_required_roles')
        assert test_func._required_roles == {UserRole.USER, UserRole.SCRIPTER, UserRole.ADMIN}


class TestConvenienceDecorators:
    """Test convenience decorators."""
    
    def test_admin_only(self):
        """Test admin_only decorator."""
        @admin_only
        def test_func():
            pass
        
        assert test_func._required_roles == {UserRole.ADMIN}
    
    def test_scripter_only(self):
        """Test scripter_only decorator."""
        @scripter_only
        def test_func():
            pass
        
        assert test_func._required_roles == {UserRole.SCRIPTER}
    
    def test_scripter_or_admin(self):
        """Test scripter_or_admin decorator."""
        @scripter_or_admin
        def test_func():
            pass
        
        assert test_func._required_roles == {UserRole.ADMIN, UserRole.SCRIPTER}
    
    def test_public(self):
        """Test public decorator."""
        @public
        def test_func():
            pass
        
        assert hasattr(test_func, '_auth_required')
        assert test_func._auth_required is False
        assert hasattr(test_func, '_is_public')
        assert test_func._is_public is True


class TestCheckPermissions:
    """Test check_permissions function."""
    
    def test_admin_has_all_permissions(self):
        """Test admin can access any endpoint."""
        assert check_permissions(UserRole.ADMIN, {UserRole.ADMIN}) is True
        assert check_permissions(UserRole.ADMIN, {UserRole.SCRIPTER}) is True
        assert check_permissions(UserRole.ADMIN, {UserRole.USER}) is True
        assert check_permissions(UserRole.ADMIN, {UserRole.GUEST}) is True
    
    def test_scripter_permissions(self):
        """Test scripter permissions."""
        assert check_permissions(UserRole.SCRIPTER, {UserRole.ADMIN}) is False
        assert check_permissions(UserRole.SCRIPTER, {UserRole.SCRIPTER}) is True
        assert check_permissions(UserRole.SCRIPTER, {UserRole.USER}) is True
        assert check_permissions(UserRole.SCRIPTER, {UserRole.GUEST}) is True
    
    def test_user_permissions(self):
        """Test user permissions."""
        assert check_permissions(UserRole.USER, {UserRole.ADMIN}) is False
        assert check_permissions(UserRole.USER, {UserRole.SCRIPTER}) is False
        assert check_permissions(UserRole.USER, {UserRole.USER}) is True
        assert check_permissions(UserRole.USER, {UserRole.GUEST}) is True
    
    def test_guest_permissions(self):
        """Test guest permissions."""
        assert check_permissions(UserRole.GUEST, {UserRole.ADMIN}) is False
        assert check_permissions(UserRole.GUEST, {UserRole.SCRIPTER}) is False
        assert check_permissions(UserRole.GUEST, {UserRole.USER}) is False
        assert check_permissions(UserRole.GUEST, {UserRole.GUEST}) is True
    
    def test_multiple_required_roles(self):
        """Test checking against multiple required roles."""
        # Admin can access endpoint requiring either ADMIN or SCRIPTER
        assert check_permissions(UserRole.ADMIN, {UserRole.ADMIN, UserRole.SCRIPTER}) is True
        
        # Scripter can access endpoint requiring either ADMIN or SCRIPTER
        assert check_permissions(UserRole.SCRIPTER, {UserRole.ADMIN, UserRole.SCRIPTER}) is True
        
        # User cannot access endpoint requiring either ADMIN or SCRIPTER
        assert check_permissions(UserRole.USER, {UserRole.ADMIN, UserRole.SCRIPTER}) is False


class TestRequireRole:
    """Test require_role function."""
    
    def test_guest_raises_401(self):
        """Test guest user raises 401 Unauthorized."""
        with pytest.raises(HTTPException) as exc_info:
            require_role(UserRole.GUEST, {UserRole.USER})
        
        assert exc_info.value.status_code == 401
        assert "Authentication required" in exc_info.value.detail
    
    def test_insufficient_permissions_raises_403(self):
        """Test authenticated user without permission raises 403 Forbidden."""
        with pytest.raises(HTTPException) as exc_info:
            require_role(UserRole.USER, {UserRole.ADMIN})
        
        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in exc_info.value.detail
        assert "admin" in exc_info.value.detail
    
    def test_sufficient_permissions_passes(self):
        """Test user with sufficient permissions doesn't raise."""
        # Should not raise any exception
        require_role(UserRole.ADMIN, {UserRole.ADMIN})
        require_role(UserRole.ADMIN, {UserRole.USER})
        require_role(UserRole.SCRIPTER, {UserRole.SCRIPTER})
        require_role(UserRole.USER, {UserRole.USER})
    
    def test_multiple_allowed_roles(self):
        """Test with multiple allowed roles."""
        # Should not raise - user has one of the required roles
        require_role(UserRole.SCRIPTER, {UserRole.ADMIN, UserRole.SCRIPTER})
        
        # Should raise - user doesn't have any of the required roles
        with pytest.raises(HTTPException) as exc_info:
            require_role(UserRole.USER, {UserRole.ADMIN, UserRole.SCRIPTER})
        
        assert exc_info.value.status_code == 403
