"""Unified environment parsing and resolution utilities.

This module centralizes how the application determines its deployment
environment to avoid duplication and ambiguity across the codebase.

Canonical environments: dev | beta | prod

Accepted synonyms (case-insensitive):
- development -> dev
- production -> prod

Priority for resolution (highest to lowest):
1) CONFIG_FILE (extracts env from filename like config/prod.yaml)
2) ENV
3) ENVIRONMENT
4) default: dev
"""

from __future__ import annotations

import os
import re
from typing import Optional

from .models import Environment, EnvironmentInfo


def parse_environment_str(value: Optional[str]) -> Environment:
    """Parse a string into the canonical Environment enum.

    Accepts canonical values (dev|beta|prod) and common synonyms
    like development|production.
    """
    if not value:
        return Environment.DEV

    s = value.strip().lower()
    # Map synonyms
    if s == "development":
        s = "dev"
    elif s == "production":
        s = "prod"

    try:
        return Environment(s)
    except ValueError:
        # Default safely to DEV and let callers decide if they want to warn
        return Environment.DEV


def resolve_environment(config_file: Optional[str] = None) -> Environment:
    """Resolve the current environment using a consistent precedence order.

    Precedence:
    1) CONFIG_FILE (env extracted from its basename, e.g., beta.yaml)
    2) ENV
    3) ENVIRONMENT
    4) default to dev
    """
    # 1) CONFIG_FILE (argument overrides env var for testability)
    config_file = config_file or os.getenv("CONFIG_FILE")
    if config_file:
        # Try to extract the environment from the filename
        # e.g., /app/config/beta.yaml -> beta
        m = re.search(r"/(\\w+)\\.yaml$", config_file)
        if m:
            return parse_environment_str(m.group(1))

    # 2) ENV
    env = os.getenv("ENV")
    if env:
        return parse_environment_str(env)

    # 3) ENVIRONMENT (supports development/production synonyms)
    env2 = os.getenv("ENVIRONMENT")
    if env2:
        return parse_environment_str(env2)

    # 4) fallback
    return Environment.DEV


def get_environment_info() -> EnvironmentInfo:
    """Return an EnvironmentInfo snapshot using the unified resolver."""
    env = resolve_environment()
    return EnvironmentInfo(
        name=env,
        is_production=(env == Environment.PROD),
        is_development=(env == Environment.DEV),
    )


def environment_name() -> str:
    """Convenience accessor for the current environment name as a string."""
    return resolve_environment().value

