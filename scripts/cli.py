#!/usr/bin/env python3
"""Unified CLI for fractovision. Delegates to scripts/video_router.py."""
import subprocess
import sys
import os

if __name__ == '__main__':
    script = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'video_router.py')
    result = subprocess.run([sys.executable, script] + sys.argv[1:])
    sys.exit(result.returncode)
