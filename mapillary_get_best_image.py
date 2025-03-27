import argparse
import json
import math
from geopy.distance import geodesic


def parse_lat_lon(lat_lon_str):
    """Parse latitude and longitude from the input string."""
    try:
        lat, lon = map(float, lat_lon_str.split(","))
        return lat, lon
    except ValueError:
        raise argparse.ArgumentTypeError(
            "Invalid format for latitude/longitude. Use 'lat,lon'."
        )


def bearing(lat1, lon1, lat2, lon2):
    """Calculate the bearing from (lat1, lon1) to (lat2, lon2)."""
    delta_lon = math.radians(lon2 - lon1)
    lat1, lat2 = math.radians(lat1), math.radians(lat2)

    x = math.sin(delta_lon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(
        delta_lon
    )
    initial_bearing = math.atan2(x, y)
    return (math.degrees(initial_bearing) + 360) % 360


def is_within_fov(target_bearing, image_bearing, horizontal_fov):
    """Check if the target bearing falls within the image's horizontal field of view."""
    half_fov = horizontal_fov / 2
    min_bearing = (image_bearing - half_fov) % 360
    max_bearing = (image_bearing + half_fov) % 360

    if min_bearing < max_bearing:
        return min_bearing <= target_bearing <= max_bearing
    else:
        return target_bearing >= min_bearing or target_bearing <= max_bearing


def find_best_image(target_point, geojson_file):
    """Find the best image that is facing the target point."""
    with open(geojson_file, "r") as file:
        data = json.load(file)

    best_image = None
    closest_distance = float("inf")

    for feature in data["features"]:
        props = feature["properties"]
        coords = feature["geometry"]["coordinates"]
        image_lat, image_lon = coords[1], coords[0]
        compass_angle = props["computed_compass_angle"]
        horizontal_fov = props["horizontal_fov"]

        # Calculate distance and bearing to target point
        distance_to_target = geodesic((image_lat, image_lon), target_point).meters
        target_bearing = bearing(image_lat, image_lon, *target_point)

        # Check if target is within the image's field of view
        if is_within_fov(target_bearing, compass_angle, horizontal_fov):
            if distance_to_target < closest_distance:
                closest_distance = distance_to_target
                best_image = {
                    "image_id": props["image_id"],
                    "latitude": image_lat,
                    "longitude": image_lon,
                    "distance_to_target": distance_to_target,
                    "bearing_to_target": target_bearing,
                    "compass_angle": compass_angle,
                    "horizontal_fov": horizontal_fov,
                    "image_url": props["image_url"],
                }

    return best_image


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Find the best image facing a given target position."
    )
    parser.add_argument(
        "--target",
        type=parse_lat_lon,
        help="Target latitude and longitude in the form 'lat,lon'.",
    )
    parser.add_argument(
        "--geojson-path",
        type=str,
        help="Path to the GeoJSON file containing image nodes.",
    )
    args = parser.parse_args()

    best_image = find_best_image(args.target, args.geojson_path)
    if best_image:
        print("Best image found:")
        print(json.dumps(best_image, indent=4))
    else:
        print("No suitable image found.")
