#!/usr/bin/env python3
import os
import sys

if len(sys.argv) < 2:
    raise SystemExit(64)
os.setsid()
os.execvp(sys.argv[1], sys.argv[1:])
