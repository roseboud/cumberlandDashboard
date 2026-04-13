"""
Generate XYZ map tiles from NEW AGRG storm surge RasterFlood data.

Source data: newData/Fundy/ and newData/Northumberland/
  - Present_Day/, 2050/, 2100/, 2100+AA/
  - Each contains RasterFlood_*.tif depth rasters + shapefiles

Pipeline (same as proven surge tile generation):
  Step 1: Reproject source TIF to EPSG:3857 compressed COG
  Step 2: Generate XYZ PNG tiles (depth = red gradient, extent = cyan-blue)

Output structure:
  assets/tiles/surge/{side}/{scenario}/{z}/{x}/{y}.png      (depth)
  assets/tiles/surge_extent/{side}/{scenario}/{z}/{x}/{y}.png (extent)

Usage:
  python generate_new_surge_tiles.py                          # All scenarios
  python generate_new_surge_tiles.py --side fundy             # One side only
  python generate_new_surge_tiles.py --scenario 20yr_present  # Single scenario
  python generate_new_surge_tiles.py --skip-reproject         # Use existing COGs
  python generate_new_surge_tiles.py --extent-only            # Only generate extent tiles
"""

import os
import sys
import math
import argparse
import time
from pathlib import Path

try:
    import rasterio
    from rasterio.windows import from_bounds as window_from_bounds
    from rasterio.enums import Resampling
    from rasterio.warp import calculate_default_transform, reproject
    import numpy as np
    from PIL import Image
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install rasterio numpy Pillow")
    sys.exit(1)

os.environ['CHECK_DISK_FREE_SPACE'] = 'FALSE'

# ─── Configuration ───────────────────────────────────────────────────────────

TILE_SIZE = 256
MIN_ZOOM = 10
MAX_ZOOM = 15

# Depth tile colors
SURGE_COLOR = (220, 38, 38)    # Red surge color
BASE_ALPHA = 0.30
MAX_ALPHA = 0.75
MAX_DEPTH = 5.0

# Extent tile colors
EXTENT_COLOR = (6, 147, 227)
EXTENT_ALPHA = 160
BORDER_COLOR = (3, 105, 161)
BORDER_ALPHA = 210

# Web Mercator constants
ORIGIN_SHIFT = 2 * math.pi * 6378137 / 2.0

# Source data mapping
# newData/{Side}/{Horizon}/RasterFlood_{prefix}_{return}.tif
SIDES = {
    'fundy': 'Fundy',
    'north': 'Northumberland',
}

HORIZONS = {
    'present': {
        'folder': 'Present_Day',
        'prefix': '',          # RasterFlood_20_yr.tif, RasterFlood_100_yr.tif
    },
    '2050': {
        'folder': '2050',
        'prefix': '2050_',     # RasterFlood_2050_20_yr.tif
    },
    '2100': {
        'folder': '2100',
        'prefix': '2100_',     # RasterFlood_2100_20_yr.tif
    },
    '2100AA': {
        'folder': '2100+AA',
        'prefix': '2100AA_',   # RasterFlood_2100AA_20_yr.tif
    },
}

RETURN_PERIODS = ['20yr', '100yr']


def get_source_tif(base_dir, side_key, horizon_key, return_period):
    """Get the source TIF path for a given scenario."""
    side_folder = SIDES[side_key]
    horizon = HORIZONS[horizon_key]
    rp = return_period.replace('yr', '_yr')  # 20yr -> 20_yr
    filename = f"RasterFlood_{horizon['prefix']}{rp}.tif"
    return os.path.join(base_dir, 'newData', side_folder, horizon['folder'], filename)


# ─── XYZ Tile Math (EPSG:3857) ──────────────────────────────────────────────

