"""
Pre-render flood raster TIFFs to optimized PNGs for web display.

This script:
1. Reads each GeoTIFF raster (FundySide + NorthSide)
2. Downsamples by a configurable factor for fast web loading
3. Renders flood pixels as blue (rgba 37,99,235) with level-based opacity
4. Saves as compressed PNG with transparency
5. Writes a JSON metadata file with georeferencing info

The original high-fidelity TIFs are preserved. The PNGs are ~10-50x smaller
and eliminate the need for geotiff.js parsing and canvas rendering at runtime.
"""

import os
import sys
import json
import struct
from pathlib import Path

try:
    from PIL import Image
    import numpy as np
except ImportError:
    print("Installing required packages...")
    os.system(f"{sys.executable} -m pip install Pillow numpy")
    from PIL import Image
    import numpy as np

# Increase PIL decompression limit for large rasters
Image.MAX_IMAGE_PIXELS = 500_000_000

DOWNSAMPLE_FACTOR = 1  # Full resolution - preserves all detail, PNGs still compress 10-30x smaller
FLOOD_COLOR = (37, 99, 235)  # Blue flood color
BASE_ALPHA = 0.25  # Minimum opacity
MAX_ALPHA = 0.55   # Maximum opacity at level 11
FLOOD_MAX = 11.0

SIDES = {
    'fundy': 'FundySide',
    'north': 'NorthSide'
}

def parse_tfw(tfw_path):
    """Parse a .tfw world file to get georeferencing info."""
    with open(tfw_path, 'r') as f:
        lines = [float(line.strip()) for line in f.readlines()[:6]]
    return {
        'pixel_width': lines[0],
        'rotation_x': lines[1],
        'rotation_y': lines[2],
        'pixel_height': lines[3],  # negative
        'origin_x': lines[4],
        'origin_y': lines[5]
    }

def get_tfw_for_tif(tif_path):
    """Find the matching .tfw file for a .tif."""
    tfw_path = tif_path.replace('.tif', '.tfw')
    if os.path.exists(tfw_path):
        return tfw_path
    return None

def level_from_filename(filename):
    """Extract water level from filename like RasterFlood_5_6m.tif -> 5.6"""
    name = filename.replace('RasterFlood_', '').replace('.tif', '').replace('m', '')
    parts = name.split('_')
    if len(parts) == 2:
        return float(parts[0]) + float(parts[1]) / 10.0
    return 0.0

def get_flood_alpha(level):
    """Calculate opacity based on flood level."""
    ratio = level / FLOOD_MAX
    return int((BASE_ALPHA + ratio * (MAX_ALPHA - BASE_ALPHA)) * 255)

