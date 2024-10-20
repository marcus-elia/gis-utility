#!/usr/bin/env python3

import argparse
import geojson
import os
import time

from general_utility import to_camel_case, get_time_estimate_string
from geojson_utility import geojson_feature_to_shapely

def main():
    parser = argparse.ArgumentParser(description="Take a geojson file of points and split into a bunch of files based on another geojson of polygons.")
    parser.add_argument("-r", "--region-geojson-path", required=True, help="Path to input geojson file of polygons.")
    parser.add_argument("-p", "--point-geojson-path", required=True, help="Path to input geojson file of points.")
    parser.add_argument("-o", "--output-directory", required=True, help="Path to output directory where geojsons will go.")
    parser.add_argument("--make-sub-directories", action='store_true', help="If you want each geojson to be in its own subdir.")
    parser.add_argument("-n", "--name-key", required=True, help="The key from each feature's properties you want to use to name the file (e.g. 'name')")
    parser.add_argument("--name-suffix", required=False, help="Append to each filename. E.g. 'TaxParcels' -> 'JeffersonTaxParcels.geojson")
    parser.add_argument("--capitalize", action='store_true', help="Make each file/directory name be capital camelcase.")

    args = parser.parse_args()

    filename_suffix = args.name_suffix if args.name_suffix else ""

    print("Loading points.")
    start_time = time.time()
    f = open(args.point_geojson_path, 'r', encoding='utf-8')
    geojson_points = geojson.loads(f.read())
    f.close()
    print("Loaded points in %.2f seconds." % (time.time() - start_time))

    f = open(args.region_geojson_path, 'r', encoding='utf-8')
    geojson_polygons = geojson.loads(f.read())
    f.close()

    if not os.path.exists(args.output_directory):
        os.mkdir(args.output_directory)

    print("Filtering %d points into %d polygons." % (len(geojson_points['features']), len(geojson_polygons['features'])))
    num_skipped = 0
    num_written = 0
    num_completed = 0
    start_time = time.time()
    num_polygons = len(geojson_polygons['features'])
    for geojson_polygon in geojson_polygons['features']:
        # Get the name of the region
        if not args.name_key in geojson_polygons.properties:
            num_skipped += 1
            continue
        name = to_camel_case(geojson_polygon.properties[args.name_key], args.capitalize)
        filename = name + filename_suffix + ".geojson"

        # Get the set of points within the region
        points = []
        shapely_polygon = geojson_feature_to_shapely(geojson_polygon.geometry)
        for geojson_point in geojson_points['features']:
            shapely_point = geojson_feature_to_shapely(geojson_point.geometry)
            if shapely_polygon.contains(shapely_point):
                points.append(geojson_point)

        # Write the points to a new geojson file
        if args.make_sub_directories:
            subdir_path = os.path.join(args.output_directory, name)
            if not os.path.exists(subdir_path):
                os.mkdir(subdir_path)
            filepath = os.path.join(subdir_path, filename)
        else:
            filepath = os.path.join(args.output_directory, filename)
        dump = geojson.dumps(geojson.FeatureCollection(features=points))
        f = open(filepath, 'w')
        f.write(dump)
        f.close()
        num_written += 1
        
        # Log the status
        num_completed += 1
        time_elapsed = int(time.time() - start_time)
        print(get_time_estimate_string(time_elapsed, num_completed, num_polygons), end='\r')
    print()

    print("Wrote %d geojson files. Skipped %d missing %s tag." % (num_written, num_skipped, args.name_key))

if __name__ == "__main__":
    main()
