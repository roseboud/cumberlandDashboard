"""
Generate XYZ map tiles from flood raster COGs for web display.

This script uses rasterio (which wraps GDAL's libgdal internally) for all
georeferenced raster operations — reading, windowed extraction, and resampling.
PIL is used only for the final lossless PNG encoding of RGBA numpy arrays.

Pipeline per COG:
  1. Open the EPSG:3857 COG from assets/cog_3857/{side}/
  2. For each zoom level (default 10–15), calculate which XYZ tiles intersect
  3. For each tile, use rasterio windowed read to extract the raster data
     at the correct resolution (GDAL handles resampling internally)
  4. Colorize flood pixels: blue rgba(37,99,235) with level-based opacity
  5. Save as transparent PNG tile: assets/tiles/{side}/{level_key}/{z}/{x}/{y}.png

Usage:
  python generate_tiles.py                    # Process all COGs
  python generate_tiles.py --side fundy       # Process only fundy side
  python generate_tiles.py --zoom 10 14       # Custom zoom range
  python generate_tiles.py --level 2_0m       # Single level only
"""

import os
import sys
import math
import argparse
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import rasterio
    from rasterio.windows import from_bounds as window_from_bounds
    from rasterio.enums import Resampling
    import numpy as np
    from PIL import Image
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install rasterio numpy Pillow")
    sys.exit(1)

# ─── Configuration ───────────────────────────────────────────────────────────

TILE_SIZE = 256
FLOOD_COLOR = (37, 99, 235)    # Blue flood color (matches frontend)
BASE_ALPHA = 0.25              # Min opacity at level 0
MAX_ALPHA = 0.55               # Max opacity at level 11
FLOOD_MAX_LEVEL = 11.0

MIN_ZOOM = 10
MAX_ZOOM = 15

SIDES = {
    'fundy': 'fundy',
    'north': 'north'
}

# Web Mercator constants
ORIGIN_SHIFT = 2 * math.pi * 6378137 / 2.0  # ~20037508.342789244


# ─── XYZ Tile Math (EPSG:3857) ──────────────────────────────────────────────

def tile_bounds_3857(x, y, z):
    """Get EPSG:3857 bounds for an XYZ tile (using TMS-flipped Y for XYZ scheme)."""
    n = 2 ** z
    tile_size_m = 2 * ORIGIN_SHIFT / n

    min_x = -ORIGIN_SHIFT + x * tile_size_m
    max_x = min_x + tile_size_m

    # XYZ scheme: y=0 is top (north)
    max_y = ORIGIN_SHIFT - y * tile_size_m
    min_y = max_y - tile_size_m

    return (min_x, min_y, max_x, max_y)


def get_tiles_for_bounds(bounds_3857, zoom):
    """Get all XYZ tile coordinates that intersect the given EPSG:3857 bounds."""
    min_x, min_y, max_x, max_y = bounds_3857
    n = 2 ** zoom
    tile_size_m = 2 * ORIGIN_SHIFT / n

    # Clamp to valid Web Mercator range
    min_x = max(min_x, -ORIGIN_SHIFT)
    max_x = min(max_x, ORIGIN_SHIFT)
    min_y = max(min_y, -ORIGIN_SHIFT)
    max_y = min(max_y, ORIGIN_SHIFT)

    x_min = int(math.floor((min_x + ORIGIN_SHIFT) / tile_size_m))
    x_max = int(math.floor((max_x + ORIGIN_SHIFT) / tile_size_m))
    # XYZ: y=0 at top
    y_min = int(math.floor((ORIGIN_SHIFT - max_y) / tile_size_m))
    y_max = int(math.floor((ORIGIN_SHIFT - min_y) / tile_size_m))

    # Clamp to valid range
    x_min = max(0, x_min)
    x_max = min(n - 1, x_max)
    y_min = max(0, y_min)
    y_max = min(n - 1, y_max)

    tiles = []
    for ty in range(y_min, y_max + 1):
        for tx in range(x_min, x_max + 1):
            tiles.append((tx, ty, zoom))
    return tiles


# ─── Level Parsing ───────────────────────────────────────────────────────────

def level_from_filename(filename):
    """Extract water level from filename like RasterFlood_5_6m.tif -> 5.6"""
    name = filename.replace('RasterFlood_', '').replace('.tif', '').replace('m', '')
    parts = name.split('_')
    if len(parts) == 2:
        return float(parts[0]) + float(parts[1]) / 10.0
    return 0.0


def level_key_from_filename(filename):
    """Extract level key from filename like RasterFlood_5_6m.tif -> 5_6m"""
    return filename.replace('RasterFlood_', '').replace('.tif', '')


def get_flood_alpha(level):
    """Calculate opacity (0–255) based on flood level."""
    ratio = min(level / FLOOD_MAX_LEVEL, 1.0)
    return int((BASE_ALPHA + ratio * (MAX_ALPHA - BASE_ALPHA)) * 255)


# ─── Tile Generation ────────────────────────────────────────────────────────

