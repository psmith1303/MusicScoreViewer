"""
Pytest configuration for MusicScoreViewer tests.

Adds the project root to sys.path so that `import MusicScoreViewer` works
from within the tests/ directory without an installed package.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
