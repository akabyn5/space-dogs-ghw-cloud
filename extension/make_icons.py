"""
make_icons.py — Space Dogs icon generator
==========================================
Run this once from the extension/ folder to produce the four PNG sizes
that manifest.json requires:

    python make_icons.py

What it does
------------
1. Downloads the official Space Dogs logo from Flickr.
2. Resizes it to 16 × 16, 32 × 32, 48 × 48, and 128 × 128 pixels.
3. Applies a circular crop (rounded mask) so the icon looks clean at
   every size — Chrome displays extension icons in a rounded context
   on some surfaces, so a pre-cropped circle is more predictable.
4. Saves all four files into the icons/ subfolder (creating it if needed).

If the download fails (no internet, CDN unavailable), the script falls
back to generating a placeholder: the cyan-on-dark circle from the
original make_icons.py, so you can still load the extension locally.

Requirements: Pillow  →  pip install Pillow
"""

import os
import io
import urllib.request
from PIL import Image, ImageDraw, ImageOps

# ── Configuration ──────────────────────────────────────────────────────────

LOGO_URL   = "https://live.staticflickr.com/65535/55156104648_757ed729af_q.jpg"
SIZES      = [16, 32, 48, 128]
OUTPUT_DIR = "icons"

# Brand colours used by the fallback generator
BRAND_BG     = (10,  22,  40,  255)   # --primary-dark
BRAND_BORDER = (0,  217, 179,  255)   # --card-border cyan


# ── Helpers ────────────────────────────────────────────────────────────────

def circular_crop(img: Image.Image) -> Image.Image:
    """
    Returns a copy of `img` cropped to a circle with a transparent background.

    How it works: we create a greyscale mask the same size as the image,
    draw a filled white ellipse that fits exactly inside the bounds, then
    pass that mask as the alpha channel of the image.  Pixels outside the
    circle become fully transparent; pixels inside are unchanged.
    """
    size   = img.size
    mask   = Image.new("L", size, 0)           # black (fully transparent) canvas
    draw   = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size[0] - 1, size[1] - 1), fill=255)  # white circle

    result = img.convert("RGBA")
    result.putalpha(mask)                       # apply the circle as the alpha
    return result


def add_glow_border(img: Image.Image, size: int) -> Image.Image:
    """
    Composites a thin cyan border ring over the circular icon.

    At small sizes (16 px, 32 px) the border is 1 px; at larger sizes it
    scales up proportionally so it stays visible without overwhelming detail.
    """
    border_width = max(1, size // 24)
    overlay      = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw         = ImageDraw.Draw(overlay)
    draw.ellipse(
        (border_width // 2, border_width // 2,
         size - border_width // 2 - 1, size - border_width // 2 - 1),
        outline=BRAND_BORDER,
        width=border_width,
    )
    return Image.alpha_composite(img, overlay)


def make_placeholder(size: int) -> Image.Image:
    """
    Generates a simple branded placeholder icon when the logo can't be downloaded.
    Dark background + cyan border — matches the extension's visual identity.
    """
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((0, 0, size - 1, size - 1), fill=BRAND_BG)
    border = max(1, size // 16)
    draw.ellipse((0, 0, size - 1, size - 1), outline=BRAND_BORDER, width=border)
    return img


def process_logo(source: Image.Image, size: int) -> Image.Image:
    """
    Takes the raw downloaded logo, fits it into a square canvas with a dark
    background (in case the source isn't perfectly square), resizes it to
    `size × size` using high-quality downsampling, applies the circular crop,
    then adds the glow border ring.
    """
    # Fit onto a square dark canvas so non-square sources don't get squashed
    dim    = max(source.width, source.height)
    canvas = Image.new("RGBA", (dim, dim), BRAND_BG)
    offset = ((dim - source.width) // 2, (dim - source.height) // 2)
    canvas.paste(source.convert("RGBA"), offset)

    # High-quality downscale to the target size
    canvas = canvas.resize((size, size), Image.LANCZOS)

    # Circular crop + border
    canvas = circular_crop(canvas)
    canvas = add_glow_border(canvas, size)
    return canvas


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── Step 1: download the logo ─────────────────────────────────────────
    source = None
    print(f"Downloading logo from {LOGO_URL} …")
    try:
        req = urllib.request.Request(
            LOGO_URL,
            headers={"User-Agent": "Mozilla/5.0 (space-dogs-icon-generator)"},
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            raw   = response.read()
            source = Image.open(io.BytesIO(raw))
            print(f"  ✓ Downloaded ({source.width}×{source.height} px, {source.mode})")
    except Exception as exc:
        print(f"  ✗ Download failed: {exc}")
        print("  → Using branded placeholder instead.")

    # ── Step 2: generate each icon size ──────────────────────────────────
    for size in SIZES:
        if source is not None:
            icon = process_logo(source, size)
        else:
            icon = make_placeholder(size)

        path = os.path.join(OUTPUT_DIR, f"icon{size}.png")
        icon.save(path, format="PNG")
        print(f"  Saved {path}  ({size}×{size})")

    print("\nDone. All icons written to the icons/ folder.")
    print("Reload the extension in chrome://extensions to pick up the new icons.")


if __name__ == "__main__":
    main()