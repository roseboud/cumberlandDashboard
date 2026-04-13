"""
Generate XYZ map tiles from storm surge FloodDepth rasters for web display.

Follows the EXACT same 2-step pipeline proven with flood tiles:
  Step 1: Reproject source TIF to EPSG:3857 compressed COG (reproject_cogs.py pattern)
  Step 2: Generate XYZ PNG tiles from the COG (generate_tiles.py pattern)

The source rasters are flood DEPTH data (metres of water above ground).
NoData = 3.4e+38. Valid data: positive float32 values (typically 0.1–5.0m).
CRS: Mercator Atlantic Canada (NAD83 CSRS v7) → EPSG:3857.

Usage:
  python generate_surge_tiles.py                        # Process all scenarios
  python generate_surge_tiles.py --scenario 20yr_2020   # Single scenario
  python generate_surge_tiles.py --zoom 10 14           # Custom zoom range
  python generate_surge_tiles.py --skip-reproject        # Skip reprojection (use existing COGs)
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

# Disable GDAL disk space check (compressed output is much smaller than estimate)
os.environ['CHECK_DISK_FREE_SPACE'] = 'FALSE'

# ─── Configuration ───────────────────────────────────────────────────────────

TILE_SIZE = 256
SURGE_COLOR = (220, 38, 38)    # Red surge color (matches frontend)
BASE_ALPHA = 0.30              # Min opacity for shallow depth
MAX_ALPHA = 0.75               # Max opacity for deep depth
MAX_DEPTH = 5.0                # Expected max depth for alpha scaling

MIN_ZOOM = 10
MAX_ZOOM = 15

# Web Mercator constants
ORIGIN_SHIFT = 2 * math.pi * 6378137 / 2.0

# Scenario file mapping
# Source: newData/FloodDepth_NW_Clipped/FloodDepth_NW_Clipped/
SCENARIOS = {
    '20yr_2020': 'Surge_20yr_2020NWFD_Cumberland.tif',
    '20yr_2050': 'Surge_20yr_2050NWFD_Cumberland.tif',
    '20yr_2100': 'Surge_20yr_2100NWFD_Cumberland.tif',
    '20yr_2150': 'Surge_20yr_2150NWFD_Cumberland.tif',
    '100yr_2020': 'Surge_100yr_2020NWFD_Cumberland.tif',
    '100yr_2050': 'Surge_100yr_2050NWFD_Cumberland.tif',
    '100yr_2100': 'Surge_100yr_2100NWFD_Cumberland.tif',
    '100yr_2150': 'Surge_100yr_2150NWFD_Cumberland.tif',
}


# ─── XYZ Tile Math (EPSG:3857) ──────────────────────────────────────────────

def tile_bounds_3857(x, y, z):
    """Get EPSG:3857 bounds for an XYZ tile (XYZ scheme: y=0 at top)."""
    n = 2 ** z
    tile_size_m = 2 * ORIGIN_SHIFT / n
    min_x = -ORIGIN_SHIFT + x * tile_size_m
    max_x = min_x + tile_size_m
    max_y = ORIGIN_SHIFT - y * tile_size_m
    min_y = max_y - tile_size_m
    return (min_x, min_y, max_x, max_y)


def get_tiles_for_bounds(bounds_3857, zoom):
    """Get all XYZ tile coordinates that intersect the given EPSG:3857 bounds."""
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


# ─── Step 1: Reproject to EPSG:3857 COG ─────────────────────────────────────
# Follows reproject_cogs.py pattern exactly

def reproject_to_3857_cog(src_path, dst_path):
    """Reproject a single TIF to EPSG:3857 as a compressed tiled GeoTIFF."""
    with rasterio.open(src_path) as src:
        if src.crs and src.crs.to_epsg() == 3857:
            print("    Already EPSG:3857, copying...")
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


# ─── Step 2: Generate XYZ Tiles from COG ────────────────────────────────────
# Follows generate_tiles.py pattern exactly

def get_surge_alpha(depth):
    """Calculate opacity (0–255) based on flood depth."""
    ratio = min(depth / MAX_DEPTH, 1.0)
    return int((BASE_ALPHA + ratio * (MAX_ALPHA - BASE_ALPHA)) * 255)


def generate_tile(src, tile_x, tile_y, zoom, output_dir, scenario_key):
    """Generate a single XYZ tile PNG from the raster source."""
    bounds = tile_bounds_3857(tile_x, tile_y, zoom)

    # Check if tile bounds intersect the raster
    rb = src.bounds
    if bounds[0] >= rb.right or bounds[2] <= rb.left or \
       bounds[1] >= rb.top or bounds[3] <= rb.bottom:
        return False

    # Use rasterio windowed read — GDAL handles resampling internally
    try:
        window = window_from_bounds(
            bounds[0], bounds[1], bounds[2], bounds[3],
            transform=src.transform
        )

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

    # Check for valid flood data (same pattern as generate_tiles.py)
    nodata = src.nodata
    if nodata is not None:
        mask = (data != 0) & (data != nodata) & (~np.isnan(data)) & (data < 1e30)
    else:
        mask = (data != 0) & (~np.isnan(data)) & (data < 1e30)

    if not mask.any():
        return False

    # Create RGBA tile — depth-based alpha
    depth_ratio = np.clip(data / MAX_DEPTH, 0, 1)
    alpha_values = (BASE_ALPHA + depth_ratio * (MAX_ALPHA - BASE_ALPHA)) * 255

    rgba = np.zeros((TILE_SIZE, TILE_SIZE, 4), dtype=np.uint8)
    rgba[mask, 0] = SURGE_COLOR[0]
    rgba[mask, 1] = SURGE_COLOR[1]
    rgba[mask, 2] = SURGE_COLOR[2]
    rgba[mask, 3] = alpha_values[mask].astype(np.uint8)

    # Save as PNG
    tile_dir = os.path.join(output_dir, scenario_key, str(zoom), str(tile_x))
    os.makedirs(tile_dir, exist_ok=True)
    tile_path = os.path.join(tile_dir, f"{tile_y}.png")

    img = Image.fromarray(rgba, 'RGBA')
    img.save(tile_path, 'PNG', optimize=True)
    return True


def process_scenario(scenario_key, cog_path, output_dir, min_zoom, max_zoom):
    """Process a single surge COG into XYZ tiles (same as generate_tiles.py)."""
    print(f"  Generating tiles for {scenario_key}...")

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
                if generate_tile(src, tx, ty, z, output_dir, scenario_key):
                    zoom_count += 1

            total_tiles += zoom_count
            print(f"    z{zoom}: {zoom_count} tiles")

        print(f"    → {total_tiles} tiles (z{min_zoom}–z{max_zoom})")
        return total_tiles


def main():
    parser = argparse.ArgumentParser(
        description='Generate XYZ tiles from storm surge FloodDepth rasters')
    parser.add_argument('--scenario', type=str, default=None,
                        help='Process single scenario (e.g., 20yr_2020)')
    parser.add_argument('--zoom', nargs=2, type=int, default=[MIN_ZOOM, MAX_ZOOM],
                        metavar=('MIN', 'MAX'),
                        help=f'Zoom range (default {MIN_ZOOM} {MAX_ZOOM})')
    parser.add_argument('--skip-reproject', action='store_true',
                        help='Skip reprojection step (use existing COGs)')
    args = parser.parse_args()

    min_zoom, max_zoom = args.zoom
    base_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(base_dir, 'newData', 'FloodDepth_NW_Clipped', 'FloodDepth_NW_Clipped')
    cog_dir = os.path.join(base_dir, 'assets', 'cog_3857', 'surge')
    output_dir = os.path.join(base_dir, 'assets', 'tiles', 'surge')
    os.makedirs(cog_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    scenarios = {args.scenario: SCENARIOS[args.scenario]} if args.scenario else SCENARIOS

    grand_total = 0
    start_time = time.time()

    print(f"\n{'='*60}")
    print(f"  STORM SURGE TILE GENERATION")
    print(f"  Scenarios: {len(scenarios)} | Zoom: z{min_zoom}–z{max_zoom}")
    print(f"  Step 1: Reproject to EPSG:3857 COG (compressed)")
    print(f"  Step 2: Generate XYZ PNG tiles")
    print(f"{'='*60}")

    for key, filename in scenarios.items():
        src_tif = os.path.join(src_dir, filename)
        cog_path = os.path.join(cog_dir, f"surge_{key}.tif")

        if not os.path.exists(src_tif):
            print(f"  SKIP: {filename} not found")
            continue

        # Step 1: Reproject
        if not args.skip_reproject:
            if os.path.exists(cog_path) and os.path.getmtime(cog_path) > os.path.getmtime(src_tif):
                print(f"  [{key}] COG exists and is newer — skipping reproject")
            else:
                print(f"  [{key}] Reprojecting to EPSG:3857...")
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
                print(f"  SKIP: COG not found for {key} (run without --skip-reproject first)")
                continue

        # Step 2: Generate tiles
        count = process_scenario(key, cog_path, output_dir, min_zoom, max_zoom)
        grand_total += count

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"DONE — {grand_total} tiles generated in {elapsed:.1f}s")
    print(f"COGs: {cog_dir}")
    print(f"Tiles: {output_dir}")
    print(f"\nTile URL pattern for OpenLayers:")
    print(f"  assets/tiles/surge/{{scenario_key}}/{{z}}/{{x}}/{{y}}.png")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
