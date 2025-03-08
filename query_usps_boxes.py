import argparse
import geopandas as gpd
import json
import requests
from shapely.geometry import Point
import subprocess
import time

from general_utility import get_time_estimate_string

CONVERT_TO_SHAPEFILE_NAME = "geojson_to_shapefile.py"

def main():
    parser = argparse.ArgumentParser(description="Query collection box nodes from the USPS website.")
    parser.add_argument("--base-url", default="https://tools.usps.com/locations/getLocations", help="")
    parser.add_argument("--wait-time", type=float, required=True, help="Seconds between queries")
    parser.add_argument("-o", "--output-gis-filepath", required=True, help="Output filepath with GIS file extensio.")
    parser.add_argument("-z", "--zip-code", required=True, help="Request a single zip code.")
    parser.add_argument("-r", "--radius-per-query", type=int, default=5, help="Radius applied to the center of each zip code.")

    args = parser.parse_args()

    collection_box_locations = {}

    body = {
        "requestZipCode": args.zip_code,
        "requestType": "COLLECTIONBOX",
        "maxDistance": args.radius_per_query,
        "requestServices": "",
        "requestHours": ""
    }

    headers = { "Content-Type": "application/json", "User-Agent": "Mozilla/5.0" }

    response = requests.post(args.base_url, json=body, headers=headers)

    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        return
    locations = response.json()['locations']
    for box_info in locations:
        loc_id = box_info["locationID"]
        if not loc_id in collection_box_locations:
            point = Point(box_info["longitude"], box_info["latitude"])
            collection_box_locations[loc_id] = {"locationID": loc_id, "address": box_info["address1"], "geometry": point}
    rows = [collection_box_locations[location_id] for location_id in collection_box_locations]
    gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    gdf.to_file(args.output_gis_filepath)

if __name__ == "__main__":
    main()
