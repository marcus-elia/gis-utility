#!/usr/bin/env python3

"""
Recurse through subdirectories and apply an operation to all geojson files
whose names end with a certain suffix.
"""

import argparse
import geojson
import geopandas
import shapely
import ntpath
import os
import time

from general_utility import list_files_recursive, get_time_estimate_string
from geojson_utility import geojson_feature_to_shapely, shapely_polygon_to_geojson

def count_files(parent_dir, filename_suffix):
    count = 0
    for full_path in list_files_recursive(parent_dir):
        filename = ntpath.basename(full_path)
        if filename.split('.')[0].endswith(filename_suffix):
            count += 1
    return count

def create_bbox_file(full_path, filename_suffix):
    f = open(full_path, 'r', encoding="utf8")
    geojson_contents = geojson.loads(f.read())
    f.close()

    if len(geojson_contents['features']) != 1:
        print("%s does not contain a single geojson feature." % (full_path))
        return
    shapely_polygon = geojson_feature_to_shapely(geojson_contents['features'][0])
    min_x, min_y, max_x, max_y = shapely_polygon[0].bounds
    bbox_polygon = shapely.Polygon((\
            (min_x, min_y),\
            (max_x, min_y),\
            (max_x, max_y),\
            (min_x, max_y),\
            (min_x, min_y)))
    feature = geojson.Feature(geometry=shapely_polygon_to_geojson(bbox_polygon), properties=geojson_contents['features'][0].properties)
    output_filepath = full_path.replace(filename_suffix + ".", filename_suffix + "Bbox" + ".")
    dump = geojson.dumps(geojson.FeatureCollection(features=[feature]))
    f = open(output_filepath, 'w')
    f.write(dump)
    f.close()

def reproject_to_epsg(full_path, epsg):
    gdf = geopandas.read_file(full_path)
    gdf = gdf.to_crs(int(epsg))
    gdf.to_file(full_path)    

def main():
    parser = argparse.ArgumentParser(description="Apply operations to geojson files.")
    parser.add_argument("-d", "--parent-dir", required=True, help="Path to parent directory.")
    parser.add_argument("-s", "--filename-suffix", required=True, help="The target suffix for geojson files. E.g. 'County' -> 'YatesCounty.geojson'.")
    operation_group = parser.add_mutually_exclusive_group(required=True)
    operation_group.add_argument("--add-bbox-file", action='store_true', help='Create an adjacent file containing the bbox of the polygon.')
    operation_group.add_argument("--reproject-to-epsg", help='Reproject geojson in place to the specified EPSG code.')

    args = parser.parse_args()

    start_time = time.time()
    num_files = count_files(args.parent_dir, args.filename_suffix)
    num_completed = 0
    for full_path in list_files_recursive(args.parent_dir):
        filename = ntpath.basename(full_path)
        if filename.split('.')[0].endswith(args.filename_suffix):
            if args.add_bbox_file:
                create_bbox_file(full_path, args.filename_suffix)
            elif args.reproject_to_epsg:
                reproject_to_epsg(full_path, args.reproject_to_epsg)
            # Log the status
            num_completed += 1
            time_elapsed = int(time.time() - start_time)
            print(get_time_estimate_string(time_elapsed, num_completed, num_files), end='\r')
    print()

if __name__ == "__main__":
    main()
