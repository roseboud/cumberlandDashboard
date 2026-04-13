# Cumberland Flood Dashboard — Changelog

---

## v1.3 — New Data Integration, AGRG Predictions & Basemap Switcher

**Date:** April 3, 2026

### Changes

**1. Base Map Switcher (Reimplemented)**
- Floating toggle control on the map with 4 options: Street, Topographic, Satellite, Dark
- SVG icons for each basemap type, mobile-responsive (icon-only on small screens)
- Fixed base layer ordering bug (Satellite and Dark were swapped in v1.2)

**2. AGRG 10-Day Tide & Storm Surge Predictions**
- Integration with AGRG ArcGIS MapServer (`agrgims.cogs.nscc.ca/arcgis/rest/services/mcfm_pro/tide_stns/MapServer`)
- Dynamically queries Layer 0 for tide station locations and attributes
- Queries per-station prediction tables for 10-day tide, surge, and total water level forecasts
- CGVD28 → CGVD2013 datum conversion applied using per-station `CGVD28_13` offset field (~-0.60m)
- New sidebar section "AGRG 10-Day Predictions" with expandable multi-line charts (tide/surge/total)
- Orange map markers distinguish AGRG stations from blue CHS stations
- Separate layer toggle for AGRG markers

**3. Storm Surge Return Period Scenarios**
- New sidebar section "Storm Surge Scenarios" with dropdown selectors for:
  - Return Period: 20-year / 100-year
  - Time Horizon: 2020 / 2050 / 2100 / 2150
- XYZ tile layer system for surge scenarios (red-colored, depth-graduated opacity)
- Tile generation script `generate_surge_tiles.py` processes FloodDepth rasters from newData/
- Source data: Northumberland Strait FloodDepth (Mercator Atlantic Canada → EPSG:3857)
- Surge layer toggle in Map Layers sidebar section

**4. Increased Flood Tile Resolution**
- OpenLayers `maxZoom` increased from 15 to 17 on flood inundation layers
- z15 tiles seamlessly overzoom to z16-17 via OpenLayers internal scaling
- No additional tile generation needed — existing z10-z15 tiles work at higher zooms

**5. Updated Dashboard KPIs**
- Added: AGRG Stations count, Surge Scenario active indicator
- 6 KPI cards now: CHS Stations, AGRG Stations, Sim. Water Level, Infrastructure, Data Latency, Surge Scenario

**6. Legend & Reference Data Updates**
- Legend adds: flood depth gradient bar, storm surge scenario area, AGRG prediction station marker
- Reference Data modal updated with AGRG service details, surge scenario parameters, and CGVD28/CGVD2013 datum info

**7. .gitignore Hardened**
- Added: new COG TIF, Python bytecode, OS files, IDE settings
- Ensures no large binary files leak into regular Git

**Files changed:** `parts/part1-5.html`, `styles/map.css`, `index.html` (rebuilt), `.gitignore`, `CHANGELOG.md`
**Files created:** `generate_surge_tiles.py`

---

## v1.2 — Stakeholder Feedback Implementation

**Date:** March 5, 2026

### Changes

**1. Pointe-du-Chêne Tide Gauge Added**
- New station: Pointe-du-Chêne, NB (CHS Station 01804) — live API feed, map marker, sidebar widget.
- Tide station count increased from 3 to 4.

**2. Datum Conversion: CD → CGVD2013**
- All water levels now displayed in CGVD2013 (Canadian Geodetic Vertical Datum of 2013) instead of Chart Datum.
- Per-station offsets applied: Saint John −4.755m, Pointe-du-Chêne −1.478m, Charlottetown −2.012m, Caribou −1.757m.
- Thresholds (NORMAL/ELEVATED/CRITICAL) recalculated for CGVD2013 equivalents.

