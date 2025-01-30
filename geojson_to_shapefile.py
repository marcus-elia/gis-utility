#!/usr/bin/env python3

import argparse
import geopandas
import os
import zipfile

SHAPEFILE_EXTENSIONS = (".cpg", ".dbf", ".prj", ".shp", ".shx")

def main():
    parser = argparse.ArgumentParser(description="Convert geojson to shapefile.")
    parser.add_argument("-i", "--input-geojson-path", required=True, help="Path to input geojson file.")
    parser.add_argument("-o", "--output-shapefile-path", required=False, help="Path to output shapefile file.")
    parser.add_argument("--zip", action='store_true', help="If present, move output files into a zip.")

    args = parser.parse_args()

    gdf = geopandas.read_file(args.input_geojson_path)
    if args.output_shapefile_path:
        output_path = args.output_shapefile_path
    else:
        output_path = args.input_geojson_path.split('.')[-2] + ".shp.zip"
    gdf.to_file(output_path)

    # Note: this is not needed because you can give a .shp.zip filepath to geopandas.to_file().
    if args.zip:
        base_filepath = args.output_shapefile_path.split('.')[-2]
        zip_filepath = args.output_shapefile_path + ".zip"
        with zipfile.ZipFile(zip_filepath, 'w') as zip_file:
            for extension in SHAPEFILE_EXTENSIONS:
                filepath = base_filepath + extension
                zip_file.write(filepath)
                os.remove(filepath)

if __name__ == "__main__":
    main()
