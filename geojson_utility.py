#!/usr/bin/env python3

import geojson
import os
import shapely
import sys
import utm

from polygon_utility import *

def geojson_polygon_to_shapely(geojson_polygon):
    # Special case for empty polygon
    if len(geojson_polygon) == 0:
        return shapely.Polygon()

    # Single polygon with no holes
    if type(geojson_polygon[0]) != list:
        outer_boundary = []
        for point in geojson_polygon:
            x = point[0]
            y = point[1]
            outer_boundary.append((x, y))
        return shapely.Polygon(outer_boundary)
    
    # A polygon that does have holes
    outer_boundary = []
    holes = []
    for point in geojson_polygon[0]:
        x = point[0]
        y = point[1]
        outer_boundary.append((x, y))
    for geojson_hole in geojson_polygon[1:]:
        hole = []
        for point in geojson_hole:
            x = point[0]
            y = point[1]
            hole.append((x, y))
        holes.append(hole)

    return shapely.Polygon(outer_boundary, holes)

def geojson_multipolygon_to_shapely(geojson_multipolygon):
    polygons = []
    for geojson_polygon in geojson_multipolygon:
        polygons.append(geojson_polygon_to_shapely(geojson_polygon))

    return polygons

def geojson_point_to_shapely(geojson_point):
    return shapely.Point(geojson_point[0], geojson_point[1])

def geojson_multipoint_to_shapely(geojson_multipoint):
    return [geojson_point_to_shapely(p) for p in geojson_multipoint]

def geojson_line_to_shapely(geojson_line):
    return shapely.LineString([(point[0], point[1]) for point in geojson_line])

def geojson_multiline_to_shapely(geojson_multiline):
    return [geojson_line_to_shapely(geojson_line) for geojson_line in geojson_multiline]

def geojson_feature_to_shapely(geojson_feature):
    if geojson_feature.geometry["type"] == "MultiPolygon":
        return geojson_multipolygon_to_shapely(geojson_feature.geometry.coordinates)
    elif geojson_feature.geometry["type"] == "Polygon":
        return [geojson_polygon_to_shapely(geojson_feature.geometry.coordinates)]
    elif geojson_feature.geometry["type"] == "Point":
        return [geojson_point_to_shapely(geojson_feature.geometry.coordinates)]
    elif geojson_feature.geometry["type"] == "MultiPoint":
        return geojson_multipoint_to_shapely(geojson_feature.geometry.coordinates)
    elif geojson_feature.geometry["type"] == "LineString":
        return [geojson_line_to_shapely(geojson_feature.geometry.coordinates)]
    elif geojson_feature.geometry["type"] == "MultiLineString":
        return geojson_multiline_to_shapely(geojson_feature.geometry.coordinates)
    else:
        print("Unknown geojson geometry type %s." % (geojson_feature.geometry["type"]))
        return []

def num_features_in_geojson_file(geojson_contents):
    return len(geojson_contents['features'])

def read_geojson_file_to_shapely_list(directory_path, filename):
    shapely_polygons = []
    try:
        f = open(os.path.join(directory_path, filename))
        geojson_contents = geojson.loads(f.read())
        f.close()

        for geojson_feature in geojson_contents['features']:
           shapely_polygons += geojson_feature_to_shapely(geojson_feature)
    except FileNotFoundError:
        pass

    return shapely_polygons

def geojson_polygon_to_pwp(geojson_polygon, properties):
    polygon = geojson_polygon_to_shapely(geojson_polygon)
    return PolygonWithProperties(polygon, properties)

def geojson_multipolygon_to_pwps(geojson_multipolygon, properties):
    pwps = []
    for geojson_polygon in geojson_multipolygon.coordinates:
        pwps.append(geojson_polygon_to_pwp(geojson_polygon, properties))
    return pwps

def geojson_feature_to_pwps(geojson_feature):
    if geojson_feature.geometry["type"] == "MultiPolygon":
        return geojson_multipolygon_to_pwps(geojson_feature.geometry, geojson_feature.properties)
    elif geojson_feature.geometry["type"] == "Polygon":
        return [geojson_polygon_to_pwp(geojson_feature.geometry.coordinates, geojson_feature.properties)]
    else:
        return PolygonWithProperties(shapely.Polygon(), {})

def shapely_point_to_geojson(shapely_point):
    return geojson.Point([shapely_point.x, shapely_point.y])

def shapely_points_to_geojson(shapely_points):
    return geojson.MultiPoint([[p.x, p.y] for p in shapely_points])

def shapely_coords_to_geojson(shapely_coords):
    return geojson.LineString([[p[0], p[1]] for p in shapely_coords])

def shapely_line_to_geojson(shapely_line):
    return shapely_coords_to_geojson(shapely_line.coords)

def shapely_multiline_to_geojson(shapely_multiline):
    return geojson.MultiLineString([shapely_line_to_geojson(shapely_line) for shapely_line in shapely_multiline.geoms])

def shapely_polygon_to_geojson(shapely_poly):
    return geojson.Polygon([list(shapely_poly.exterior.coords)] + [list(hole.coords) for hole in shapely_poly.interiors])

def shapely_multipolygon_to_geojson(shapely_multipoly):
    return geojson.MultiPolygon([shapely_polygon_to_geojson(shapely_poly) for shapely_poly in shapely_multipoly.geoms])

def polygon_with_properties_to_geojson(pwp):
    return geojson.Feature(geometry=shapely_polygon_to_geojson(pwp.polygon), properties=pwp.properties)

def geojson_to_city_dictionary(file_contents):
    geojson_contents = geojson.loads(file_contents)

    cities_to_latlon = {}
    for geojson_feature in geojson_contents['features']:
        city_name = geojson_feature.properties["name"]
        lat, lon = geojson_feature.geometry["coordinates"][1], geojson_feature.geometry["coordinates"][0]
        cities_to_latlon[city_name] = (lat, lon)
    return cities_to_latlon
