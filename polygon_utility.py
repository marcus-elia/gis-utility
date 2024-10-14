#!/usr/bin/env python3

import shapely
import utm

class Bbox:
    def __init__(self, linestring):
        coords = list(linestring.coords)
        self.min_x, self.min_y = coords[0]
        self.max_x, self.max_y = coords[0]
        for x, y in coords[1:]:
            self.min_x = min(x, self.min_x)
            self.min_y = min(y, self.min_y)
            self.max_x = max(x, self.max_x)
            self.max_y = max(y, self.max_y)

class PolygonWithProperties:
    def __init__(self, polygon, properties):
        self.polygon = polygon
        self.properties = properties

def point_lonlat_to_utm(point_lonlat, offset=(0,0)):
    x, y, zone, letter = utm.from_latlon(point_lonlat.y, point_lonlat.x)
    return shapely.Point(x + offset[0], y + offset[1])

def line_lonlat_to_utm(line_lonlat, offset=(0,0)):
    """
    Convert a shapely line from lat/lon to UTM. If an offset is specified, it is
    added to every point (in UTM).
    """
    # Get the UTM zone of the first point
    _, _, original_zone, _ = utm.from_latlon(line_lonlat.coords[0][1], line_lonlat.coords[0][0])

    # Iterate over the outer boundary and convert it
    points_utm = []
    for lonlat_point in line_lonlat.coords:
        # Convert
        x, y, zone, letter = utm.from_latlon(lonlat_point[1], lonlat_point[0])

        # Check for a UTM zone crossing
        if zone != original_zone:
            print("Line crosses from UTM zone %d to %d. Omitting." % (original_zone, zone))
            return shapely.Line()

        # If nothing bad happened, add the point to the new line
        points_utm.append((x + offset[0], y + offset[1]))

    return shapely.LineString(points_utm)

def poly_lonlat_to_utm(poly_lonlat, offset=(0,0)):
    """
    Convert a shapely polygon from lat/lon to UTM. This does both
    the exterior and the holes. If an offset is specified, it is
    added to every point (in UTM).
    """
    # First, don't do anything to an empty polygon
    if len(poly_lonlat.exterior.coords) == 0:
        return shapely.Polygon()

    # Get the UTM zone of the first point
    _, _, original_zone, _ = utm.from_latlon(poly_lonlat.exterior.coords[0][1], poly_lonlat.exterior.coords[0][0])

    # Iterate over the outer boundary and convert it
    outer_boundary_utm = []
    for lonlat_point in poly_lonlat.exterior.coords:
        # Convert
        x, y, zone, letter = utm.from_latlon(lonlat_point[1], lonlat_point[0])

        # Check for a UTM zone crossing
        if zone != original_zone:
            print("Polygon crosses from UTM zone %d to %d. Omitting." % (original_zone, zone))
            return shapely.Polygon()

        # If nothing bad happened, add the point to the new polygon
        outer_boundary_utm.append((x + offset[0], y + offset[1]))

    # Do the holes
    holes_utm = []
    for hole in poly_lonlat.interiors:
        hole_utm = []
        for lonlat_point in hole.coords:
            # Convert
            x, y, zone, letter = utm.from_latlon(lonlat_point[1], lonlat_point[0])

            # Check for a UTM zone crossing
            if zone != original_zone:
                print("Polygon crosses from UTM zone %d to %d. Omitting." % (original_zone, zone))
                continue

            # If nothing bad happened, add the point to the new polygon
            hole_utm.append((x + offset[0], y + offset[1]))
        holes_utm.append(hole_utm)

    return shapely.Polygon(outer_boundary_utm, holes_utm)

def polygon_list_contains(polygon_list, point):
    for polygon in polygon_list:
        try:
            if polygon.contains(point):
                return True
        except shapely.errors.GEOSException:
            pass
    return False

def transform_point(input_point, transform):
    x, y = transform(input_point.x, input_point.y)
    return shapely.Point(x, y)

def transform_coordinates(input_coords, transform):
    return [transform(x, y) for x,y in input_coords]

def transform_linestring(input_linestring, transform):
    return shapely.LineString(transform_coordinates(input_linestring.coords, transform))

def transform_polygon(input_polygon, transform):
    outer = transform_coordinates(input_polygon.exterior.coords, transform)
    holes = [transform_coordinates(hole.coords, transform) for hole in input_polygon.interiors]
    return shapely.Polygon(outer, holes)

def swap_coordinates(xy_coords):
    swap = lambda x,y : (y, x)
    return transform_coordinates(xy_coords, swap)

def swap_point_coordinates(point):
    return shapely.Point(point.y, point.x)

def swap_linestring_coordinates(linestring):
    return shapely.LineString(swap_coordinates(linestring.coords))

def swap_polygon_coordinates(polygon):
    swap = lambda x,y : (y, x)
    return transform_polygon(polygon, swap)
