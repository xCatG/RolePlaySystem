"""Example usage of user roles in handlers.

This file demonstrates how to use the role-based authorization system.
"""

from role_play.server.auth_decorators import (
    auth_required,
    admin_only,
    public,
    scripter_or_admin,
)
from role_play.server.base_handler import BaseHandler


class ExampleHandler(BaseHandler):
    """Example handler showing different authorization patterns."""
    
    @public
    async def health_check(self):
        """Public endpoint - accessible by everyone including GUEST users."""
        return {"status": "healthy"}
    
    @public
    async def get_public_info(self):
        """Another public endpoint - no authentication required."""
        return {"message": "This is public information"}
    
    @auth_required
    async def get_user_profile(self):
        """Requires any authenticated user (USER, SCRIPTER, or ADMIN)."""
        # self.current_user is available here with user info
        return {
            "user_id": self.current_user.user_id,
            "username": self.current_user.username,
            "role": self.current_user.role.value,
        }
    
    @auth_required
    async def use_chat(self, message: str):
        """Regular users can use chat functionality."""
        # USER, SCRIPTER, and ADMIN can all use this
        return {"response": f"Chat response to: {message}"}
    
    @scripter_or_admin
    async def create_script(self, script_data: dict):
        """Only SCRIPTER and ADMIN roles can create scripts."""
        # Only users with SCRIPTER or ADMIN role can access this
        return {"script_id": "new-script-123", "created_by": self.current_user.username}
    
    @scripter_or_admin
    async def edit_script(self, script_id: str):
        """Only SCRIPTER and ADMIN roles can edit scripts."""
        return {"script_id": script_id, "edited_by": self.current_user.username}
    
    @admin_only
    async def manage_users(self):
        """Only ADMIN can manage other users."""
        return {"users": ["user1", "user2", "user3"]}
    
    @admin_only
    async def change_user_role(self, user_id: str, new_role: str):
        """Only ADMIN can change user roles."""
        return {
            "user_id": user_id,
            "new_role": new_role,
            "changed_by": self.current_user.username,
        }
    
    @admin_only
    async def view_system_stats(self):
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
