"""
Pre-compute flood risk level for each infrastructure point.
Uses the flood GeoJSON polygons (0-11m, whole-meter increments) for both
fundy and north sides to determine the minimum flood level that inundates
each infrastructure facility.

Writes `flood_risk_m` into each feature's properties.
"""

import json
import os
import sys
import numpy as np
from pathlib import Path

try:
    import rasterio
    from rasterio.transform import rowcol
    from pyproj import Transformer
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install rasterio pyproj numpy")
    sys.exit(1)

# Transform from WGS84 (lon/lat) to EPSG:3857 (Web Mercator)
transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)

INFRA_PATH = Path('cumberlandDashboard/assets/geojson/infrastructure_cumberland.geojson')
COG_DIRS = {
    'fundy': Path('cumberlandDashboard/assets/cog_3857/fundy'),
    'north': Path('cumberlandDashboard/assets/cog_3857/north'),
}


def level_from_filename(filename):
    """Extract water level from filename like RasterFlood_5_6m.tif -> 5.6"""
    name = filename.replace('RasterFlood_', '').replace('.tif', '').replace('m', '')
    parts = name.split('_')
    if len(parts) == 2:
        return float(parts[0]) + float(parts[1]) / 10.0
    return None


def check_point_in_raster(src, x_3857, y_3857):
    """Check if a point (EPSG:3857) has flood data in an open rasterio source."""
    if (x_3857 < src.bounds.left or x_3857 > src.bounds.right or
            y_3857 < src.bounds.bottom or y_3857 > src.bounds.top):
        return False
    try:
        row, col = rowcol(src.transform, x_3857, y_3857)
        if row < 0 or col < 0 or row >= src.height or col >= src.width:
            return False
        val = src.read(1, window=rasterio.windows.Window(col, row, 1, 1))[0, 0]
        nodata = src.nodata
        if nodata is not None and val == nodata:
            return False
        if np.isnan(val) or val == 0:
            return False
        return True
    except Exception:
        return False


def point_in_polygon(px, py, polygon_coords):
    """Ray-casting point-in-polygon test for a single ring."""
    n = len(polygon_coords)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon_coords[i]
        xj, yj = polygon_coords[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def point_in_multipolygon(px, py, geometry):
    """Check if point is inside any polygon of a GeoJSON geometry."""
    gtype = geometry['type']
    coords = geometry['coordinates']

    if gtype == 'Polygon':
        # Check outer ring (index 0), ignore holes for simplicity
        return point_in_polygon(px, py, coords[0])
    elif gtype == 'MultiPolygon':
        for poly in coords:
            if point_in_polygon(px, py, poly[0]):
                return True
    return False


def check_point_in_flood(lon, lat, flood_geojson):
    """Check if a point falls within any feature of the flood geojson."""
    for feat in flood_geojson['features']:
        if point_in_multipolygon(lon, lat, feat['geometry']):
            return True
    return False


def main():
    # Load infrastructure
    with open(INFRA_PATH, 'r') as f:
        infra = json.load(f)

    # Build sorted list of COGs per side (ascending by level)
    side_cogs = {}
    for side, cog_dir in COG_DIRS.items():
        if not cog_dir.exists():
            print(f"Warning: {cog_dir} not found, skipping side {side}")
            continue
        cogs = []
        for fname in sorted(os.listdir(cog_dir)):
            if fname.startswith('RasterFlood_') and fname.endswith('.tif') and '.tif.' not in fname:
                level = level_from_filename(fname)
                if level is not None:
                    cogs.append((level, str(cog_dir / fname)))
        cogs.sort(key=lambda x: x[0])
        side_cogs[side] = cogs
        print(f"  {side}: {len(cogs)} COGs loaded")

    features = infra['features']
    n = len(features)
    print(f"\nProcessing {n} infrastructure points at 0.1m precision...\n")

    at_risk_count = 0
    for i, feat in enumerate(features):
        coords = feat['geometry']['coordinates']
        lon, lat = coords[0], coords[1]
        x_3857, y_3857 = transformer.transform(lon, lat)
        name = feat['properties'].get('name', '')
        amenity = feat['properties'].get('amenity', '')
        label = name if name else amenity

        min_risk = None
        risk_side = None

        for side, cogs in side_cogs.items():
            for level, cog_path in cogs:
                # Skip levels above current best
                if min_risk is not None and level >= min_risk:
                    break
                with rasterio.open(cog_path) as src:
                    if check_point_in_raster(src, x_3857, y_3857):
                        min_risk = level
                        risk_side = side
                        break  # Found lowest for this side

        if min_risk is not None:
            feat['properties']['flood_risk_m'] = round(min_risk, 1)
            feat['properties']['flood_risk_side'] = risk_side
            at_risk_count += 1
            print(f"  [{i+1:3d}/{n}] {label}: AT RISK at {min_risk:.1f}m ({risk_side})")
        else:
            feat['properties']['flood_risk_m'] = None
            feat['properties']['flood_risk_side'] = None
            print(f"  [{i+1:3d}/{n}] {label}: safe within model range")

    print(f"\n{at_risk_count}/{n} facilities at flood risk")

    with open(INFRA_PATH, 'w') as f:
        json.dump(infra, f)
    print(f"Updated {INFRA_PATH} with flood_risk_m at 0.1m precision")


if __name__ == '__main__':
    main()
