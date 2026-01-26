#!/usr/bin/env python3
"""Debug the indentation detection"""

# Read specific lines to debug
with open(r'H:\Mumble-AI\web-control-panel\app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Lines 97-110 contain init_config_table
for i in range(96, 110):
    line = lines[i]
    indent = len(line) - len(line.lstrip())
    print(f"Line {i+1}: indent={indent:2d} | {repr(line[:60])}")
