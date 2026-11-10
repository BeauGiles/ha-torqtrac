#!/usr/bin/env python3
"""Render brand-src/*.svg to the PNG files Home Assistant / the brands repo expect.

    python3 -m venv .venv && .venv/bin/pip install pymupdf
    .venv/bin/python tools/render_brand.py
"""
import pathlib

import pymupdf

root = pathlib.Path(__file__).resolve().parent.parent
src = root / "brand-src"
out = root / "custom_components" / "torqeedo_torqtrac" / "brand"
out.mkdir(parents=True, exist_ok=True)

# name -> (svg, target height in px)  [logos keep aspect ratio]
JOBS = {
    "icon.png": ("icon.svg", 256),
    "icon@2x.png": ("icon.svg", 512),
    "logo.png": ("logo.svg", 192),
    "logo@2x.png": ("logo.svg", 384),
    "dark_logo.png": ("dark_logo.svg", 192),
    "dark_logo@2x.png": ("dark_logo.svg", 384),
}

for name, (svg, height) in JOBS.items():
    page = pymupdf.open(src / svg)[0]
    scale = height / page.rect.height
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=True)
    pix.save(out / name)
    print(f"{name}: {pix.width}x{pix.height}")
