#!/usr/bin/env python3

import argparse
import csv
import geojson
from unidecode import unidecode

from general_utility import standardize_string

OSM_KEY_NAME = "name"

def main():
    parser = argparse.ArgumentParser(description="Add a new attribute to each of the features of a geojson file based on a csv.")
    parser.add_argument("-i", "--input-geojson-path", required=True, help="Path to input geojson file")
    parser.add_argument("-o", "--output-geojson-path", required=False, help="Path to output geojson file. If omitted, write to input file.")
    parser.add_argument("-c", "--csv-path", required=True, help="Path to csv file.")
    parser.add_argument("-n", "--name-index", type=int, required=True, help="Column index of the feature name in the csv.")
    parser.add_argument("-a", "--attribute-key", required=True, help="The name of the new attribute.")
    parser.add_argument("-v", "--value-index", type=int, required=True, help="Column index of the new attribute value in the csv.")
    parser.add_argument("-t", "--value-type", required=True, help="str, int, or float")
    parser.add_argument("--skip-header", action='store_true', help="If present, assume the CSV starts with a header.")
    parser.add_argument("--append-to-csv-names", required=False, help="Add a string to the end of each name in the CSV (like 'county').")

    args = parser.parse_args()
    
    f = open(args.input_geojson_path, 'r', encoding="utf8")
    geojson_contents = geojson.loads(f.read())
    f.close()

    csv_name_addon = args.append_to_csv_names if args.append_to_csv_names else ""

    name_to_value = {}
    with open(args.csv_path, mode='r', encoding="utf8") as file:
        csv_reader = csv.reader(file)
        header = next(csv_reader)
        for row in csv_reader:
            name = standardize_string(row[args.name_index] + csv_name_addon)
            value = row[args.value_index]
            if args.value_type == "int":
                value = int(value)
            elif args.value_type == "float":
                value = float(value)
            name_to_value[name] = [value, 0] # Int to count how many times this value gets used

    for geojson_feature in geojson_contents['features']:
        if not OSM_KEY_NAME in geojson_feature.properties or geojson_feature.properties[OSM_KEY_NAME] == None:
            continue
        name = standardize_string(geojson_feature.properties[OSM_KEY_NAME])
        if name in name_to_value:
            geojson_feature.properties[args.attribute_key] = name_to_value[name][0]
            name_to_value[name][1] += 1
        else:
            print("Feature named %s in the geojson did not have %s in the csv." % (geojson_feature.properties[OSM_KEY_NAME], args.attribute_key))

    for key in name_to_value:
        if name_to_value[key][1] == 0:
            print("Row with standardized name %s in the csv was not matched with a feature in the geojson." % (key))

    output_geojson_path = args.output_geojson_path if args.output_geojson_path else args.input_geojson_path
    f = open(output_geojson_path, 'w', encoding="utf8")
    f.write(geojson.dumps(geojson_contents))
    f.close()

if __name__ == "__main__":
    main()
