"""
Generate XYZ map tiles from the AGRG Color Shaded Relief (CSR) COGTiff.

Source: newData/Cumber_HydroDEM_NoAboiteau_CSRp_1m_Clipped_COGTiff.tif
  - 160984x86390 pixels, 3-band RGB, 8.3GB, EPSG:26920 (NAD83 UTM 20N)
  - 1m resolution hydro-conditioned DEM color shaded relief

Strategy: The file is too large to reproject in-memory. Instead we use
rasterio.vrt.WarpedVRT to create a virtual reprojected view, then read
individual tile windows on-the-fly. This processes only the pixels needed
for each tile, avoiding a massive intermediate file.

Output: assets/tiles/csr/{z}/{x}/{y}.png

Usage:
  python generate_csr_tiles.py                    # Generate all tiles
  python generate_csr_tiles.py --zoom 8 15        # Custom zoom range
"""

import os
import sys
import math
import argparse
import time

try:
    import rasterio
    from rasterio.vrt import WarpedVRT
    from rasterio.windows import from_bounds as window_from_bounds
    from rasterio.enums import Resampling
    import numpy as np
    from PIL import Image
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install rasterio numpy Pillow")
    sys.exit(1)

os.environ['CHECK_DISK_FREE_SPACE'] = 'FALSE'
# Use GDAL caching for performance with large COGs
os.environ['GDAL_CACHEMAX'] = '512'

TILE_SIZE = 256
MIN_ZOOM = 8
MAX_ZOOM = 15

ORIGIN_SHIFT = 2 * math.pi * 6378137 / 2.0

SOURCE_TIF = 'newData/Cumber_HydroDEM_NoAboiteau_CSRp_1m_Clipped_COGTiff.tif'


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


def generate_csr_tile(vrt, tile_x, tile_y, zoom, output_dir):
    """Generate a single CSR basemap tile from WarpedVRT (already in EPSG:3857)."""
    bounds = tile_bounds_3857(tile_x, tile_y, zoom)
    rb = vrt.bounds
    if bounds[0] >= rb.right or bounds[2] <= rb.left or \
       bounds[1] >= rb.top or bounds[3] <= rb.bottom:
        return False

    try:
        # Clip requested bounds to VRT extent (WarpedVRT does not support boundless reads)
        clipped_left = max(bounds[0], rb.left)
        clipped_bottom = max(bounds[1], rb.bottom)
        clipped_right = min(bounds[2], rb.right)
        clipped_top = min(bounds[3], rb.top)

        if clipped_left >= clipped_right or clipped_bottom >= clipped_top:
            return False

        # Calculate pixel offsets for partial tiles (where tile extends beyond VRT)
        tile_width_m = bounds[2] - bounds[0]
        tile_height_m = bounds[3] - bounds[1]
        px_left = int(round((clipped_left - bounds[0]) / tile_width_m * TILE_SIZE))
        px_top = int(round((bounds[3] - clipped_top) / tile_height_m * TILE_SIZE))
        px_right = int(round((clipped_right - bounds[0]) / tile_width_m * TILE_SIZE))
        px_bottom = int(round((bounds[3] - clipped_bottom) / tile_height_m * TILE_SIZE))

        out_w = max(px_right - px_left, 1)
        out_h = max(px_bottom - px_top, 1)

        # Clamp to valid range
        if out_w > TILE_SIZE: out_w = TILE_SIZE
        if out_h > TILE_SIZE: out_h = TILE_SIZE

        window = window_from_bounds(
            clipped_left, clipped_bottom, clipped_right, clipped_top,
            transform=vrt.transform
        )

        # Ensure window has positive dimensions
        if window.width < 1 or window.height < 1:
            return False

        # Read all 3 RGB bands at the clipped tile resolution
        band_count = min(vrt.count, 3)
        data = vrt.read(
            list(range(1, band_count + 1)),
            window=window,
            out_shape=(band_count, out_h, out_w),
            resampling=Resampling.bilinear
        )
    except Exception:
        return False

    # Check if tile has any non-zero data (not all nodata/black)
    if band_count >= 3:
        mask = (data[0] != 0) | (data[1] != 0) | (data[2] != 0)
        if not mask.any():
            return False

        # Build full 256x256 RGBA canvas (transparent background for partial edge tiles)
        rgba = np.zeros((TILE_SIZE, TILE_SIZE, 4), dtype=np.uint8)
        sub_alpha = np.where(mask, 255, 0).astype(np.uint8)
        rgba[px_top:px_top+out_h, px_left:px_left+out_w, 0] = data[0].astype(np.uint8)
        rgba[px_top:px_top+out_h, px_left:px_left+out_w, 1] = data[1].astype(np.uint8)
        rgba[px_top:px_top+out_h, px_left:px_left+out_w, 2] = data[2].astype(np.uint8)
        rgba[px_top:px_top+out_h, px_left:px_left+out_w, 3] = sub_alpha
    elif band_count == 1:
        gray = data[0].astype(np.uint8)
        mask = gray != 0
        if not mask.any():
            return False
        rgba = np.zeros((TILE_SIZE, TILE_SIZE, 4), dtype=np.uint8)
        sub_alpha = np.where(mask, 255, 0).astype(np.uint8)
        rgba[px_top:px_top+out_h, px_left:px_left+out_w, 0] = gray
        rgba[px_top:px_top+out_h, px_left:px_left+out_w, 1] = gray
        rgba[px_top:px_top+out_h, px_left:px_left+out_w, 2] = gray
        rgba[px_top:px_top+out_h, px_left:px_left+out_w, 3] = sub_alpha
    else:
        return False

    # Save tile
    tile_dir = os.path.join(output_dir, str(zoom), str(tile_x))
    os.makedirs(tile_dir, exist_ok=True)
    tile_path = os.path.join(tile_dir, f"{tile_y}.png")

    img = Image.fromarray(rgba, 'RGBA')
    img.save(tile_path, 'PNG', optimize=True)
    return True


