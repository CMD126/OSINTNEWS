"""
Pytest bootstrap. Ensures the repo root is importable so `import modules.*`
works no matter which directory pytest is invoked from.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
