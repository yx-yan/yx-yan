"""Turn the brand fish mark into ASCII art for the profile card.

One-off helper; run it again only when the mark changes, then hand-tune
ascii/fish.txt. Needs Google Chrome for rendering and nothing beyond the
standard library.

    python3 scripts/make_ascii.py path/to/mark-white.svg > ascii/fish.txt
"""

import argparse
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# Light to dark coverage; the mark is drawn white on black, so more white = denser glyph.
RAMP = " .:-=+*#%@"
# A monospace cell is roughly twice as tall as it is wide.
CELL_ASPECT = 2.0


def render(svg: Path, size: int) -> Path:
    html = Path(tempfile.mkdtemp()) / "mark.html"
    html.write_text(
        "<html><body style='margin:0;background:#000'>"
        f"<img src='{svg.resolve().as_uri()}' width='{size}' height='{size}'>"
        "</body></html>"
    )
    png = html.with_suffix(".png")
    subprocess.run(
        [CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
         f"--screenshot={png}", f"--window-size={size},{size}", html.as_uri()],
        check=True, capture_output=True,
    )
    return png


def read_png_gray(path: Path) -> tuple[int, int, list[list[int]]]:
    """Decode an 8-bit RGB/RGBA PNG into rows of grey levels."""
    data = path.read_bytes()
    pos, idat = 8, b""
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, color = struct.unpack(">IIBB", body[:10])
            if depth != 8 or color not in (2, 6):
                sys.exit(f"unsupported PNG (depth {depth}, colour type {color})")
            bpp = 3 if color == 2 else 4
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length

    raw = zlib.decompress(idat)
    stride = width * bpp
    prev = bytearray(stride)
    rows = []
    for y in range(height):
        start = y * (stride + 1)
        filt, line = raw[start], bytearray(raw[start + 1:start + 1 + stride])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if filt == 1:
                line[i] = (line[i] + a) & 0xFF
            elif filt == 2:
                line[i] = (line[i] + b) & 0xFF
            elif filt == 3:
                line[i] = (line[i] + (a + b) // 2) & 0xFF
            elif filt == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if pa <= pb and pa <= pc else b if pb <= pc else c
                line[i] = (line[i] + pred) & 0xFF
        rows.append([sum(line[x * bpp:x * bpp + 3]) // 3 for x in range(width)])
        prev = line
    return width, height, rows


def to_ascii(rows: list[list[int]], size: int, cols: int) -> list[str]:
    cell_w = size / cols
    cell_h = cell_w * CELL_ASPECT
    out = []
    for r in range(int(size / cell_h)):
        y0, y1 = int(r * cell_h), int((r + 1) * cell_h)
        line = ""
        for c in range(cols):
            x0, x1 = int(c * cell_w), int((c + 1) * cell_w)
            block = [rows[y][x] for y in range(y0, y1) for x in range(x0, x1)]
            level = sum(block) / len(block) / 255
            line += RAMP[min(len(RAMP) - 1, int(level * len(RAMP)))]
        out.append(line.rstrip())
    while out and not out[0]:
        out.pop(0)
    while out and not out[-1]:
        out.pop()
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("svg", type=Path)
    parser.add_argument("--cols", type=int, default=44)
    parser.add_argument("--size", type=int, default=880)
    args = parser.parse_args()

    _, _, rows = read_png_gray(render(args.svg, args.size))
    print("\n".join(to_ascii(rows, args.size, args.cols)))


if __name__ == "__main__":
    main()
