import argparse
import geojson
import math
from pyproj import Transformer

from general_utility import parse_latlon_string

GEOJSON_CRS = { "type": "name", "properties": { "name": "urn:ogc:def:crs:EPSG::4326"}}

def main():
    parser = argparse.ArgumentParser(description="Generate a grid in a geojson.")
    parser.add_argument("--sw", required=True, help="SW lat/lon corner of region.")
    parser.add_argument("--ne", required=True, help="NE lat/lon corner of region.")
    parser.add_argument("-s", "--max-square-size-meters", type=float, required=True, help="Max size a grid square is allowed to be (meters).")
    parser.add_argument("-o", "--output-geojson-path", required=True, help="Path to output geojson path")
    parser.add_argument("--osm-tag", required=False, help="'key=value' to apply to each grid polygon")

    args = parser.parse_args()

    if args.osm_tag:
        key, value = args.osm_tag.split('=')

    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857")
    inv_transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326")

    min_lat, min_lon = parse_latlon_string(args.sw)
    max_lat, max_lon = parse_latlon_string(args.ne)
    min_x, min_y = transformer.transform(min_lat, min_lon)
    max_x, max_y = transformer.transform(max_lat, max_lon)

    grid_size_x = math.floor((max_x - min_x) / args.max_square_size_meters)
    square_size_x = (max_x - min_x) / grid_size_x
    grid_size_y = math.floor((max_y - min_y) / args.max_square_size_meters)
    square_size_y = (max_y - min_y) / grid_size_y
    square_size = min(square_size_x, square_size_y)

    center_x = min_x + square_size / 2
    center_y = min_y + square_size / 2
    square_index = 1
    features = []
    while center_y < max_y:
        center_x = min_x + square_size / 2
        while center_x < max_x:
            vertices_meters = (\
                    (center_x - square_size / 2, center_y - square_size / 2),\
                    (center_x + square_size / 2, center_y - square_size / 2),\
                    (center_x + square_size / 2, center_y + square_size / 2),\
                    (center_x - square_size / 2, center_y + square_size / 2),\
                    (center_x - square_size / 2, center_y - square_size / 2)\
                    )
            vertices_lonlat = (inv_transformer.transform(x, y) for x,y in vertices_meters)
            vertices_latlon = [(lat, lon) for lon,lat in vertices_lonlat]
            geojson_poly = geojson.Polygon([vertices_latlon])
            properties = {"square_index" : str(square_index)}
            if args.osm_tag:
                properties[key] = value
            features.append(geojson.Feature(geometry=geojson_poly, properties=properties))
            center_x += square_size
            square_index += 1
        center_y += square_size

    dump = geojson.dumps(geojson.FeatureCollection(features=features, crs=GEOJSON_CRS), indent=4)
    f = open(args.output_geojson_path, 'w')
    f.write(dump)
    f.close()

if __name__ == "__main__":
    main()
