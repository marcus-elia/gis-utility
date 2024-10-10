#!/usr/bin/env python3

import argparse
from enum import Enum
import geojson

from general_utility import standardize_string

"""
Performing a union operation in QGIS can result in a layer with some features having
name=Philadelphia and others having name_2=Pittsburgh. This script can combine them.
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
    parser = argparse.ArgumentParser(description="If two keys are potentially present for the same data, merge them.")
    parser.add_argument("-i", "--input-geojson-path", required=True, help="Path to input geojson file")
    parser.add_argument("--key1", required=True, help="The primary key (e.g. 'name')")
    parser.add_argument("--key2", required=True, help="The secondary key (e.g. 'name_2')")
    parser.add_argument("-o", "--output-geojson-path", required=False, help="Path to output geojson file. If omitted, write to input file.")

    args = parser.parse_args()
    
    f = open(args.input_geojson_path, 'r', encoding="utf8")
    geojson_contents = geojson.loads(f.read())
    f.close()

    num_combined = 0
    num_features = 0
    for geojson_feature in geojson_contents['features']:
        num_features += 1
        key_presence = check_key_presence(geojson_feature.properties, args.key1, args.key2)
        if key_presence == KeyPresence.Key2Only:
            geojson_feature.properties[args.key1] = geojson_feature.properties[args.key2]
            num_combined += 1

    output_geojson_path = args.output_geojson_path if args.output_geojson_path else args.input_geojson_path
    f = open(output_geojson_path, 'w', encoding="utf8")
    f.write(geojson.dumps(geojson_contents))
    f.close()
    print("Copied %s to %s for %d/%d features." % (args.key2, args.key1, num_combined, num_features))

if __name__ == "__main__":
    main()