def generate_tile(src, tile_x, tile_y, zoom, level, output_dir, side_key, level_key):
    """Generate a single XYZ tile PNG from the raster source."""
    bounds = tile_bounds_3857(tile_x, tile_y, zoom)

    # Check if tile bounds intersect the raster
    rb = src.bounds
    if bounds[0] >= rb.right or bounds[2] <= rb.left or \
       bounds[1] >= rb.top or bounds[3] <= rb.bottom:
        return False  # No intersection

    # Use rasterio windowed read — this uses GDAL's internal resampling
    try:
        window = window_from_bounds(
            bounds[0], bounds[1], bounds[2], bounds[3],
            transform=src.transform
        )

        # Read the raster data at tile resolution using GDAL resampling
        data = src.read(
            1,
            window=window,
            out_shape=(TILE_SIZE, TILE_SIZE),
            resampling=Resampling.nearest,
            boundless=True,
            fill_value=0
        )
    except Exception:
        return False

    # Check if tile has any flood data
    nodata = src.nodata
    if nodata is not None:
        mask = (data != 0) & (data != nodata) & (~np.isnan(data))
    else:
        mask = (data != 0) & (~np.isnan(data))

    if not mask.any():
        return False  # Empty tile — skip

    # Create RGBA tile
    alpha_val = get_flood_alpha(level)
    rgba = np.zeros((TILE_SIZE, TILE_SIZE, 4), dtype=np.uint8)
    rgba[mask, 0] = FLOOD_COLOR[0]
    rgba[mask, 1] = FLOOD_COLOR[1]
    rgba[mask, 2] = FLOOD_COLOR[2]
    rgba[mask, 3] = alpha_val

    # Save as PNG (lossless encoding)
    tile_dir = os.path.join(output_dir, side_key, level_key, str(zoom), str(tile_x))
    os.makedirs(tile_dir, exist_ok=True)
    tile_path = os.path.join(tile_dir, f"{tile_y}.png")

    img = Image.fromarray(rgba, 'RGBA')
    img.save(tile_path, 'PNG', optimize=True)
    return True


def process_cog(cog_path, side_key, output_dir, min_zoom, max_zoom):
    """Process a single COG file into XYZ tiles for all zoom levels."""
    filename = os.path.basename(cog_path)
    level = level_from_filename(filename)
    level_key = level_key_from_filename(filename)

    print(f"  {filename} (level {level:.1f}m)...", flush=True)

    with rasterio.open(cog_path) as src:
        # Verify CRS is EPSG:3857
        if src.crs and src.crs.to_epsg() != 3857:
            print(f"    WARNING: CRS is {src.crs}, expected EPSG:3857. Skipping.")
            return 0

        bounds_3857 = (src.bounds.left, src.bounds.bottom,
                       src.bounds.right, src.bounds.top)

        total_tiles = 0

        for zoom in range(min_zoom, max_zoom + 1):
            tiles = get_tiles_for_bounds(bounds_3857, zoom)
            zoom_count = 0

            for tx, ty, z in tiles:
                if generate_tile(src, tx, ty, z, level, output_dir,
                                 side_key, level_key):
                    zoom_count += 1

            total_tiles += zoom_count

        print(f"    → {total_tiles} tiles (z{min_zoom}–z{max_zoom})")
        return total_tiles


def main():
    parser = argparse.ArgumentParser(
        description='Generate XYZ tiles from flood COGs')
    parser.add_argument('--side', choices=['fundy', 'north'],
                        help='Process only one side')
    parser.add_argument('--zoom', nargs=2, type=int, default=[MIN_ZOOM, MAX_ZOOM],
                        metavar=('MIN', 'MAX'),
                        help=f'Zoom range (default {MIN_ZOOM} {MAX_ZOOM})')
    parser.add_argument('--level', type=str, default=None,
                        help='Process single level (e.g., 2_0m)')
    args = parser.parse_args()

    min_zoom, max_zoom = args.zoom

    base_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(base_dir, 'assets')
    cog_dir = os.path.join(assets_dir, 'cog_3857')
    output_dir = os.path.join(assets_dir, 'tiles')
    os.makedirs(output_dir, exist_ok=True)

    sides_to_process = {args.side: SIDES[args.side]} if args.side else SIDES

    grand_total = 0
    start_time = time.time()

    for side_key in sides_to_process:
        side_cog_dir = os.path.join(cog_dir, side_key)
        if not os.path.isdir(side_cog_dir):
            print(f"Warning: {side_cog_dir} not found, skipping.")
            continue

        tif_files = sorted([f for f in os.listdir(side_cog_dir)
                            if f.startswith('RasterFlood_') and f.endswith('.tif')
                            and '.tif.' not in f])

        if args.level:
            target = 'RasterFlood_' + args.level + '.tif'
            tif_files = [f for f in tif_files if f == target]

        print(f"\n{'='*60}")
        print(f"  {side_key.upper()} — {len(tif_files)} COGs → z{min_zoom}–z{max_zoom}")
        print(f"{'='*60}")

        for i, tif_file in enumerate(tif_files):
            cog_path = os.path.join(side_cog_dir, tif_file)
            print(f"  [{i+1}/{len(tif_files)}] ", end='')
            count = process_cog(cog_path, side_key, output_dir,
                                min_zoom, max_zoom)
            grand_total += count

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"DONE — {grand_total} tiles generated in {elapsed:.1f}s")
    print(f"Output: {output_dir}")
    print(f"Zoom range: z{min_zoom}–z{max_zoom}")
    print(f"\nTile URL pattern for OpenLayers:")
    print(f"  assets/tiles/{{side}}/{{level_key}}/{{z}}/{{x}}/{{y}}.png")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
