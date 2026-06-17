import os
import sys

# 把 lab 目录加入 sys.path,使 `from dataio import ...` 在 tests/ 下可用
sys.path.insert(0, os.path.dirname(__file__))
