#!/usr/bin/env python3
"""
mermaid_to_png.py — рендер .mmd → .png через mermaid-cli (mmdc).

Usage:
    python mermaid_to_png.py 02_Спецификация/architecture.mmd
    python mermaid_to_png.py 02_Спецификация/*.mmd --width 1600 --height 900
    python mermaid_to_png.py 02_Спецификация/architecture.mmd --output 06_ПЗ/figures/Р6.png

Требует mermaid-cli:
    npm install -g @mermaid-js/mermaid-cli

Опции по умолчанию: 1600x900, белый фон, scale 2 (≈ 300 DPI).
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def render_one(input_path: Path, output_path: Path, width: int, height: int, scale: int):
    cmd = [
        "mmdc",
        "-i", str(input_path),
        "-o", str(output_path),
        "-w", str(width),
        "-H", str(height),
        "-s", str(scale),
        "--backgroundColor", "white",
    ]
    print(" ".join(cmd))
    r = subprocess.run(cmd)
    return r.returncode


def main():
    p = argparse.ArgumentParser()
    p.add_argument("inputs", nargs="+", type=Path, help="Один или несколько .mmd-файлов")
    p.add_argument("--output", "-o", type=Path, default=None,
                   help="Выходной .png (если 1 input). Если несколько inputs — игнорируется")
    p.add_argument("--width", "-w", type=int, default=1600)
    p.add_argument("--height", "-H", type=int, default=900)
    p.add_argument("--scale", "-s", type=int, default=2)
    args = p.parse_args()

    if shutil.which("mmdc") is None:
        sys.exit("mmdc не найден. Установи: npm install -g @mermaid-js/mermaid-cli")

    failed = 0
    for inp in args.inputs:
        if len(args.inputs) == 1 and args.output:
            out = args.output
        else:
            out = inp.with_suffix(".png")
        if render_one(inp, out, args.width, args.height, args.scale) != 0:
            failed += 1

    sys.exit(failed)


if __name__ == "__main__":
    main()
