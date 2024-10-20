#!/usr/bin/env python3

import argparse
import geojson
import os

from general_utility import to_camel_case

def main():
    parser = argparse.ArgumentParser(description="Create a json file mapping cities/villages to the towns containing them.")
    parser.add_argument("-i", "--input-geojson-path", required=True, help="Path to input geojson file of polygons.")
    parser.add_argument("-o", "--output-directory", required=True, help="Path to output directory where geojsons will go.")
    parser.add_argument("--make-sub-directories", action='store_true', help="If you want each geojson to be in its own subdir.")
    parser.add_argument("-n", "--name-key", required=True, help="The key from each feature's properties you want to use to name the file.")
    parser.add_argument("--capitalize", action='store_true', help="Make each file/directory name be capital camelcase.")

    args = parser.parse_args()

    f = open(args.input_geojson_path, 'r', encoding='utf-8')
    geojson_contents = geojson.loads(f.read())
    f.close()

    if not os.path.exists(args.output_directory):
        os.mkdir(args.output_directory)

    num_skipped = 0
    num_written = 0
    for geojson_feature in geojson_contents['features']:
        if not args.name_key in geojson_feature.properties:
            num_skipped += 1
            continue
        name = to_camel_case(geojson_feature.properties[args.name_key], args.capitalize)
        filename = name + ".geojson"
        if args.make_sub_directories:
            subdir_path = os.path.join(args.output_directory, name)
            if not os.path.exists(subdir_path):
                os.mkdir(subdir_path)
            filepath = os.path.join(subdir_path, filename)
        else:
            filepath = os.path.join(args.output_directory, filename)
        dump = geojson.dumps(geojson.FeatureCollection(features=[geojson_feature]))
        f = open(filepath, 'w')
        f.write(dump)
        f.close()
        num_written += 1

    print("Wrote %d geojson files. Skipped %d missing %s tag." % (num_written, num_skipped, args.name_key))

if __name__ == "__main__":
    main()
