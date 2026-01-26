#!/usr/bin/env python3
"""
Fix indentation for all 'with get_db_connection() as conn:' blocks in app.py

The issue: Code inside 'with get_db_connection() as conn:' blocks is not indented properly.
The pattern is:
    with get_db_connection() as conn:
        cursor = conn.cursor()  # correctly indented at +4
    cursor.execute(...)  # WRONG - should also be at +4 inside the with block

We need to re-indent everything after the 'with' statement until we hit a new function/class
definition or decorator at the same or lower indent level as the function containing the 'with'.
"""

def fix_indentation(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    fixed_lines = []
    block_count = 0
    lines_fixed = 0
    removed_lines = 0

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check if this line contains 'with get_db_connection() as conn:'
        if 'with get_db_connection() as conn:' in line:
            block_count += 1
            # Get the indentation level of the 'with' statement
            with_indent = len(line) - len(line.lstrip())
            expected_content_indent = with_indent + 4

            # Add the 'with' line as-is
            fixed_lines.append(line)
            i += 1

            # Find the function/method indent level (should be with_indent - 4 usually)
            # The with block ends when we hit a line at <= with_indent that starts a new block
            # (def, class, @decorator) or when we hit EOF

            while i < len(lines):
                current_line = lines[i]
                current_indent = len(current_line) - len(current_line.lstrip())
                stripped = current_line.lstrip()

                # Empty lines - keep as is
                if not stripped:
                    fixed_lines.append(current_line)
                    i += 1
                    continue

                # Check if we've hit a new function, class, or decorator at or before with_indent level
                # This signals the end of the with block
                if current_indent <= with_indent:
                    if (stripped.startswith('def ') or
                        stripped.startswith('class ') or
                        stripped.startswith('@')):
                        # Exited the with block - new function/decorator
                        break
                    # Also exit if we see 'return' at the with indent level (end of function)
                    if stripped.startswith('return '):
                        # This return is at the function level, outside the with block
                        break

                # Remove cursor.close() and conn.commit() lines (not needed with context manager)
                if stripped.startswith('cursor.close()') or stripped.startswith('conn.commit()'):
                    removed_lines += 1
                    i += 1
                    continue

                # Now fix the indentation
                # Everything in the with block should be at least at expected_content_indent

                if current_indent >= expected_content_indent:
                    # Already properly indented (or nested deeper)
                    fixed_lines.append(current_line)
                else:
                    # Under-indented - needs fixing
                    indent_diff = expected_content_indent - current_indent
                    fixed_line = (' ' * indent_diff) + current_line
                    fixed_lines.append(fixed_line)
                    lines_fixed += 1

                i += 1

            # Don't increment i - the break positioned us correctly
            continue

        # Regular line outside with blocks
        fixed_lines.append(line)
        i += 1

    # Write back to file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)

    return block_count, lines_fixed, removed_lines

if __name__ == '__main__':
    file_path = r'H:\Mumble-AI\web-control-panel\app.py'
    print("Fixing indentation in app.py...")
    blocks, lines, removed = fix_indentation(file_path)
    print(f"\n[OK] Fixed {blocks} 'with get_db_connection() as conn:' blocks")
    print(f"[OK] Re-indented {lines} lines")
    print(f"[OK] Removed {removed} unnecessary cursor.close()/conn.commit() lines")
    print(f"\nTotal blocks processed: {blocks}")
