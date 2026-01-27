"""
Parse a published Google Doc containing a character grid specification
and print the resulting grid.

The document must contain an HTML table with columns:
  x-coordinate | Character | y-coordinate

Each row specifies a unicode character and its (x, y) position in the grid.
Unspecified positions are filled with spaces.
"""

import re
import requests


def extract_table_cells(html: str) -> list[str]:
    """Extract text content from all <td> elements in an HTML string."""
    return [re.sub(r'<[^>]+>', '', cell).strip()
            for cell in re.findall(r'<td[^>]*>(.*?)</td>', html, re.DOTALL)]


def fetch_and_print_grid(url: str) -> None:
    """
    Fetch a published Google Doc, parse the character grid table,
    and print the grid to stdout.
    """
    response = requests.get(url)
    response.raise_for_status()

    cells = extract_table_cells(response.text)
    if not cells:
        print("No table data found in document.")
        return

    # Skip the 3 header cells, then parse data in groups of 3: x, char, y
    data_cells = cells[3:]
    grid_points = []
    for i in range(0, len(data_cells) - 2, 3):
        try:
            x = int(data_cells[i])
            y = int(data_cells[i + 2])
        except ValueError:
            continue
        grid_points.append((x, y, data_cells[i + 1]))

    if not grid_points:
        print("No valid grid data found.")
        return

    max_x = max(p[0] for p in grid_points)
    max_y = max(p[1] for p in grid_points)

    grid = [[' '] * (max_x + 1) for _ in range(max_y + 1)]
    for x, y, char in grid_points:
        grid[y][x] = char

    for row in grid:
        print(''.join(row))


if __name__ == '__main__':
    import sys
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    url = sys.argv[1]
    if not url.startswith(('https://docs.google.com/', 'http://docs.google.com/')):
        raise ValueError(f"Invalid URL: {url}")

    fetch_and_print_grid(url)
