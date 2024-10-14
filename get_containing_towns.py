#!/usr/bin/env python3

import argparse
import geojson
import json
import shapely
import time

from general_utility import get_time_estimate_string, standardize_city
from geojson_utility import geojson_feature_to_shapely

def main():
    parser = argparse.ArgumentParser(description="Create a json file mapping cities/villages to the towns containing them.")
    parser.add_argument("-i", "--input-geojson-path", required=True, help="Path to input geojson file of municipality polygons.")
    parser.add_argument("-o", "--output-json-path", required=True, help="Path to output json file.")

    args = parser.parse_args()

    f = open(args.input_geojson_path, 'r', encoding='utf-8')
    geojson_contents = geojson.loads(f.read())
    f.close()

    print("Loading %d municipality polygons." % (len(geojson_contents['features'])))
    name_to_polygon = {}
    name_to_area = {}
    for geojson_feature in geojson_contents['features']:
        if geojson_feature['properties']['name']:
            polygon = geojson_feature_to_shapely(geojson_feature)[0]
            polygon = shapely.Polygon(polygon.exterior)
            name_to_polygon[geojson_feature['properties']['name']] = polygon
            name_to_area[geojson_feature['properties']['name']] = polygon.area

    start_time = time.time()
    num_completed = 0
    num_points = len(name_to_polygon)
    print("Checking polygons for a containing town.")
    contained_to_containing = {}
    for contained_name in name_to_polygon:
        for containing_name in name_to_polygon:
            if contained_name == containing_name:
                continue
            # If the intersection between the polygons is more than 50% of the size
            # of the first polygon, we say there is containment.
            intersection = name_to_polygon[containing_name].intersection(name_to_polygon[contained_name])
            if intersection.area > 0.5 * name_to_area[contained_name]:
                if standardize_city(contained_name) != standardize_city(containing_name):
                    contained_to_containing[standardize_city(contained_name)] = standardize_city(containing_name)
                break
        # Log the status
        num_completed += 1
        time_elapsed = int(time.time() - start_time)
        print(get_time_estimate_string(time_elapsed, num_completed, num_points), end='\r')
    print()


    f = open(args.output_json_path, 'w')
    f.write(json.dumps(contained_to_containing))
    f.close()

if __name__ == "__main__":
    main()
