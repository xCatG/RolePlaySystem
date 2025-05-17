"""
Server package initialization
"""
from role_play.server.config import config
from role_play.server.role_play_server import app, server, start_server

__all__ = ['config', 'app', 'server', 'start_server']