def main():
    parser = argparse.ArgumentParser(description='Generate CSR basemap XYZ tiles')
    parser.add_argument('--zoom', nargs=2, type=int, default=[MIN_ZOOM, MAX_ZOOM],
                        metavar=('MIN', 'MAX'))
    args = parser.parse_args()

    min_zoom, max_zoom = args.zoom
    base_dir = os.path.dirname(os.path.abspath(__file__))
    src_tif = os.path.join(base_dir, SOURCE_TIF)
    output_dir = os.path.join(base_dir, 'assets', 'tiles', 'csr')
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(src_tif):
        print(f"ERROR: Source TIF not found: {src_tif}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  CSR BASEMAP TILE GENERATION")
    print(f"  Source: {SOURCE_TIF}")
    print(f"  Zoom: z{min_zoom}–z{max_zoom}")
    print(f"  Method: WarpedVRT (on-the-fly reprojection per tile)")
    print(f"{'='*60}")

    start_time = time.time()
    grand_total = 0

    # Open source and wrap in WarpedVRT for on-the-fly reprojection to EPSG:3857
    # This avoids creating a massive intermediate reprojected file
    with rasterio.open(src_tif) as src:
        print(f"  Source CRS: {src.crs} | Size: {src.width}x{src.height} | Bands: {src.count}")
        print(f"  Opening WarpedVRT (EPSG:3857)...")

        with WarpedVRT(src, crs='EPSG:3857', resampling=Resampling.bilinear) as vrt:
            bounds_3857 = (vrt.bounds.left, vrt.bounds.bottom,
                           vrt.bounds.right, vrt.bounds.top)
            print(f"  VRT bounds: {bounds_3857}")
            print(f"  VRT size: {vrt.width}x{vrt.height}")
            print()

            for zoom in range(min_zoom, max_zoom + 1):
                tiles = get_tiles_for_bounds(bounds_3857, zoom)
                zoom_count = 0
                zoom_start = time.time()

                for i, (tx, ty, z) in enumerate(tiles):
                    if generate_csr_tile(vrt, tx, ty, z, output_dir):
                        zoom_count += 1

                    # Progress indicator for large zoom levels
                    if (i + 1) % 50 == 0:
                        pct = (i + 1) / len(tiles) * 100
                        print(f"    z{zoom}: {i+1}/{len(tiles)} ({pct:.0f}%) - {zoom_count} tiles so far", end='\r')

                zoom_elapsed = time.time() - zoom_start
                grand_total += zoom_count
                print(f"    z{zoom}: {zoom_count} tiles from {len(tiles)} candidates ({zoom_elapsed:.1f}s)     ")

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"DONE — {grand_total} CSR tiles in {elapsed:.1f}s")
    print(f"Output: {output_dir}/{{z}}/{{x}}/{{y}}.png")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
