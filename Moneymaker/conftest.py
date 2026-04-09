"""Pytest configuration for Moneymaker.

Adds the repository root to sys.path so that ``workspace`` (a top-level
package) is importable when running tests from the Moneymaker/ directory.
"""

import sys
from pathlib import Path

# Repository root is one level above this file (Moneymaker/../)
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
