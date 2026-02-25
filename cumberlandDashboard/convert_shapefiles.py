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

# Flood levels to convert (0.1m increments)
# filenames use an underscore as the decimal separator (e.g. "0_1m" -> 0.1 m).
# helpers for creating and interpreting those labels are defined below so the
# script can treat the underscore as a decimal point when reporting or
# otherwise working with the elevation value.

MAX_LEVEL = 11.0    # maximum depth in metres; change as needed
STEP      = 0.1     # increment in metres (0.1 = 10 cm)


def level_label(meters: float) -> str:
    """Return a flood level string for a given depth.
    Examples:
        0.0 -> '0_0m'
        0.1 -> '0_1m'
        2.3 -> '2_3m'
    """
    whole = int(meters)
    tenths = int(round((meters - whole) * 10))
    return f"{whole}_{tenths}m"


def parse_label(label: str) -> float:
    """Convert a label like '0_1m' back to a float (0.1).
    The underscore is treated as the decimal point.
    """
    return float(label.replace('_', '.').rstrip('m'))

# build the list of labels we need to process
LEVELS = [level_label(i * STEP) for i in range(int(MAX_LEVEL / STEP) + 1)]

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
            # convert label back to a numeric value for human‑readable output
            depth_m = parse_label(level)
            print(
                f"  OK: flood_{side_name}_{level}.geojson "
                f"({fsize:.0f} KB, {len(gdf)} features, {depth_m:.1f} m)"
            )
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
