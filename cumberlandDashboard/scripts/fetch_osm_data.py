"""
Fetch real road network and critical infrastructure from OpenStreetMap
for Cumberland County, Nova Scotia using Overpass API
"""
import json
import urllib.request
import urllib.parse
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'assets', 'geojson')
os.makedirs(OUTPUT_DIR, exist_ok=True)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Cumberland County bounding box (south,west,north,east)
BBOX = "45.30,-65.10,46.00,-63.40"

def query_overpass(query):
    """Send query to Overpass API and return JSON response"""
    data = urllib.parse.urlencode({'data': query}).encode('utf-8')
    req = urllib.request.Request(OVERPASS_URL, data=data)
    req.add_header('User-Agent', 'CumberlandFloodDashboard/1.0')
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode('utf-8'))

def overpass_to_geojson_lines(data, name):
    """Convert Overpass way results to GeoJSON LineString features"""
    features = []
    for element in data.get('elements', []):
        if element['type'] == 'way' and 'geometry' in element:
            coords = [[n['lon'], n['lat']] for n in element['geometry']]
            tags = element.get('tags', {})
            feature = {
                "type": "Feature",
                "properties": {
                    "name": tags.get('name', 'Unnamed'),
                    "ref": tags.get('ref', ''),
                    "highway": tags.get('highway', ''),
                    "surface": tags.get('surface', ''),
                    "lanes": tags.get('lanes', ''),
                    "osm_id": element['id']
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": coords
                }
            }
            features.append(feature)
    return {"type": "FeatureCollection", "name": name, "features": features}

def overpass_to_geojson_points(data, name):
    """Convert Overpass node results to GeoJSON Point features"""
    features = []
    for element in data.get('elements', []):
        if element['type'] == 'node':
            tags = element.get('tags', {})
            feature = {
                "type": "Feature",
                "properties": {k: v for k, v in tags.items()},
                "geometry": {
                    "type": "Point",
                    "coordinates": [element['lon'], element['lat']]
                }
            }
            feature['properties']['osm_id'] = element['id']
            features.append(feature)
        elif element['type'] == 'way' and 'center' in element:
            tags = element.get('tags', {})
            feature = {
                "type": "Feature",
                "properties": {k: v for k, v in tags.items()},
                "geometry": {
                    "type": "Point",
                    "coordinates": [element['center']['lon'], element['center']['lat']]
                }
            }
            feature['properties']['osm_id'] = element['id']
            features.append(feature)
    return {"type": "FeatureCollection", "name": name, "features": features}

# ---- 1. MAJOR ROADS (trunk, primary, secondary highways) ----
print("Fetching major roads...")
road_query = f"""
[out:json][timeout:90];
(
  way["highway"="trunk"]({BBOX});
  way["highway"="primary"]({BBOX});
  way["highway"="secondary"]({BBOX});
  way["highway"="motorway"]({BBOX});
  way["highway"="motorway_link"]({BBOX});
  way["highway"="trunk_link"]({BBOX});
);
out geom;
"""

try:
    road_data = query_overpass(road_query)
    road_geojson = overpass_to_geojson_lines(road_data, "Cumberland_Roads")
    with open(os.path.join(OUTPUT_DIR, 'roads_cumberland.geojson'), 'w') as f:
        json.dump(road_geojson, f)
    print(f"  OK: roads_cumberland.geojson ({len(road_geojson['features'])} road segments)")
except Exception as e:
    print(f"  ERROR: {e}")

# ---- 2. CRITICAL INFRASTRUCTURE ----
print("Fetching critical infrastructure...")
infra_query = f"""
[out:json][timeout:90];
(
  node["amenity"="fire_station"]({BBOX});
  way["amenity"="fire_station"]({BBOX});
  node["amenity"="hospital"]({BBOX});
  way["amenity"="hospital"]({BBOX});
  node["amenity"="police"]({BBOX});
  way["amenity"="police"]({BBOX});
  node["amenity"="townhall"]({BBOX});
  way["amenity"="townhall"]({BBOX});
  node["amenity"="community_centre"]({BBOX});
  way["amenity"="community_centre"]({BBOX});
  node["amenity"="clinic"]({BBOX});
  way["amenity"="clinic"]({BBOX});
  node["healthcare"="hospital"]({BBOX});
  way["healthcare"="hospital"]({BBOX});
  node["emergency"="ambulance_station"]({BBOX});
  way["emergency"="ambulance_station"]({BBOX});
);
out center;
"""

try:
    infra_data = query_overpass(infra_query)
    infra_geojson = overpass_to_geojson_points(infra_data, "Cumberland_Infrastructure")
    with open(os.path.join(OUTPUT_DIR, 'infrastructure_cumberland.geojson'), 'w') as f:
        json.dump(infra_geojson, f)
    print(f"  OK: infrastructure_cumberland.geojson ({len(infra_geojson['features'])} facilities)")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n=== OSM data fetch complete ===")