**3. Embedded 24h Water Level Charts**
- Each tide station widget now includes an expand/collapse sparkline chart showing the last 24 hours of observed water levels (CGVD2013).
- Charts rendered via native HTML5 Canvas — zero external dependencies.
- CGVD2013 zero-line reference rendered when data crosses zero.

**4. Direct Links to tides.gc.ca**
- Each station widget includes a clickable external link to the corresponding tides.gc.ca station page for full historical graphs and predictions.

**5. AGRG Reference Data Modal**
- New "Reference Data" sidebar section with a button that opens a modal overlay.
- Modal contains AGRG project metadata: DEM specs, coordinate system, flood model parameters, ocean reference points, and the full CD-to-CGVD2013 offset table.
- Accessible via click, closeable via X button, backdrop click, or Escape key.

**6. Sidebar Footer Updated**
- Added vertical datum note (CGVD2013) to sidebar footer.

**Files changed:** `index.html`, `styles/map.css`, `CHANGELOG.md`

---

## v1.0 — Initial Production Release

**Date:** February 15, 2026
**Author:** Automated upgrade (AI-assisted)
**Branch:** Main

---

## Summary

The dashboard was upgraded from a demo/prototype into a production-ready, professional municipal flood risk application. Every layer of the application was touched: the UI, the data, and the map logic.

---

## What Changed

### 1. UI/UX — Complete Redesign

**Before:** Dark-only theme with emojis everywhere (🌊📡🚒📎), demo-quality styling.
**After:** Clean, professional municipality-grade interface.

