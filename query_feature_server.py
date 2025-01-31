import argparse
import json
import requests
import subprocess
import time

from general_utility import get_time_estimate_string

CONVERT_TO_SHAPEFILE_NAME = "geojson_to_shapefile.py"

def main():
    parser = argparse.ArgumentParser(description="Query data from a FeatureServer.")
    parser.add_argument("-n", "--layer-number", required=True, type=int, help="The number of the layer on the server.")
    parser.add_argument("--base-url", required=True, help="FeatureServer url (ending with /FeatureServer)")
    parser.add_argument("--wait-time", type=float, required=True, help="Seconds between queries")
    parser.add_argument("--output-geojson-filepath", required=True, help="Output geojson filepath")
    parser.add_argument("--convert-to-shapefile", action='store_true', help="Convert geojson to shp.zip with the same name.")
    parser.add_argument("--result-record-count", default=1000, type=int, help="How many records to request per query.")

    args = parser.parse_args()

    params = {
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": "true",
        "f": "geojson",
        "resultOffset": 0,
        "resultRecordCount": args.result_record_count
    }

    all_features = []
    base_url = args.base_url + "/%d/query" % (args.layer_number)

    count_params = {
        "where": "1=1",
        "returnCountOnly": "true",
        "f": "json"
    }

    response = requests.get(base_url, params=count_params)
    count_data = response.json()

    if "count" in count_data:
        num_features = count_data['count']
        print("FeatureServer has %d features." % (num_features))
    else:
        num_features = None
        print("Failed to retrieve count.")

    start_time = time.time()
    while True:
        response = requests.get(base_url, params=params)
        data = response.json()

        if "features" in data:
            all_features.extend(data["features"])

        # Stop if no more features
        if len(data["features"]) < params["resultRecordCount"]:
            break

        # Increment offset for next batch
        params["resultOffset"] += params["resultRecordCount"]
        time.sleep(args.wait_time)
        if num_features != None:
            time_elapsed = time.time() - start_time
            print(get_time_estimate_string(time_elapsed, len(all_features), num_features))

    # Save the results as GeoJSON
    geojson_output = {
        "type": "FeatureCollection",
        "features": all_features
    }
    f = open(args.output_geojson_filepath, 'w')
    f.write(json.dumps(geojson_output))
    f.close()

    if args.convert_to_shapefile:
        p = subprocess.Popen(['python3', CONVERT_TO_SHAPEFILE_NAME, "-i", args.output_geojson_filepath], shell=True)
        p.communicate()


if __name__ == "__main__":
    main()
