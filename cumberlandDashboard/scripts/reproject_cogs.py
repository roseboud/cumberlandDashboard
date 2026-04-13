"""
Reproject flood raster TIFs from EPSG:32620 (UTM Zone 20N) to EPSG:3857 (Web Mercator)
as Cloud-Optimized GeoTIFFs for direct use with OpenLayers WebGLTile + ol.source.GeoTIFF.

This eliminates on-the-fly reprojection in the browser, enabling GPU-accelerated rendering.
Original TIFs are NOT modified - reprojected COGs go to assets/cog_3857/
"""

import os
import sys
import glob

try:
    import rasterio
    from rasterio.warp import calculate_default_transform, reproject, Resampling
    from rasterio.transform import from_bounds
except ImportError:
    print("Installing rasterio...")
    os.system(f"{sys.executable} -m pip install rasterio")
    import rasterio
    from rasterio.warp import calculate_default_transform, reproject, Resampling

DST_CRS = 'EPSG:3857'

SIDES = {
    'fundy': 'FundySide',
    'north': 'NorthSide'
}

def reproject_tif(src_path, dst_path):
    """Reproject a single TIF to EPSG:3857 as a COG."""
    with rasterio.open(src_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, DST_CRS, src.width, src.height, *src.bounds
        )
        
        kwargs = src.meta.copy()
        kwargs.update({
            'crs': DST_CRS,
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
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=DST_CRS,
                    resampling=Resampling.nearest
                )

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(base_dir, 'assets')
    output_dir = os.path.join(assets_dir, 'cog_3857')
    os.makedirs(output_dir, exist_ok=True)
    
    total = 0
    
    for side_key, folder_name in SIDES.items():
        rasters_dir = os.path.join(assets_dir, folder_name, 'Rasters')
        if not os.path.isdir(rasters_dir):
            print(f"Warning: {rasters_dir} not found, skipping.")
            continue
        
        side_out = os.path.join(output_dir, side_key)
        os.makedirs(side_out, exist_ok=True)
        
        tif_files = sorted([f for f in os.listdir(rasters_dir) 
                           if f.startswith('RasterFlood_') and f.endswith('.tif')
                           and '.tif.' not in f])  # exclude .tif.aux.xml etc
        
        print(f"\n=== {folder_name} ({len(tif_files)} files) ===")
        
        for i, tif_file in enumerate(tif_files):
            src_path = os.path.join(rasters_dir, tif_file)
            dst_path = os.path.join(side_out, tif_file)
            
            # Skip if already reprojected and newer than source
            if os.path.exists(dst_path) and os.path.getmtime(dst_path) > os.path.getmtime(src_path):
                print(f"  [{i+1}/{len(tif_files)}] {tif_file} - SKIP (already done)")
                total += 1
                continue
            
            print(f"  [{i+1}/{len(tif_files)}] {tif_file}...", end=' ', flush=True)
            try:
                reproject_tif(src_path, dst_path)
                src_size = os.path.getsize(src_path) // 1024
                dst_size = os.path.getsize(dst_path) // 1024
                print(f"OK ({src_size}KB -> {dst_size}KB)")
                total += 1
            except Exception as e:
                print(f"ERROR: {e}")
    
    print(f"\n{'='*60}")
    print(f"Reprojected {total} files to {output_dir}")
    print(f"CRS: {DST_CRS}")

if __name__ == '__main__':
    main()
