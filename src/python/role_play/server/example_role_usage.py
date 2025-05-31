"""Example usage of user roles in handlers.

This file demonstrates how to use the role-based authorization system with the new RoleChecker dependency pattern.
"""

from fastapi import Depends
from typing import Annotated

from role_play.server.base_handler import BaseHandler
from role_play.server.dependencies import (
    get_current_user,
    require_admin,
    require_scripter_or_admin,
    require_user_or_higher,
    RoleChecker
)
from role_play.common.models import User, UserRole


class ExampleHandler(BaseHandler):
    """Example handler showing different authorization patterns."""
    
    # Public endpoints - no authentication required
    async def health_check(self):
        """Public endpoint - accessible by everyone including GUEST users."""
        return {"status": "healthy"}
    
    async def get_public_info(self):
        """Another public endpoint - no authentication required."""
        return {"message": "This is public information"}
    
    async def get_user_profile(
        self,
        current_user: Annotated[User, Depends(get_current_user)]
    ):
        """Requires any authenticated user (USER, SCRIPTER, or ADMIN)."""
        return {
            "user_id": current_user.id,
            "username": current_user.username,
            "role": current_user.role.value,
        }
    
    async def use_chat(
        self,
        message: str,
        current_user: Annotated[User, Depends(require_user_or_higher)]
    ):
        """Regular users can use chat functionality."""
        # USER, SCRIPTER, and ADMIN can all use this
        return {"response": f"Chat response to: {message}"}
    
    async def create_script(
        self,
        script_data: dict,
        current_user: Annotated[User, Depends(require_scripter_or_admin)]
    ):
        """Only SCRIPTER and ADMIN roles can create scripts."""
        # Only users with SCRIPTER or ADMIN role can access this
        return {"script_id": "new-script-123", "created_by": current_user.username}
    
    async def edit_script(
        self,
        script_id: str,
        current_user: Annotated[User, Depends(require_scripter_or_admin)]
    ):
        """Only SCRIPTER and ADMIN roles can edit scripts."""
        return {"script_id": script_id, "edited_by": current_user.username}
    
    async def manage_users(
        self,
        current_user: Annotated[User, Depends(require_admin)]
    ):
        """Only ADMIN can manage other users."""
        return {"users": ["user1", "user2", "user3"]}
    
    async def change_user_role(
        self,
        user_id: str,
        new_role: str,
        current_user: Annotated[User, Depends(require_admin)]
    ):
        """Only ADMIN can change user roles."""
        return {
            "user_id": user_id,
            "new_role": new_role,
            "changed_by": current_user.username,
        }
    
    async def view_system_stats(
        self,
        current_user: Annotated[User, Depends(require_admin)]
    ):
        """Only ADMIN can view system statistics."""
        return {
            "total_users": 100,
            "active_sessions": 25,
            "scripts_created": 50,
        }


# Role permission matrix:
# 
# Endpoint                    | GUEST | USER | SCRIPTER | ADMIN |
# ----------------------------|-------|------|----------|-------|
# health_check               |   ✓   |  ✓   |    ✓     |   ✓   |
# get_public_info            |   ✓   |  ✓   |    ✓     |   ✓   |
# get_user_profile           |   ✗   |  ✓   |    ✓     |   ✓   |
# use_chat                   |   ✗   |  ✓   |    ✓     |   ✓   |
# create_script              |   ✗   |  ✗   |    ✓     |   ✓   |
# edit_script                |   ✗   |  ✗   |    ✓     |   ✓   |
# manage_users               |   ✗   |  ✗   |    ✗     |   ✓   |
# change_user_role           |   ✗   |  ✗   |    ✗     |   ✓   |
# view_system_stats          |   ✗   |  ✗   |    ✗     |   ✓   |

# How to use custom role requirements:
# 
# For endpoints that need specific role combinations, create a custom RoleChecker:
# 
# # Allow only USER role (not SCRIPTER or ADMIN)
# require_user_only = RoleChecker({UserRole.USER})
# 
# # Allow GUEST and USER but not higher roles
# require_guest_or_user = RoleChecker({UserRole.GUEST, UserRole.USER})
# 
# Then use it in your endpoint:
# async def special_endpoint(
#     self,
#     current_user: Annotated[User, Depends(require_user_only)]
# ):
