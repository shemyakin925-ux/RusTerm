"""CLI commands: init, ingest, snapshot, export, verify, doctor.

Strict prohibitions: no Qt at all, only standard library.
"""
from __future__ import annotations

import sys
import argparse
import json
import os
from typing import Optional, List
