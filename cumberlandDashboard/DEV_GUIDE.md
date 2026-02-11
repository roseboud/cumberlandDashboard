# 🌊 Cumberland Flood Dashboard — Developer Guide

> **INFT3000 Capstone — Step-by-Step Setup for Students**

This guide walks you through downloading, opening, and running the Cumberland Flood Dashboard on your local machine. No install wizards, no frameworks — just a browser and a text editor.

---

## 📋 Prerequisites

Before you begin, make sure you have:

| Tool | Why You Need It | How to Check |
|------|----------------|--------------|
| **Git** | To download the repository | Open a terminal → type `git --version` |
| **VS Code** | To view and edit the code | [Download here](https://code.visualstudio.com/) |
| **Python 3** | To run the local web server | Open a terminal → type `python --version` |
| **A modern browser** | Chrome, Firefox, or Edge | You already have one! |

> 💡 **Don't have Python?** You can also use the VS Code **"Live Server"** extension (see Step 4b below).

---

## 🚀 Step 1 — Clone the Repository

Open your terminal (Command Prompt, PowerShell, or Terminal on Mac) and run:

```bash
git clone https://github.com/NSCC-ITC-Fall2024-PROC1700-702-CIm/techcheck4-roseboud.git
```

This creates a folder with all the project files. Navigate into it:

```bash
cd techcheck4-roseboud
```

> 📁 You should see these files:
> ```
> index.html              ← The main dashboard (open this!)
> styles/map.css          ← Dark-theme styling
> assets/flood_100yr.json ← Flood zone polygons (GeoJSON)
> assets/road_network.json← Evacuation routes (GeoJSON)
> implementation.md       ← Technical blueprint
> DEV_GUIDE.md            ← This file!
> ```

---

## 🖥️ Step 2 — Open in VS Code

You can open the project in VS Code two ways:

### Option A: From the terminal
```bash
code .
```
This opens VS Code in the current folder.

### Option B: From VS Code
1. Open VS Code
2. Click **File** → **Open Folder...**
3. Navigate to the `techcheck4-roseboud` folder you just cloned
4. Click **Select Folder**

You should now see all the project files in the VS Code sidebar (Explorer panel on the left).

---

## 🌐 Step 3 — Understand Why You Need a Local Server

⚠️ **You cannot just double-click `index.html` to run this dashboard.**

Here's why: The dashboard fetches **live tide data** from the Canadian Hydrographic Service (CHS) API. Browsers block these network requests when you open an HTML file directly (`file:///...`) due to [CORS security policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS).

**Solution:** Run a simple local web server. This makes your browser think it's loading from a real website (`http://localhost:...`), which the API allows.

---

## ▶️ Step 4 — Launch the Dashboard

### Option A: Python HTTP Server (Recommended)

1. In VS Code, open the **integrated terminal**:
   - Press `` Ctrl + ` `` (backtick key, next to the 1 key)
   - Or click **Terminal** → **New Terminal** from the menu bar

2. Make sure you're in the project folder (you should see the path in the terminal prompt). If not:
   ```bash
   cd path/to/techcheck4-roseboud
   ```

3. Start the server:
   ```bash
   python -m http.server 8080
   ```
   
   You should see:
   ```
   Serving HTTP on :: port 8080 (http://[::]:8080/) ...
   ```

4. Open your browser and go to:
   ```
   http://localhost:8080
   ```

5. 🎉 **The dashboard should load!** You'll see the map, flood zones, and live tide data within a few seconds.

> **To stop the server:** Go back to the terminal and press `Ctrl + C`.

### Option B: VS Code Live Server Extension

If you don't have Python or prefer a one-click solution:

1. In VS Code, go to the **Extensions** panel (click the square icon on the left sidebar, or press `Ctrl+Shift+X`)

2. Search for **"Live Server"** by Ritwick Dey

3. Click **Install**

4. Once installed, right-click on `index.html` in the Explorer sidebar

5. Select **"Open with Live Server"**

6. Your default browser will open automatically with the dashboard running!

> **Bonus:** Live Server auto-refreshes the page whenever you save a file — great for development!

---

## ✅ Step 5 — Verify Everything Works

Once the dashboard loads, check these features:

| Feature | What to Look For |
|---------|-----------------|
| **Map** | Leaflet map centered on the Chignecto Isthmus (Amherst/Sackville area) |
| **Tide Data** | Three stations showing live numbers (e.g., `3.37` metres) with **NORMAL** status |
| **Flood Zones** | Blue polygons on the map — click one to see a popup with zone details |
| **Evacuation Routes** | Orange/yellow lines across the map |
| **Infrastructure** | Colored dots near Amherst — click to see Fire, Police, Hospital details |
| **Layer Toggles** | Sidebar checkboxes to show/hide each layer |
| **File Upload** | Drag a `.geojson` or `.csv` file onto the upload area to add your own layer |
| **Toast Notification** | A "Tide data refreshed" message appears at the bottom on load |
| **Base Map Switch** | Click the layers icon (top-left of map) to switch between OSM, Topo, and Dark mode |

---

## 🔍 Step 6 — Explore the Code

Here's where to find each feature in the code:

| Feature | Location in `index.html` |
|---------|-------------------------|
| Map initialization | Search for `L.map('map'` |
| Tide station config | Search for `TIDE_STATIONS` |
| API fetch logic | Search for `fetchTideData` |
| Flood zone loading | Search for `flood_100yr.json` |
| Infrastructure data | Search for `infrastructureData` |
| File upload handler | Search for `processUploadedFile` |
| Layer toggles | Search for `layer-flood` |

The CSS is in `styles/map.css` — the dark theme uses a palette of `#16213e` (navy), `#0f3460` (deep blue), `#e94560` (accent red), and `#00d4ff` (cyan).

---

## 🧪 Step 7 — Test with Your Own Data

Want to try uploading your own data? Create a simple CSV file:

```csv
Name,Lat,Lng,Type
Test Point 1,45.83,-64.25,Sensor
Test Point 2,45.80,-64.20,Gauge
Test Point 3,45.85,-64.30,Station
```

1. Save it as `test_points.csv`
2. In the dashboard sidebar, scroll to **"Add Layer"**
3. Click the upload area or drag your file in
4. The points should appear as purple markers on the map!

You can also upload `.geojson` files exported from QGIS or other GIS tools.

---

## 🛑 Troubleshooting

| Problem | Solution |
|---------|----------|
| **Tide stations show "ERR" or "OFFLINE"** | Your network may be blocking the CHS API. Try a different network (school vs. home). The API URL is `api-iwls.dfo-mpo.gc.ca`. |
| **Tide stations show "N/A"** | The API may be temporarily down. Wait a few minutes and refresh. |
| **Map tiles don't load (grey squares)** | Check your internet connection — the map tiles come from OpenStreetMap's CDN. |
| **"python" is not recognized** | Try `python3 -m http.server 8080` instead. Or install Python from [python.org](https://www.python.org/downloads/). |
| **Port 8080 already in use** | Use a different port: `python -m http.server 9090` then go to `http://localhost:9090`. |
| **CORS errors in console** | Make sure you're using `http://localhost:8080`, NOT opening the file directly. |

---

## 📚 Key Data Sources

| Data | Source | API/URL |
|------|--------|---------|
| Tide Levels | Canadian Hydrographic Service (CHS/DFO-MPO) | `api-iwls.dfo-mpo.gc.ca/api/v1/` |
| Base Map Tiles | OpenStreetMap | `tile.openstreetmap.org` |
| Flood Zones | Project LiDAR Data (prototype polygons) | `assets/flood_100yr.json` |
| Evacuation Routes | Project Data | `assets/road_network.json` |

### Live Tide Station IDs (for API queries)

| Station | CHS Code | API ObjectId |
|---------|----------|-------------|
| Saint John, NB | 00065 | `5cebf1df3d0f4a073c4bbc24` |
| Charlottetown, PE | 00612 | `5cebf1e33d0f4a073c4bc21f` |
| Caribou, NS | 00490 | `5cebf1e33d0f4a073c4bc20d` |

> **Note:** The CHS API uses MongoDB ObjectIds, not the traditional numeric station codes. The full station list can be queried at:
> ```
> https://api-iwls.dfo-mpo.gc.ca/api/v1/stations?chs-region-code=ATL
> ```

---

## 🚢 Next Steps (for the team)

1. **Replace prototype flood zones** with real vectorized LiDAR data from QGIS (Polygonize → Simplify → Export as GeoJSON)
2. **Add more local stations** — Joggins (`5cebf1df3d0f4a073c4bbc44`), Parrsboro (`5cebf1df3d0f4a073c4bbc54`), and Amherst Basin (`5dd3064de0fdc4b9b4be6665`) are available in the API
3. **Deploy to GitHub Pages** for public access (Settings → Pages → Source: main branch)
4. **Migrate to Power BI** for the final deliverable using Azure Maps visual + Python data connector

---

*Last updated: February 11, 2026 — INFT3000 Capstone Team*
