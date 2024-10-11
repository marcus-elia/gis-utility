#!/usr/bin/env python3

import argparse
from enum import Enum
import geojson
import os
import time

from general_utility import standardize_string, get_time_estimate_string

"""
OSM data often has a lot of non-useful tags that I consider to be clutter.
This script only retains the ones you specify.
"""

def main():
    parser = argparse.ArgumentParser(description="Remove all attributes except the keys given in the text file.")
    parser.add_argument("-i", "--input-geojson-path", required=True, help="Path to input geojson file")
    parser.add_argument("-k", "--key-filepath", required=True, help="Path to text file containing keys to retain. One key per line.")
    parser.add_argument("-o", "--output-geojson-path", required=False, help="Path to output geojson file. If omitted, write to input file.")

    args = parser.parse_args()

    print("Loading %s" % (args.input_geojson_path))
    start_time = time.time()
    f = open(args.input_geojson_path, 'r', encoding="utf8")
    geojson_contents = geojson.loads(f.read())
    f.close()
    print("Loaded %d features in %.2f seconds" % (len(geojson_contents['features']), time.time() - start_time))

    original_file_size_mb = os.stat(args.input_geojson_path).st_size / (1024 * 1024)

    # Get a list of keys to retain from the file.
    keys_to_keep = []
    f = open(args.key_filepath, 'r', encoding="utf8")
    for line in f:
        keys_to_keep.append(line.strip())
    f.close()

    # Iterate over every key in every feature to get a set of keys to remove.
    print("Compiling set of keys to remove")
    keys_to_remove = set()
    start_time = time.time()
    num_points = len(geojson_contents['features'])
    num_completed = 0
    for geojson_feature in geojson_contents['features']:
        for key in geojson_feature.properties:
            if not key in keys_to_keep:
                keys_to_remove.add(key)
        # Log the status
        num_completed += 1
        time_elapsed = int(time.time() - start_time)
        print(get_time_estimate_string(time_elapsed, num_completed, num_points), end='\r')
    print()

    # Iterate over every feature and remove the keys we don't want.
    num_attributes_removed = 0
    num_null_removed = 0
    num_features = 0
    start_time = time.time()
    num_points = len(geojson_contents['features'])
    num_completed = 0
    print("Removing keys from features")
    for geojson_feature in geojson_contents['features']:
        num_features += 1
        for key in keys_to_remove:
            try:
                if not geojson_feature.properties[key]:
                    num_null_removed += 1
                del geojson_feature.properties[key]
                num_attributes_removed += 1
            except KeyError:
                pass
        # Log the status
        num_completed += 1
        time_elapsed = int(time.time() - start_time)
        print(get_time_estimate_string(time_elapsed, num_completed, num_points), end='\r')
    print()

    output_geojson_path = args.output_geojson_path if args.output_geojson_path else args.input_geojson_path
    f = open(output_geojson_path, 'w', encoding="utf8")
    f.write(geojson.dumps(geojson_contents))
    f.close()

    final_file_size_mb = os.stat(output_geojson_path).st_size / (1024 * 1024)
    average_num_removed = num_attributes_removed / num_features
    percent_null = num_null_removed / num_attributes_removed * 100
    print("Removed %.2f keys per feature for %d features. %f%% were null." % (average_num_removed, num_features, percent_null))
    print("File size reduced from %.2f MB to %.2f MB." % (original_file_size_mb, final_file_size_mb))

if __name__ == "__main__":
    main()