def tile_bounds_3857(x, y, z):
    n = 2 ** z
    tile_size_m = 2 * ORIGIN_SHIFT / n
    min_x = -ORIGIN_SHIFT + x * tile_size_m
    max_x = min_x + tile_size_m
    max_y = ORIGIN_SHIFT - y * tile_size_m
    min_y = max_y - tile_size_m
    return (min_x, min_y, max_x, max_y)


def get_tiles_for_bounds(bounds_3857, zoom):
    min_x, min_y, max_x, max_y = bounds_3857
    n = 2 ** zoom
    tile_size_m = 2 * ORIGIN_SHIFT / n
    min_x = max(min_x, -ORIGIN_SHIFT)
    max_x = min(max_x, ORIGIN_SHIFT)
    min_y = max(min_y, -ORIGIN_SHIFT)
    max_y = min(max_y, ORIGIN_SHIFT)
    x_min = int(math.floor((min_x + ORIGIN_SHIFT) / tile_size_m))
    x_max = int(math.floor((max_x + ORIGIN_SHIFT) / tile_size_m))
    y_min = int(math.floor((ORIGIN_SHIFT - max_y) / tile_size_m))
    y_max = int(math.floor((ORIGIN_SHIFT - min_y) / tile_size_m))
    x_min = max(0, x_min)
    x_max = min(n - 1, x_max)
    y_min = max(0, y_min)
    y_max = min(n - 1, y_max)
    tiles = []
    for ty in range(y_min, y_max + 1):
        for tx in range(x_min, x_max + 1):
            tiles.append((tx, ty, zoom))
    return tiles


# ─── Step 1: Reproject ──────────────────────────────────────────────────────

def reproject_to_3857_cog(src_path, dst_path):
    with rasterio.open(src_path) as src:
        if src.crs and src.crs.to_epsg() == 3857:
            import shutil
            shutil.copy2(src_path, dst_path)
            return dst_path

        transform, width, height = calculate_default_transform(
            src.crs, 'EPSG:3857', src.width, src.height, *src.bounds
        )
        kwargs = src.meta.copy()
        kwargs.update({
            'crs': 'EPSG:3857',
            'transform': transform,
            'width': width,
            'height': height,
            'driver': 'GTiff',
            'compress': 'deflate',
            'tiled': True,
            'blockxsize': 256,
            'blockysize': 256,
        })
        with rasterio.open(dst_path, 'w', **kwargs) as dst:
            for band in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, band),
                    destination=rasterio.band(dst, band),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs='EPSG:3857',
                    resampling=Resampling.nearest
                )
    return dst_path


# ─── Step 2: Tile Generation ────────────────────────────────────────────────

def generate_depth_tile(src, tile_x, tile_y, zoom, output_dir, side_key, scenario_key):
    bounds = tile_bounds_3857(tile_x, tile_y, zoom)
    rb = src.bounds
    if bounds[0] >= rb.right or bounds[2] <= rb.left or \
       bounds[1] >= rb.top or bounds[3] <= rb.bottom:
        return False
    try:
        window = window_from_bounds(bounds[0], bounds[1], bounds[2], bounds[3], transform=src.transform)
        data = src.read(1, window=window, out_shape=(TILE_SIZE, TILE_SIZE),
                        resampling=Resampling.nearest, boundless=True, fill_value=0)
    except Exception:
        return False

    nodata = src.nodata
    if nodata is not None:
        mask = (data != 0) & (data != nodata) & (~np.isnan(data)) & (data < 1e30)
    else:
        mask = (data != 0) & (~np.isnan(data)) & (data < 1e30)
    if not mask.any():
        return False

    depth_ratio = np.clip(data / MAX_DEPTH, 0, 1)
    alpha_values = (BASE_ALPHA + depth_ratio * (MAX_ALPHA - BASE_ALPHA)) * 255
    rgba = np.zeros((TILE_SIZE, TILE_SIZE, 4), dtype=np.uint8)
    rgba[mask, 0] = SURGE_COLOR[0]
    rgba[mask, 1] = SURGE_COLOR[1]
    rgba[mask, 2] = SURGE_COLOR[2]
    rgba[mask, 3] = alpha_values[mask].astype(np.uint8)

    tile_dir = os.path.join(output_dir, side_key, scenario_key, str(zoom), str(tile_x))
    os.makedirs(tile_dir, exist_ok=True)
    img = Image.fromarray(rgba, 'RGBA')
    img.save(os.path.join(tile_dir, f"{tile_y}.png"), 'PNG', optimize=True)
    return True


