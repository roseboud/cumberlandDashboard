"""
Enrich unnamed infrastructure features with location-based names
using Nominatim reverse geocoding to add nearby place context.
"""
import json
import urllib.request
import time
import os

INFRA_PATH = os.path.join('cumberlandDashboard', 'assets', 'geojson', 'infrastructure_cumberland.geojson')

TYPE_LABELS = {
    'fire_station': 'Fire Station',
    'community_centre': 'Community Centre',
    'townhall': 'Town Hall',
    'police': 'Police Station',
    'hospital': 'Hospital',
    'clinic': 'Health Clinic',
    'ambulance_station': 'Ambulance Station',
}


def reverse_geocode(lat, lon):
    """Use Nominatim to get nearby place name."""
    url = (f"https://nominatim.openstreetmap.org/reverse?"
           f"lat={lat}&lon={lon}&format=json&zoom=14&addressdetails=1")
    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'CumberlandFloodDashboard/1.1')
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            addr = data.get('address', {})
            # Try village -> town -> city -> county in that order
            place = (addr.get('village') or addr.get('town') or
                     addr.get('city') or addr.get('hamlet') or
                     addr.get('suburb') or addr.get('municipality') or
                     addr.get('county', ''))
            return place
    except Exception as e:
        print(f"  Geocode error: {e}")
        return ''


def main():
    with open(INFRA_PATH, 'r') as f:
        infra = json.load(f)

    unnamed_count = 0
    enriched_count = 0

    for i, feat in enumerate(infra['features']):
        props = feat['properties']
        name = props.get('name', '')
        amenity = props.get('amenity') or props.get('healthcare') or props.get('emergency') or ''

        if name:
            # Already has a name, skip
            continue

        unnamed_count += 1
        coords = feat['geometry']['coordinates']
        lon, lat = coords[0], coords[1]

        # Rate limit: Nominatim requires max 1 req/sec
        time.sleep(1.1)

        place = reverse_geocode(lat, lon)
        type_label = TYPE_LABELS.get(amenity, amenity.replace('_', ' ').title())

        if place:
            new_name = f"{type_label} ({place})"
            props['name'] = new_name
            enriched_count += 1
            print(f"  [{i+1:3d}] {amenity} -> {new_name}")
        else:
            print(f"  [{i+1:3d}] {amenity} at ({lat:.4f}, {lon:.4f}) — no place found")

    print(f"\n{enriched_count}/{unnamed_count} unnamed features enriched")

    with open(INFRA_PATH, 'w') as f:
        json.dump(infra, f)
    print(f"Updated {INFRA_PATH}")


if __name__ == '__main__':
    main()
