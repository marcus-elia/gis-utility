import argparse
import geopandas as gpd
import requests
from shapely.geometry import Point
import time

from general_utility import get_time_estimate_string, parse_latlon_string

def main():
    parser = argparse.ArgumentParser(description="Query collection box nodes from the USPS website.")
    parser.add_argument("--base-url", default="https://tools.usps.com/locations/getLocations", help="")
    parser.add_argument("--wait-time", type=float, required=True, help="Seconds between queries")
    parser.add_argument("-o", "--output-gis-filepath", required=True, help="Output filepath with GIS file extensio.")
    parser.add_argument("-r", "--radius-per-query", type=int, default=5, help="Radius applied to the center of each zip code.")
    parser.add_argument("--single-zip-code", required=False, help="Request a single zip code.")
    parser.add_argument("--sw", required=False, help="SW lat/lon corner of region.")
    parser.add_argument("--ne", required=False, help="NE lat/lon corner of region.")
    parser.add_argument("--zip-codes-filepath", required=False, help="Path to geojson file containing centroids of zip codes.")

    args = parser.parse_args()

    if args.single_zip_code:
        zip_codes = [args.single_zip_code]
    else:
        print("Loading relevant zip codes")
        start_time = time.time()
        if not (args.sw and args.ne and args.zip_codes_filepath):
            raise ValueError("Must specify sw corner, ne corner, and zip codes filepath.")
        zips_gdf = gpd.read_file(args.zip_codes_filepath)
        print("Loaded %d zip codes in %.2f seconds." % (len(zips_gdf), time.time() - start_time))
        start_time = time.time()
        min_lat, min_lon = parse_latlon_string(args.sw)
        max_lat, max_lon = parse_latlon_string(args.ne)
        zips_gdf = zips_gdf.cx[min_lon:max_lon, min_lat:max_lat]
        zip_codes = zips_gdf['ZIP_CODE'].to_list()
        print("Restricted to %d zip codes in %.2f seconds." % (len(zip_codes), time.time() - start_time))

    # Put locations into a dictionary as we get them to prevent duplicates.
    collection_box_locations = {}

    start_time = time.time()
    num_complete = 0
    num_total = len(zip_codes)
    print("Querying the USPS website.")
    prev_num_boxes = 0
    for zip_code in zip_codes:
        body = {
            "requestZipCode": zip_code,
            "requestType": "COLLECTIONBOX",
            "maxDistance": args.radius_per_query,
            "requestServices": "",
            "requestHours": ""
        }

        headers = { "Content-Type": "application/json", "User-Agent": "Mozilla/5.0" }

        response = requests.post(args.base_url, json=body, headers=headers)
        if response.status_code != 200:
            print(f"Error: {response.status_code} from querying zip code %s." % (zip_code))
            return
        locations = response.json()['locations']
        for box_info in locations:
            loc_id = box_info["locationID"]
            if loc_id == None or box_info["longitude"] == None or box_info["latitude"] == None:
                continue
            if not loc_id in collection_box_locations:
                point = Point(box_info["longitude"], box_info["latitude"])
                collection_box_locations[loc_id] = {"locationID": loc_id, "address": box_info["address1"], "geometry": point}
        print("Loaded %d boxes from %s. %d total. Sleeping for %.0f seconds." % (len(collection_box_locations) - prev_num_boxes, zip_code, len(collection_box_locations), args.wait_time))
        prev_num_boxes = len(collection_box_locations)
        time.sleep(args.wait_time)
        num_complete += 1
        time_elapsed = time.time() - start_time
        print(get_time_estimate_string(time_elapsed, num_complete, num_total))

    # Once all data is in a dictionary (and thus unique), pass a list of rows to geopandas.
    rows = [collection_box_locations[location_id] for location_id in collection_box_locations]
    gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    gdf.to_file(args.output_gis_filepath)

if __name__ == "__main__":
    main()
