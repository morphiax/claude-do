#!/usr/bin/env python3
"""Entry point — resolves through symlinks to find the cli package."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from cli.__main__ import main

main()
