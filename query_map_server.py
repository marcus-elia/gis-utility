import argparse
import requests
import json
import subprocess
import time

from general_utility import get_time_estimate_string

CONVERT_TO_SHAPEFILE_NAME = "geojson_to_shapefile.py"
THIS_SCRIPT_NAME = "query_map_server.py"

# Configurable variables
FIELDS = "*"  # Fields to retrieve, '*' for all fields
FORMAT = "geojson"  # Response format
MAX_NUM_REQUESTS = 10000 # Don't do more than this without confirming the user wants it

# Helper function to build query
def build_query(minX, minY, maxX, maxY, where):
    return {
        "where": where,
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

def number_to_command_line_arg(num):
    """
    Negative numbers need spaces in front.
    """
    if num < 0:
        return " " + str(num)
    else:
        return str(num)

def get_server_info(base_url):
    info_url = base_url + "?f=json"
    info_response = requests.get(info_url)
    info_data = info_response.json()
    max_record_count = info_data.get("maxRecordCount", "Not specified")
    num_features = info_data.get('count')
    full_extents = info_data.get("fullExtent", {})
    if len(full_extents) == 0:
        raise ValueError("The server does not have 'fullExtent'.")
    minX = full_extents['xmin']
    minY = full_extents['ymin']
    maxX = full_extents['xmax']
    maxY = full_extents['ymax']
    return (max_record_count, num_features, (minX, minY, maxX, maxY))

# Main function to query the server
def query_all_data(base_url, layer_number, output_geojson_filepath, where, wait_time, grid_size, sudo=False, minX=None, minY=None, maxX=None, maxY=None):
    features = []

    # Get the max number of results that can be returned, so we can check if we ever hit it.
    # Also get the extents so the user doesn't have to specify them
    max_record_count, num_features, bounds = get_server_info(base_url)
    if minX == None:
        minX, minY, maxX, maxY = bounds

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
            query = build_query(x, y, x_max, y_max, where)
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
    parser.add_argument("--subdivide", required=False, type=int, help="Split the job into an n x n square of jobs, resulting in n^2 files.")
    parser.add_argument("--require-tag", required=False, help="Pass a 'key=value' string to only get features with this attribute.")
    parser.add_argument("--avoid-tag", required=False, help="Pass a 'key=value' string to only get features without this attribute.")

    args = parser.parse_args()

    if args.require_tag and args.avoid_tag:
        raise ValueError("Cannot yet make multiple attribute restrictions. Only pass one of --require-tag and --avoid-tag.")

    # If subdividing, use subprocess to run this script a bunch of times
    if args.subdivide:
        if not (args.min_x or args.min_y or args.max_x or args.max_y):
            # If none are specified, detect the extents
            _, _, (minX, minY, maxX, maxY) = get_server_info(args.base_url)
        else:
            if not (args.min_x and args.min_y and args.max_x and args.max_y):
                raise ValueError("Must specify all of min_x, min_y, max_x, max_y.")
            minX, minY, maxX, maxY = (args.min_x, args.min_y, args.max_x, args.max_y)
        square_size_x = (maxX - minX) / args.subdivide
        square_size_y = (maxY - minY) / args.subdivide
        grid_size = min((args.grid_size, square_size_x, square_size_y))
        # Iterate over the grid
        filename_index = 1
        for i in range(args.subdivide):
            square_min_x = number_to_command_line_arg(minX + i * square_size_x)
            square_max_x = number_to_command_line_arg(minX + (i + 1) * square_size_x)
            for j in range(args.subdivide):
                print("Running job %s %d/%d." % (THIS_SCRIPT_NAME, filename_index, args.subdivide * args.subdivide))
                square_min_y = number_to_command_line_arg(minY + j * square_size_y)
                square_max_y = number_to_command_line_arg(minY + (j + 1) * square_size_y)
                current_geojson_filepath = args.output_geojson_filepath[:-len(".geojson")] + str(filename_index) + ".geojson"
                command_list = ['python3', THIS_SCRIPT_NAME, "--base-url", args.base_url, "-n", number_to_command_line_arg(args.layer_number),\
                        "-X", square_min_x, "-Y", square_min_y, "-U", square_max_x, "-V", square_max_y,\
                        "--wait-time", number_to_command_line_arg(args.wait_time),\
                        "--grid-size", number_to_command_line_arg(grid_size), "-o", current_geojson_filepath]
                if args.sudo:
                    command_list.append("--sudo")
                if args.dont_convert_to_shapefile:
                    command_list.append("--dont-convert-to-shapefile")
                if args.require_tag:
                    command_list.append("--require-tag")
                    comment_list.append(args.require_tag)
                if args.avoid_tag:
                    command_list.append("--avoid-tag")
                    command_list.append(args.avoid_tag)
                print(command_list)
                p = subprocess.Popen(command_list, shell=True)
                p.communicate()
                filename_index += 1
    else:
        if args.require_tag:
            key, value = args.require_tag.split('=')
            where = str(key) + " = " + "'%s'" % (value)
        elif args.avoid_tag:
            key, value = args.avoid_tag.split('=')
            where = str(key) + " != " + "'%s'" % (value)
        else:
            where = "1=1"

        # If not subdiving, run this script's functionality once
        if not (args.min_x or args.min_y or args.max_x or args.max_y):
            # If none are specified, detect the extents
            query_all_data(args.base_url, args.layer_number, args.output_geojson_filepath, where, args.wait_time,\
                    args.grid_size if args.grid_size else 0.001, sudo=args.sudo)
        else:
            if not (args.min_x and args.min_y and args.max_x and args.max_y):
                raise ValueError("Must specify all of min_x, min_y, max_x, max_y.")
            query_all_data(args.base_url, args.layer_number, args.output_geojson_filepath, where, args.wait_time,\
                    args.grid_size if args.grid_size else 0.001, args.sudo, args.min_x, args.min_y, args.max_x, args.max_y)

        if not args.dont_convert_to_shapefile:
            p = subprocess.Popen(['python3', CONVERT_TO_SHAPEFILE_NAME, "-i", args.output_geojson_filepath], shell=True)
            p.communicate()

if __name__ == "__main__":
    main()
