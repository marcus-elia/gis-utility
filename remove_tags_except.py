#!/usr/bin/env python3

import argparse
from enum import Enum
import geojson

from general_utility import standardize_string

"""
OSM data often has a lot of non-useful tags that I consider to be clutter.
This script only retains the ones you specify.
"""

class KeyPresence(Enum):
    Both = 1
    Key1Only = 2
    Key2Only = 3
    Neither = 4

def check_key_presence(properties, key1, key2):
    key1_present = key1 in properties and properties[key1]
    key2_present = key2 in properties and properties[key2]
    if key1_present and key2_present:
        return KeyPresence.Both
    elif key1_present:
        return KeyPresence.Key1Only
    elif key2_present:
        return KeyPresence.Key2Only
    else:
        return KeyPresence.Neither

def main():
    parser = argparse.ArgumentParser(description="Remove all attributes except the keys given in the text file.")
    parser.add_argument("-i", "--input-geojson-path", required=True, help="Path to input geojson file")
    parser.add_argument("-k", "--key-filepath", required=True, help="Path to text file containing keys to retain. One key per line.")
    parser.add_argument("-o", "--output-geojson-path", required=False, help="Path to output geojson file. If omitted, write to input file.")

    args = parser.parse_args()
    
    f = open(args.input_geojson_path, 'r', encoding="utf8")
    geojson_contents = geojson.loads(f.read())
    f.close()

    # Get a list of keys to retain from the file.
    keys_to_keep = []
    f = open(args.key_filepath, 'r', encoding="utf8")
    for line in f:
        keys_to_keep.append(line.strip())
    f.close()

    # Iterate over every key in every feature to get a set of keys to remove.
    keys_to_remove = set()
    for geojson_feature in geojson_contents['features']:
        for key in geojson_feature.properties:
            if not key in keys_to_keep:
                keys_to_remove.add(key)

    # Iterate over every feature and remove the keys we don't want.
    num_attributes_removed = 0
    num_features = 0
    for geojson_feature in geojson_contents['features']:
        num_features += 1
        for key in keys_to_remove:
            try:
                del geojson_feature.properties[key]
                num_attributes_removed += 1
            except KeyError:
                pass

    output_geojson_path = args.output_geojson_path if args.output_geojson_path else args.input_geojson_path
    f = open(output_geojson_path, 'w', encoding="utf8")
    f.write(geojson.dumps(geojson_contents))
    f.close()

    average_num_removed = num_attributes_removed / num_features
    print("Removed %.2f keys per feature for %d features." % (average_num_removed, num_features))

if __name__ == "__main__":
    main()
