import argparse
import requests
import json
import subprocess
import time

from general_utility import get_time_estimate_string

CONVERT_TO_SHAPEFILE_NAME = "geojson_to_shapefile.py"

# Configurable variables
FIELDS = "*"  # Fields to retrieve, '*' for all fields
FORMAT = "geojson"  # Response format
MAX_NUM_REQUESTS = 10000 # Don't do more than this without confirming the user wants it

# Helper function to build query
def build_query(minX, minY, maxX, maxY):
    return {
        "where": "1=1",  # Get all features in this geometry
        "geometry": f"{minX},{minY},{maxX},{maxY}",
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": FIELDS,
        "f": FORMAT
    }

# Save GeoJSON data to a file
def save_geojson(data, file_name):
    with open(file_name, "w") as f:
        json.dump(data, f)

# Main function to query the server
def query_all_data(base_url, layer_number, output_geojson_filepath, wait_time, grid_size, sudo=False, minX=None, minY=None, maxX=None, maxY=None):
    features = []

    # Get the max number of results that can be returned, so we can check if we ever hit it.
    # Also get the extents so the user doesn't have to specify them
    info_url = base_url + "?f=json"
    info_response = requests.get(info_url)
    info_data = info_response.json()
    max_record_count = info_data.get("maxRecordCount", "Not specified")
    num_features = info_data.get('count')
    if minX == None:
        full_extents = info_data.get("fullExtent", {})
        if len(full_extents) == 0:
            raise ValueError("The server does not have 'fullExtent'.")
        minX = full_extents['xmin']
        minY = full_extents['ymin']
        maxX = full_extents['xmax']
        maxY = full_extents['ymax']

    url = base_url + '/' + str(layer_number) + '/query'

    num_total = ((maxX - minX) // grid_size + 1) * ((maxY - minY) // grid_size + 1)
    if num_total > MAX_NUM_REQUESTS and not sudo:
        raise ValueError("This would involve more than %d requests (%d). If this is what you want, pass --sudo. Otherwise, consider manually passing bounds." % (MAX_NUM_REQUESTS, num_total))
    num_complete = 0
    start_time = time.time()
    num_limited_by_max_record_count = 0
    num_without_features = 0
    # Iterate over the bounding box in a grid pattern
    x = minX
    while x < maxX:
        y = minY
        while y < maxY:
            # Define the small grid's corners
            x_max = min(x + grid_size, maxX)
            y_max = min(y + grid_size, maxY)
            
            # Build and execute the query
            query = build_query(x, y, x_max, y_max)
            try:
                response = requests.get(url, params=query)
            except:
                print("Failure at %f, %f, %f, %f. Retrying." % (x, y, x_max, y_max))
                try:
                    response = requests.get(url, params=query)
                except:
                    reponse = None
            if response == None:
                print("Incomplete read for %f, %f, %f, %f." % (x, y, x_max, y_max))
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "features" in data:
                        if len(data["features"]) == max_record_count:
                            print("Reached maximum of %d features returned by a single query at %f, %f, %f, %f." % (max_record_count, x, y, x_max, y_max))
                            num_limited_by_max_record_count += 1
                        features.extend(data["features"])
                        print(f"Retrieved {len(data['features'])} features from ({x}, {y}) to ({x_max}, {y_max})")
                    else:
                        num_without_features += 1
                        print("No 'features' in response: " + str(data))
                except requests.exceptions.JSONDecodeError:
                    print("Failed to decode JSON at %f, %f, %f, %f." % (x, y, x_max, y_max))
            else:
                if response.headers.get("Content-Type") == "application/json":
                    print(f"Error: {response.status_code} for query at ({x}, {y}): %s" % (response.json()))
                else:
                    print(f"Error: {response.status_code} for query at ({x}, {y}): %s" % (response.text))
            
            # Move to next grid and pause
            y += grid_size
            num_complete += 1
            time_elapsed = time.time() - start_time
            print(get_time_estimate_string(time_elapsed, num_complete, num_total))
            time.sleep(wait_time)
        x += grid_size

    print("%d queries were restricted to %d features." % (num_limited_by_max_record_count, max_record_count))
    print("%d queries were did not have 'features'." % (num_without_features))
    
    # Save the results as GeoJSON
    geojson_output = {
        "type": "FeatureCollection",
        "features": features
    }
    save_geojson(geojson_output, output_geojson_filepath)
    print(f"Saved {len(features)} features to {output_geojson_filepath}")
    if num_features != None:
        print("You got %d/%d features from the server." % (len(features), num_features))

def main():
    parser = argparse.ArgumentParser(description="Query data from a MapServer.")
    parser.add_argument("-n", "--layer-number", required=True, type=int, help="The number of the layer on the server.")
    parser.add_argument("-X", "--min-x", required=False, type=float, help="West border of query region")
    parser.add_argument("-Y", "--min-y", required=False, type=float, help="South border of query region")
    parser.add_argument("-U", "--max-x", required=False, type=float, help="East border of query region")
    parser.add_argument("-V", "--max-y", required=False, type=float, help="North border of query region")
    parser.add_argument("--base-url", required=True, help="MapServer url (ending with /MapServer)")
    parser.add_argument("--wait-time", type=float, required=True, help="Seconds between queries")
    parser.add_argument("--grid-size", required=False, type=float, help="Grid size (defaults to degrees)")
    parser.add_argument("-o", "--output-geojson-filepath", required=True, help="Output geojson filepath")
    parser.add_argument("--dont-convert-to-shapefile", action='store_true', help="Don't convert geojson to shp.zip with the same name.")
    parser.add_argument("--sudo", action='store_true', help="You will be prompted to pass this to run a very large set of requests.")

    args = parser.parse_args()

    if not (args.min_x or args.min_y or args.max_x or args.max_y):
        # If none are specified, detect the extents
        query_all_data(args.base_url, args.layer_number, args.output_geojson_filepath, args.wait_time, args.grid_size if args.grid_size else 0.001, sudo=args.sudo)
    else:
        if not (args.min_x and args.min_y and args.max_x and args.max_y):
            raise ValueError("Must specify all of min_x, min_y, max_x, max_y.")
        query_all_data(args.base_url, args.layer_number, args.output_geojson_filepath, args.wait_time, args.grid_size if args.grid_size else 0.001, args.sudo, args.min_x, args.min_y, args.max_x, args.max_y)

    if not args.dont_convert_to_shapefile:
        p = subprocess.Popen(['python3', CONVERT_TO_SHAPEFILE_NAME, "-i", args.output_geojson_filepath], shell=True)
        p.communicate()

if __name__ == "__main__":
    main()