def prerender_tif(tif_path, output_dir, side_key, metadata_list):
    """Convert a single TIF to an optimized PNG."""
    filename = os.path.basename(tif_path)
    level = level_from_filename(filename)
    level_key = filename.replace('RasterFlood_', '').replace('.tif', '')
    
    # Find TFW for georeferencing
    tfw_path = get_tfw_for_tif(tif_path)
    
    print(f"  Processing {filename} (level {level:.1f}m)...", end=' ', flush=True)
    
    try:
        # Open and read raster
        img = Image.open(tif_path)
        orig_w, orig_h = img.size
        arr = np.array(img, dtype=np.float32)
        
        # Downsample
        new_w = max(1, orig_w // DOWNSAMPLE_FACTOR)
        new_h = max(1, orig_h // DOWNSAMPLE_FACTOR)
        
        # Reshape and take every Nth pixel (fast nearest-neighbor downsample)
        ds_arr = arr[::DOWNSAMPLE_FACTOR, ::DOWNSAMPLE_FACTOR]
        actual_h, actual_w = ds_arr.shape
        
        # Create RGBA image
        alpha = get_flood_alpha(level)
        rgba = np.zeros((actual_h, actual_w, 4), dtype=np.uint8)
        
        # Mask: non-zero, non-NaN pixels are flood
        mask = (ds_arr != 0) & (~np.isnan(ds_arr))
        rgba[mask, 0] = FLOOD_COLOR[0]  # R
        rgba[mask, 1] = FLOOD_COLOR[1]  # G
        rgba[mask, 2] = FLOOD_COLOR[2]  # B
        rgba[mask, 3] = alpha            # A
        
        # Save as optimized PNG
        out_filename = f"flood_{side_key}_{level_key}.png"
        out_path = os.path.join(output_dir, out_filename)
        out_img = Image.fromarray(rgba, 'RGBA')
        out_img.save(out_path, 'PNG', optimize=True)
        
        file_size = os.path.getsize(out_path)
        tif_size = os.path.getsize(tif_path)
        
        # Calculate extent from TFW or embedded georef
        extent = None
        if tfw_path:
            geo = parse_tfw(tfw_path)
            # Extent with downsampled pixel size
            ds_pixel_w = geo['pixel_width'] * DOWNSAMPLE_FACTOR
            ds_pixel_h = geo['pixel_height'] * DOWNSAMPLE_FACTOR  # negative
            min_x = geo['origin_x']
            max_y = geo['origin_y']
            max_x = min_x + orig_w * geo['pixel_width']
            min_y = max_y + orig_h * geo['pixel_height']
            extent = [min_x, min_y, max_x, max_y]
        
        # Store metadata
        metadata_list.append({
            'side': side_key,
            'level_key': level_key,
            'level': round(level, 1),
            'file': out_filename,
            'width': actual_w,
            'height': actual_h,
            'extent': extent,
            'projection': 'EPSG:32620'
        })
        
        ratio = tif_size / max(file_size, 1)
        print(f"OK  {actual_w}x{actual_h}  PNG: {file_size//1024}KB  (was {tif_size//1024}KB, {ratio:.1f}x smaller)")
        
        img.close()
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(base_dir, 'assets')
    output_dir = os.path.join(assets_dir, 'flood_png')
    os.makedirs(output_dir, exist_ok=True)
    
    metadata_list = []
    total_tif_size = 0
    total_png_size = 0
    count = 0
    
    for side_key, folder_name in SIDES.items():
        rasters_dir = os.path.join(assets_dir, folder_name, 'Rasters')
        if not os.path.isdir(rasters_dir):
            print(f"Warning: {rasters_dir} not found, skipping.")
            continue
        
        print(f"\n=== {folder_name} ===")
        
        tif_files = sorted([f for f in os.listdir(rasters_dir) 
                           if f.startswith('RasterFlood_') and f.endswith('.tif')
                           and not f.endswith('.tif.aux.xml')
                           and not f.endswith('.tif.ovr')
                           and not f.endswith('.tif.xml')
                           and not f.endswith('.tif.vat.cpg')
                           and not f.endswith('.tif.vat.dbf')])
        
        for tif_file in tif_files:
            tif_path = os.path.join(rasters_dir, tif_file)
            tif_size = os.path.getsize(tif_path)
            total_tif_size += tif_size
            
            if prerender_tif(tif_path, output_dir, side_key, metadata_list):
                png_file = f"flood_{side_key}_{tif_file.replace('RasterFlood_', '').replace('.tif', '')}.png"
                png_path = os.path.join(output_dir, png_file)
                if os.path.exists(png_path):
                    total_png_size += os.path.getsize(png_path)
                count += 1
    
    # Write metadata JSON
    meta_path = os.path.join(output_dir, 'metadata.json')
    with open(meta_path, 'w') as f:
        json.dump({
            'downsample_factor': DOWNSAMPLE_FACTOR,
            'flood_color': list(FLOOD_COLOR),
            'projection': 'EPSG:32620',
            'layers': metadata_list
        }, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"Pre-rendered {count} flood layers")
    print(f"Total TIF size: {total_tif_size // (1024*1024)} MB")
    print(f"Total PNG size: {total_png_size // (1024*1024)} MB")
    print(f"Compression ratio: {total_tif_size / max(total_png_size, 1):.1f}x")
    print(f"Metadata: {meta_path}")
    print(f"Output: {output_dir}")

if __name__ == '__main__':
    main()
