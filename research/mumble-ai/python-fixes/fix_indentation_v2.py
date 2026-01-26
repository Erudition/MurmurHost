#!/usr/bin/env python3
"""
Fix indentation for 'with get_db_connection() as conn:' blocks - Version 2

This version uses a smarter approach: for each 'with' statement, we find ALL lines
that should be inside the with block by tracking indentation carefully and looking
for the actual end of the function/block containing the with statement.
"""

import re

def find_with_block_end(lines, start_idx, with_indent):
    """
    Find where a 'with get_db_connection() as conn:' block should end.

    The block ends when we hit:
    1. A line at with_indent or less that starts with 'def ', 'class ', or '@'
    2. End of file
    3. A line at less than with_indent (back to outer scope)

    But we need to be careful about:
    - Empty lines (ignore)
    - Nested blocks (track them)
    - String literals (don't treat as code)
    """
    i = start_idx
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()

        # Skip empty lines
        if not stripped:
            i += 1
            continue

        current_indent = len(line) - len(line.lstrip())

        # If we hit a line at the same indentation as 'with' or less
        if current_indent <= with_indent:
            # Check if it's a new function/class/decorator
            if (stripped.startswith('def ') or
                stripped.startswith('class ') or
                stripped.startswith('@app.') or
                stripped.startswith('@contextmanager')):
                # End of with block
                return i

            # If we're at LESS indent than with, we've definitely left the block
            if current_indent < with_indent:
                return i

        i += 1

    return len(lines)

def fix_indentation_v2(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    fixed_lines = []
    blocks_fixed = 0
    lines_fixed = 0
    lines_removed = 0

    i = 0
    while i < len(lines):
        line = lines[i]

        if 'with get_db_connection() as conn:' in line:
            blocks_fixed += 1
            with_indent = len(line) - len(line.lstrip())
            expected_content_indent = with_indent + 4

            # Add the with line
            fixed_lines.append(line)
            i += 1

            # Find where this with block should end
            block_end = find_with_block_end(lines, i, with_indent)

            # Process all lines in the with block
            while i < block_end:
                current_line = lines[i]
                stripped = current_line.lstrip()

                # Empty lines - keep as is
                if not stripped:
                    fixed_lines.append(current_line)
                    i += 1
                    continue

                # Remove cursor.close() and conn.commit()
                if (stripped.startswith('cursor.close()') or
                    stripped.startswith('conn.commit()')):
                    lines_removed += 1
                    i += 1
                    continue

                current_indent = len(current_line) - len(current_line.lstrip())

                # Fix indentation if needed
                if current_indent >= expected_content_indent:
                    # Properly indented or nested deeper
                    fixed_lines.append(current_line)
                else:
                    # Under-indented - add spaces
                    spaces_to_add = expected_content_indent - current_indent
                    fixed_line = (' ' * spaces_to_add) + current_line
                    fixed_lines.append(fixed_line)
                    lines_fixed += 1

                i += 1

            # Don't increment i - we're already at block_end
            continue

        # Regular line
        fixed_lines.append(line)
        i += 1

    # Write back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)

    return blocks_fixed, lines_fixed, lines_removed

if __name__ == '__main__':
    file_path = r'H:\Mumble-AI\web-control-panel\app.py'
    print("Fixing indentation in app.py (v2)...")
    blocks, lines, removed = fix_indentation_v2(file_path)
    print(f"\n[OK] Fixed {blocks} 'with get_db_connection() as conn:' blocks")
    print(f"[OK] Re-indented {lines} lines")
    print(f"[OK] Removed {removed} unnecessary cursor.close()/conn.commit() lines")
