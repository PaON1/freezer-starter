#!/usr/bin/env python3
"""
freezer_paths.py — Freezer knows where WRM lives (no hardcoding)
Assumes freezer is at: ~/wrm_dash_core/freezer
"""

from __future__ import annotations
from pathlib import Path

FREEZER_DIR = Path(__file__).resolve().parent
WRM_ROOT = FREEZER_DIR.parent  # ~/wrm_dash_core

MESH_DIR = WRM_ROOT / "wrm_mesh"
CORTEX_DIR = WRM_ROOT / "wrm_cortex_core"

def p(*parts: str) -> Path:
    return FREEZER_DIR.joinpath(*parts)

def mesh(*parts: str) -> Path:
    return MESH_DIR.joinpath(*parts)

def cortex(*parts: str) -> Path:
    return CORTEX_DIR.joinpath(*parts)