| What | Before | After |
|------|--------|-------|
| Emojis | 20+ emojis in headers, labels, popups | Zero emojis — replaced with inline SVG icons |
| Theme | Dark-only (hardcoded navy colors) | Light mode (default) + Dark mode toggle |
| Font | Segoe UI | Inter (Google Fonts) with system fallbacks |
| Colors | Neon cyan (#00d4ff), hot pink (#e94560) | Muted government blues, clean grays |
| Header | "🌊 Cumberland Flood Dashboard" | "Cumberland County — Flood Risk Dashboard" with SVG logo |
| CSS | Hardcoded hex colors throughout | CSS Custom Properties (`--bg-primary`, `--text-primary`, etc.) |
| Theme persistence | N/A | Saves to `localStorage`, persists across sessions |

**Files changed:**
- `styles/map.css` — Completely rewritten (400+ lines)
- `index.html` — Completely rewritten (800+ lines)

### 2. Flood Data — Real LiDAR-Derived Inundation Models

**Before:** 5 hand-drawn polygons in `flood_100yr.json` with approximate coordinates.
**After:** 24 GeoJSON files converted from actual LiDAR-derived flood shapefiles.

| What was done | Details |
|---------------|---------|
| Source data | `assets/FundySide/Shapefiles/` and `assets/NorthSide/Shapefiles/` |
| Conversion | Python script (`convert_shapefiles.py`) using `geopandas` + `pyogrio` |
| Reprojection | NAD83(CSRS)v6 UTM Zone 20N → WGS84 (EPSG:4326) for Leaflet compatibility |
| Simplification | Geometry simplified (tolerance 0.00005°, ~5m) for web performance |
| Output | `assets/geojson/flood_fundy_X_0m.geojson` and `flood_north_X_0m.geojson` (X = 0–11) |
| Levels | 1.0m increments: 0m, 1m, 2m, 3m, 4m, 5m, 6m, 7m, 8m, 9m, 10m, 11m |

**New feature — Flood Slider:**
- Range slider (0–11m) in the sidebar lets you visualize progressive flooding
- Toggle buttons: "Both Sides", "Bay of Fundy", "Northumberland" to isolate regions
- Layer caching: once a level is loaded, revisiting it is instant (no re-fetch)
- Loading overlay shows while GeoJSON data is being fetched
- Color gradient: lighter blue at low levels → darker blue at high levels

### 3. Road Network — Real OpenStreetMap Data

**Before:** 4 hand-drawn LineStrings in `road_network.json` (approximate routes for TCH-104, Hwy 2, Route 302).
**After:** 965 real road segments fetched from OpenStreetMap Overpass API.

| What was done | Details |
|---------------|---------|
| Source | OpenStreetMap via Overpass API |
| Query | All motorway, trunk, primary, and secondary highways in the Cumberland County bounding box |
| Output | `assets/geojson/roads_cumberland.geojson` |
| Script | `fetch_osm_data.py` |
| Styling | Color-coded by road classification (motorway=purple, trunk=red, primary=orange, secondary=yellow) |
| Popups | Click any road segment to see name, reference number, classification, surface type |

### 4. Critical Infrastructure — Real OpenStreetMap Data

**Before:** 6 hardcoded markers with approximate lat/lng (fire stations, hospital, RCMP, EMO, Joggins, Parrsboro).
**After:** 101 real infrastructure facilities from OpenStreetMap.

| What was done | Details |
|---------------|---------|
| Source | OpenStreetMap via Overpass API |
| Facility types | Fire stations, hospitals, clinics, police, town halls, community centres, ambulance stations |
| Output | `assets/geojson/infrastructure_cumberland.geojson` |
| Styling | Color-coded circle markers (red=fire/emergency, green=healthcare, blue=police/government, purple=town hall, orange=community centre) |
| Popups | Click any marker to see name, type, address, data source |

### 5. Ocean Reference Points — Converted from Shapefiles

**Before:** Not used.
**After:** `oceanpoint_fundy.geojson` and `oceanpoint_north.geojson` converted from the FundySide/NorthSide shapefiles.

### 6. Base Map Options

**Before:** 3 options (OpenStreetMap, Topographic, Dark Mode CARTO).
**After:** 4 options (Street Map, Topographic, **Satellite** (Esri World Imagery), Dark).

### 7. Existing Features Preserved

These features from the original demo still work exactly as before:
- Live tide data from CHS/DFO-MPO API (Saint John, Charlottetown, Caribou)
- Auto-refresh every 5 minutes
- Status badges (NORMAL / ELEVATED / CRITICAL)
- File upload (drag-and-drop or click) for .geojson, .json, .csv
- User layer management (add/remove custom layers)
- Cursor position display (lat, lng, zoom)
- Toast notifications
- Responsive layout (mobile-friendly)

---

## New Files Created

| File | Purpose |
|------|---------|
| `assets/geojson/flood_fundy_0_0m.geojson` through `flood_fundy_11_0m.geojson` | Bay of Fundy flood inundation (12 levels) |
| `assets/geojson/flood_north_0_0m.geojson` through `flood_north_11_0m.geojson` | Northumberland flood inundation (12 levels) |
| `assets/geojson/roads_cumberland.geojson` | Real road network from OSM |
| `assets/geojson/infrastructure_cumberland.geojson` | Real infrastructure from OSM |
| `assets/geojson/oceanpoint_fundy.geojson` | Bay of Fundy ocean reference point |
| `assets/geojson/oceanpoint_north.geojson` | Northumberland ocean reference point |
| `convert_shapefiles.py` | Python script to convert .shp → .geojson |
| `fetch_osm_data.py` | Python script to fetch road/infrastructure from OSM |
| `CHANGELOG.md` | This file |
| `HOSTING_GUIDE.md` | Guide for deploying to the web |

---

## How to Run Locally

Same as before — nothing changed in the dev workflow:

```bash
cd cumberlandDashboard
python -m http.server 8080
# Open http://localhost:8080
```

Or use VS Code Live Server extension (right-click `index.html` → Open with Live Server).

---

## Dependencies Added

For the data conversion scripts only (not needed to run the dashboard):

```bash
pip install geopandas pyogrio pyproj shapely
```

The dashboard itself is still **zero-dependency** — just HTML, CSS, JavaScript, and Leaflet (loaded from CDN).