def generate_extent_tile(src, tile_x, tile_y, zoom, output_dir, side_key, scenario_key):
    bounds = tile_bounds_3857(tile_x, tile_y, zoom)
    rb = src.bounds
    if bounds[0] >= rb.right or bounds[2] <= rb.left or \
       bounds[1] >= rb.top or bounds[3] <= rb.bottom:
        return False
    try:
        window = window_from_bounds(bounds[0], bounds[1], bounds[2], bounds[3], transform=src.transform)
        data = src.read(1, window=window, out_shape=(TILE_SIZE, TILE_SIZE),
                        resampling=Resampling.nearest, boundless=True, fill_value=0)
    except Exception:
        return False

    nodata = src.nodata
    if nodata is not None:
        mask = (data != 0) & (data != nodata) & (~np.isnan(data)) & (data < 1e30)
    else:
        mask = (data != 0) & (~np.isnan(data)) & (data < 1e30)
    if not mask.any():
        return False

    rgba = np.zeros((TILE_SIZE, TILE_SIZE, 4), dtype=np.uint8)
    rgba[mask, 0] = EXTENT_COLOR[0]
    rgba[mask, 1] = EXTENT_COLOR[1]
    rgba[mask, 2] = EXTENT_COLOR[2]
    rgba[mask, 3] = EXTENT_ALPHA

    # Edge detection
    pad_mask = np.pad(mask, 1, mode='constant', constant_values=False)
    edges = mask & (
        ~pad_mask[:-2, 1:-1] | ~pad_mask[2:, 1:-1] |
        ~pad_mask[1:-1, :-2] | ~pad_mask[1:-1, 2:]
    )
    rgba[edges, 0] = BORDER_COLOR[0]
    rgba[edges, 1] = BORDER_COLOR[1]
    rgba[edges, 2] = BORDER_COLOR[2]
    rgba[edges, 3] = BORDER_ALPHA

    tile_dir = os.path.join(output_dir, side_key, scenario_key, str(zoom), str(tile_x))
    os.makedirs(tile_dir, exist_ok=True)
    img = Image.fromarray(rgba, 'RGBA')
    img.save(os.path.join(tile_dir, f"{tile_y}.png"), 'PNG', optimize=True)
    return True


def process_scenario(cog_path, side_key, scenario_key, depth_dir, extent_dir, min_zoom, max_zoom, extent_only=False):
    print(f"  Generating tiles for {side_key}/{scenario_key}...")
    with rasterio.open(cog_path) as src:
        if src.crs and src.crs.to_epsg() != 3857:
            print(f"    WARNING: CRS is {src.crs}, expected EPSG:3857. Skipping.")
            return 0
        bounds_3857 = (src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top)
        total_tiles = 0
        for zoom in range(min_zoom, max_zoom + 1):
            tiles = get_tiles_for_bounds(bounds_3857, zoom)
            depth_count = 0
            extent_count = 0
            for tx, ty, z in tiles:
                if not extent_only:
                    if generate_depth_tile(src, tx, ty, z, depth_dir, side_key, scenario_key):
                        depth_count += 1
                if generate_extent_tile(src, tx, ty, z, extent_dir, side_key, scenario_key):
                    extent_count += 1
            total_tiles += depth_count + extent_count
            if not extent_only:
                print(f"    z{zoom}: {depth_count} depth + {extent_count} extent tiles")
            else:
                print(f"    z{zoom}: {extent_count} extent tiles")
        return total_tiles


