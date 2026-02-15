"""
Convert Cumberland County flood shapefiles to GeoJSON (WGS84)
Converts at 1.0m increments for both FundySide and NorthSide
"""
import geopandas as gpd
import os
import json

# Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'assets', 'geojson')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Flood levels to convert (1.0m increments)
LEVELS = [
    '0_0m', '1_0m', '2_0m', '3_0m', '4_0m', '5_0m',
    '6_0m', '7_0m', '8_0m', '9_0m', '10_0m', '11_0m'
]

SIDES = {
    'fundy': os.path.join(BASE_DIR, 'assets', 'FundySide', 'Shapefiles'),
    'north': os.path.join(BASE_DIR, 'assets', 'NorthSide', 'Shapefiles')
}

converted = 0
errors = []

for side_name, shp_dir in SIDES.items():
    print(f"\n--- Processing {side_name} ---")
    for level in LEVELS:
        shp_file = os.path.join(shp_dir, f'Flood_{level}.shp')
        if not os.path.exists(shp_file):
            print(f"  SKIP: Flood_{level}.shp not found")
            errors.append(f"{side_name}/Flood_{level}.shp")
            continue
        
        try:
            gdf = gpd.read_file(shp_file)
            # Reproject from UTM 20N to WGS84
            if gdf.crs and gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs(epsg=4326)
            
            # Simplify geometry for web performance (tolerance in degrees ~5m)
            gdf['geometry'] = gdf['geometry'].simplify(tolerance=0.00005, preserve_topology=True)
            
            # Remove empty geometries
            gdf = gdf[~gdf.geometry.is_empty]
            
            out_file = os.path.join(OUTPUT_DIR, f'flood_{side_name}_{level}.geojson')
            gdf.to_file(out_file, driver='GeoJSON')
            
            fsize = os.path.getsize(out_file) / 1024
            print(f"  OK: flood_{side_name}_{level}.geojson ({fsize:.0f} KB, {len(gdf)} features)")
            converted += 1
        except Exception as e:
            print(f"  ERROR: {level} - {e}")
            errors.append(f"{side_name}/Flood_{level}.shp: {e}")

# Also convert ocean point files
print("\n--- Processing ocean points ---")
ocean_files = [
    ('fundy', os.path.join(BASE_DIR, 'assets', 'FundySide', 'oceanpoint.shp')),
    ('north', os.path.join(BASE_DIR, 'assets', 'NorthSide', 'northumberland_op.shp'))
]

for side_name, shp_file in ocean_files:
    if os.path.exists(shp_file):
        try:
            gdf = gpd.read_file(shp_file)
            if gdf.crs and gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs(epsg=4326)
            out_file = os.path.join(OUTPUT_DIR, f'oceanpoint_{side_name}.geojson')
            gdf.to_file(out_file, driver='GeoJSON')
            print(f"  OK: oceanpoint_{side_name}.geojson ({len(gdf)} features)")
            converted += 1
        except Exception as e:
            print(f"  ERROR: {side_name} ocean point - {e}")

print(f"\n=== Done: {converted} files converted ===")
if errors:
    print(f"Errors/skips: {len(errors)}")
    for e in errors:
        print(f"  - {e}")
