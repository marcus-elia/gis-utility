#!/usr/bin/env python3

import argparse
import geojson
from unidecode import unidecode

OSM_KEY_NAME = "name"
OSM_KEY_ENGLISH_NAME = "name:en"

def sanitize_string(string):
    return unidecode(string)

def properties_has_both_names(properties):
    return OSM_KEY_NAME in properties and OSM_KEY_ENGLISH_NAME in properties and\
            properties[OSM_KEY_NAME] and properties[OSM_KEY_ENGLISH_NAME] # Yes, they can be None

def names_are_different(properties):
    return sanitize_string(properties[OSM_KEY_NAME]).lower() != sanitize_string(properties[OSM_KEY_ENGLISH_NAME]).lower()

def main():
    parser = argparse.ArgumentParser(description="Replace the osm 'name' value with the 'name:en' value if they differ.")
    parser.add_argument("-i", "--input-geojson-path", required=True, help="Path to input geojson file")
    parser.add_argument("-o", "--output-geojson-path", required=False, help="Path to output geojson file. If omitted, write to input file.")

    args = parser.parse_args()
    
    f = open(args.input_geojson_path, 'r', encoding="utf8")
    geojson_contents = geojson.loads(f.read())
    f.close()


    for geojson_feature in geojson_contents['features']:
        if properties_has_both_names(geojson_feature.properties) and names_are_different(geojson_feature.properties):
            geojson_feature.properties[OSM_KEY_NAME] = geojson_feature.properties[OSM_KEY_ENGLISH_NAME]

    output_geojson_path = args.output_geojson_path if args.output_geojson_path else args.input_geojson_path
    f = open(output_geojson_path, 'w', encoding="utf8")
    f.write(geojson.dumps(geojson_contents))
    f.close()

if __name__ == "__main__":
    main()