def main():
    parser = argparse.ArgumentParser(description='Generate XYZ tiles from new AGRG surge data')
    parser.add_argument('--side', choices=['fundy', 'north'], default=None)
    parser.add_argument('--scenario', type=str, default=None,
                        help='Single scenario key (e.g., 20yr_present, 100yr_2100AA)')
    parser.add_argument('--zoom', nargs=2, type=int, default=[MIN_ZOOM, MAX_ZOOM])
    parser.add_argument('--skip-reproject', action='store_true')
    parser.add_argument('--extent-only', action='store_true')
    args = parser.parse_args()

    min_zoom, max_zoom = args.zoom
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cog_dir = os.path.join(base_dir, 'assets', 'cog_3857', 'surge_new')
    depth_dir = os.path.join(base_dir, 'assets', 'tiles', 'surge')
    extent_dir = os.path.join(base_dir, 'assets', 'tiles', 'surge_extent')
    os.makedirs(cog_dir, exist_ok=True)
    os.makedirs(depth_dir, exist_ok=True)
    os.makedirs(extent_dir, exist_ok=True)

    # Build scenario list
    sides_to_process = [args.side] if args.side else list(SIDES.keys())
    scenarios = []
    for side_key in sides_to_process:
        for horizon_key in HORIZONS:
            for rp in RETURN_PERIODS:
                scenario_key = f"{rp}_{horizon_key}"
                if args.scenario and scenario_key != args.scenario:
                    continue
                scenarios.append((side_key, horizon_key, rp, scenario_key))

    grand_total = 0
    start_time = time.time()

    print(f"\n{'='*60}")
    print(f"  NEW AGRG SURGE TILE GENERATION")
    print(f"  Scenarios: {len(scenarios)} | Zoom: z{min_zoom}–z{max_zoom}")
    print(f"  Step 1: Reproject to EPSG:3857 COG")
    print(f"  Step 2: Generate depth + extent XYZ PNG tiles")
    print(f"{'='*60}")

    for side_key, horizon_key, rp, scenario_key in scenarios:
        src_tif = get_source_tif(base_dir, side_key, horizon_key, rp)
        cog_path = os.path.join(cog_dir, f"{side_key}_{scenario_key}.tif")

        if not os.path.exists(src_tif):
            print(f"  SKIP: {src_tif} not found")
            continue

        # Step 1: Reproject
        if not args.skip_reproject:
            if os.path.exists(cog_path) and os.path.getmtime(cog_path) > os.path.getmtime(src_tif):
                print(f"  [{side_key}/{scenario_key}] COG exists — skipping reproject")
            else:
                print(f"  [{side_key}/{scenario_key}] Reprojecting to EPSG:3857...")
                t0 = time.time()
                try:
                    reproject_to_3857_cog(src_tif, cog_path)
                    src_mb = os.path.getsize(src_tif) // (1024*1024)
                    dst_mb = os.path.getsize(cog_path) // (1024*1024)
                    print(f"    Done in {time.time()-t0:.1f}s ({src_mb}MB → {dst_mb}MB)")
                except Exception as e:
                    print(f"    ERROR reprojecting: {e}")
                    continue
        else:
            if not os.path.exists(cog_path):
                print(f"  SKIP: COG not found for {side_key}/{scenario_key}")
                continue

        # Step 2: Generate tiles
        count = process_scenario(cog_path, side_key, scenario_key,
                                 depth_dir, extent_dir, min_zoom, max_zoom,
                                 args.extent_only)
        grand_total += count

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"DONE — {grand_total} tiles generated in {elapsed:.1f}s")
    print(f"Depth tiles: {depth_dir}/{{side}}/{{scenario}}/{{z}}/{{x}}/{{y}}.png")
    print(f"Extent tiles: {extent_dir}/{{side}}/{{scenario}}/{{z}}/{{x}}/{{y}}.png")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
