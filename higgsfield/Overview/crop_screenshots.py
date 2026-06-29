#!/usr/bin/env python3
"""Crop the DocSend viewer chrome (top toolbar, bottom privacy bar) off deck
screenshots, leaving just the slide (and the "Tribe Capital: Higgsfield" pill).

Usage:
    python3 crop_screenshots.py [folder ...]

Defaults to the current folder if none given. Writes results into a
"cropped" subfolder next to the originals (originals are left untouched).
"""
import sys
import glob
import os
from PIL import Image

TOP = 208           # px to trim off the top (DocSend toolbar / menu bar)
BOTTOM_MARGIN = 80  # px to trim off the bottom (DocSend privacy/cookies bar)


def crop_folder(folder):
    out_dir = os.path.join(folder, "cropped")
    os.makedirs(out_dir, exist_ok=True)
    files = sorted(glob.glob(os.path.join(folder, "*.png")))
    for f in files:
        im = Image.open(f)
        w, h = im.size
        cropped = im.crop((0, TOP, w, h - BOTTOM_MARGIN))
        cropped.save(os.path.join(out_dir, os.path.basename(f)))
    print(f"{folder}: cropped {len(files)} image(s) -> {out_dir}")


if __name__ == "__main__":
    folders = sys.argv[1:] or ["."]
    for folder in folders:
        crop_folder(folder)
