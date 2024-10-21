#!/usr/bin/env python3

"""
Recurse through subdirectories and create a geojson file consisting of the bbox
of each geojson file ending with a certain suffix.
"""

import argparse
import geojson
import shapely
import ntpath
import os

from general_utility import list_files_recursive
from geojson_utility import geojson_feature_to_shapely, shapely_polygon_to_geojson

def main():
    parser = argparse.ArgumentParser(description="Create geojson files consisting of bboxes of other geojsons.")
    parser.add_argument("-d", "--parent-dir", required=True, help="Path to parent directory.")
    parser.add_argument("-s", "--filename-suffix", required=True, help="The target suffix for geojson files. E.g. 'County' -> 'YatesCounty.geojson'.")

    args = parser.parse_args()

    for full_path in list_files_recursive(args.parent_dir):
        filename = ntpath.basename(full_path)
        if filename.split('.')[0].endswith(args.filename_suffix):
            f = open(full_path, 'r', encoding="utf8")
            geojson_contents = geojson.loads(f.read())
            f.close()

            if len(geojson_contents['features']) != 1:
                print("%s does not contain a single geojson feature." % (full_path))
                continue
            shapely_polygon = geojson_feature_to_shapely(geojson_contents['features'][0])
            min_x, min_y, max_x, max_y = shapely_polygon[0].bounds
            bbox_polygon = shapely.Polygon((\
                    (min_x, min_y),\
                    (max_x, min_y),\
                    (max_x, max_y),\
                    (min_x, max_y),\
                    (min_x, min_y)))
            feature = geojson.Feature(geometry=shapely_polygon_to_geojson(bbox_polygon), properties=geojson_contents['features'][0].properties)
            output_filepath = full_path.replace(args.filename_suffix + ".", args.filename_suffix + "Bbox" + ".")
            dump = geojson.dumps(geojson.FeatureCollection(features=[feature]))
            f = open(output_filepath, 'w')
            f.write(dump)
            f.close()

if __name__ == "__main__":
    main()
