#!/usr/bin/env python
"""
Script to run the Role Play Server
"""
from role_play.server.role_play_server import start_server, config

if __name__ == "__main__":
    print(f"Starting Role Play Server v{config.version}")
    print(f"Server will be available at http://{config.host}:{config.port}")
    print(f"Configuration:\n{config}")
    start_server()
