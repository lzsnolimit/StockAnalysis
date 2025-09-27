import os
import sys

# Ensure project root is on sys.path for tests
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.append(ROOT)

