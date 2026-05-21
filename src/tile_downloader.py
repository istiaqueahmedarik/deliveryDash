import math
import os
import requests
import time

def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)

def download_tiles(center_lat, center_lon, radius_km, zoom_levels=[14, 15, 16], output_dir="tiles", progress_callback=None):
    # approximate bounding box
    lat_offset = radius_km / 111.0
    lon_offset = radius_km / (111.0 * math.cos(math.radians(center_lat)))
    
    min_lat = center_lat - lat_offset
    max_lat = center_lat + lat_offset
    min_lon = center_lon - lon_offset
    max_lon = center_lon + lon_offset
    
    total_tiles = 0
    tile_list = []
    for z in zoom_levels:
        x_min, y_min = deg2num(max_lat, min_lon, z)
        x_max, y_max = deg2num(min_lat, max_lon, z)
        
        # Sometimes y_min and y_max can be swapped depending on hemisphere
        if x_min > x_max: x_min, x_max = x_max, x_min
        if y_min > y_max: y_min, y_max = y_max, y_min
        
        for x in range(x_min, x_max + 1):
            for y in range(y_min, y_max + 1):
                tile_list.append((z, x, y))
                total_tiles += 1
                
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    downloaded = 0
    for z, x, y in tile_list:
        # Using CartoDB Voyager as a free, reliable alternative to direct OSM tiles
        url = f"https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png"
        dir_path = os.path.join(output_dir, str(z), str(x))
        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, f"{y}.png")
        
        if not os.path.exists(file_path):
            try:
                response = requests.get(url, headers=headers, timeout=5)
                if response.status_code == 200:
                    with open(file_path, "wb") as f:
                        f.write(response.content)
                time.sleep(0.05)  # slight delay to be polite
            except Exception as e:
                print(f"Failed to download tile {z}/{x}/{y}: {e}")
        
        downloaded += 1
        if progress_callback:
            progress_callback(downloaded, total_tiles)
            
    return {"min_lat": min_lat, "max_lat": max_lat, "min_lon": min_lon, "max_lon": max_lon}
