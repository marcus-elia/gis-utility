import argparse
import geojson
import json
import math
import os
from PIL import Image
import requests
from shapely import from_geojson, Polygon, MultiPolygon

from mapillary_nearest_images import image_metadata_name

API_KEY = "MLY|9579478658738838|77aac5cb29c86a35823e17be7aee23ac"
API_BASE_URL = "https://a.mapillary.com/v3/images/"

# Any image further than this from the building is not useful (meters)
MAX_ALLOWED_DISTANCE = 300


def calculate_bearing(lat1, lon1, lat2, lon2):
    """Calculate bearing between two latitude/longitude points."""
    lat1, lat2 = map(math.radians, [lat1, lat2])
    diff_lon = math.radians(lon2 - lon1)
    x = math.sin(diff_lon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(
        diff_lon
    )
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def download_image(image_id, image_filepath):

    header = {"Authorization": "OAuth {}".format(API_KEY)}
    url = "https://graph.mapillary.com/{}?fields=thumb_2048_url".format(image_id)
    r = requests.get(url, headers=header)
    data = r.json()
    image_url = data["thumb_2048_url"]

    with open(image_filepath, "wb") as f:
        image_data = requests.get(image_url, stream=True).content
        f.write(image_data)


def building_polygon_from_geojson(geojson_filepath):
    """
    Requires the geojson to contain a single polygon. Returns a shapely version of it.
    """
    with open(geojson_filepath, "r") as file:
        geojson_data = json.load(file)

    geometry = from_geojson(geojson.dumps(geojson_data["features"][0]["geometry"]))

    if isinstance(geometry, Polygon):
        return geometry  # Return the polygon as is
    elif isinstance(geometry, MultiPolygon):
        # Return the outer boundary (convex hull) of the largest polygon in the multipolygon
        return max(geometry.geoms, key=lambda p: p.area)
    else:
        raise ValueError(
            "The GeoJSON does not contain a valid polygon or multipolygon."
        )


def get_image_metadatas(geojson_file):
    with open(geojson_file, "r") as file:
        data = json.load(file)
    return [feature["properties"] for feature in data["features"]]


def score_image_relevance(image_metadata):
    distance = image_metadata["distance_from_target"]
    angle = abs(image_metadata["angle_delta"])
    distance = min(distance, 200)
    angle = min(angle, 45)
    # Lower score means better
    # TODO: Think hard about the constant scaling the angle's influence
    return 1 - 1 / (1 + 3 * angle + distance)


def sort_images(image_metadatas):
    return sorted(image_metadatas, key=lambda item: score_image_relevance(item))


def find_relative_bearing_range(polygon, img_lat, img_lon, compass_direction):
    """
    Calculate the min and max bearings relative to the camera's compass direction.

    Args:
        polygon (shapely.geometry.Polygon): The building polygon.
        img_lat, img_lon (float): Latitude and longitude of the image location.
        compass_direction (float): Camera's compass direction in degrees.

    Returns:
        tuple: (min_relative_bearing, max_relative_bearing), both adjusted relative to the camera's view.
    """
    min_bearing, max_bearing = float("inf"), float("-inf")

    for point in polygon.exterior.coords:
        lon, lat = point
        bearing = calculate_bearing(img_lat, img_lon, lat, lon)

        # Calculate the bearing relative to the camera's direction and normalize to [0, 360)
        relative_bearing = bearing - compass_direction
        if relative_bearing > 180:
            relative_bearing -= 360
        if relative_bearing < -180:
            relative_bearing += 360

        min_bearing = min(min_bearing, relative_bearing)
        max_bearing = max(max_bearing, relative_bearing)

    return min_bearing, max_bearing


def crop_image_based_on_relative_bearing(
    image_path, metadata, min_bearing, max_bearing
):
    """
    Crop the image horizontally based on the relative bearing range.

    Args:
        image_path (str): Path to the image.
        metadata (dict): Dictionary containing image metadata ('lat', 'lon', 'compass', 'fov').
        min_bearing, max_bearing (float): Bearings relative to the camera's direction.

    Returns:
        PIL.Image.Image: Cropped image.
    """
    image = Image.open(image_path)
    width, height = image.size

    horizontal_fov = metadata["horizontal_fov"]

    left_pixel = width / 2 + int((min_bearing / horizontal_fov) * width)
    right_pixel = width / 2 + int((max_bearing / horizontal_fov) * width)

    # Crop the image horizontally
    left_crop = max(0, left_pixel)
    right_crop = min(width, right_pixel)

    cropped_image = image.crop((left_crop, 0, right_crop, height))
    return cropped_image


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Find the best image facing a given target position."
    )
    parser.add_argument(
        "--target-building-geojson-filepath",
        type=str,
        required=False,
        help="Path to GeoJSON file containing only the footprint of the building.",
    )
    parser.add_argument(
        "--num-images", type=int, required=True, help="Max number of images to download"
    )
    parser.add_argument(
        "-b",
        "--building-name",
        type=str,
        help="Name to identify building that will be used as filename prefix",
    )
    parser.add_argument(
        "-o",
        "--building-dir",
        type=str,
        help="Building-specific directory where output files are created",
    )
    args = parser.parse_args()

    image_point_geojson_path = os.path.join(args.building_dir, image_metadata_name)

    if args.target_building_geojson_filepath:
        footprint = building_polygon_from_geojson(args.target_building_geojson_filepath)
    else:
        footprint = None

    image_metadatas = sort_images(get_image_metadatas(image_point_geojson_path))
    if image_metadatas:
        for i in range(min(len(image_metadatas), args.num_images)):
            print("Image #%d:" % (i + 1))
            print(json.dumps(image_metadatas[i], indent=4))

            image_filepath = os.path.join(
                args.building_dir, args.building_name + "_" + str(i + 1) + ".jpg"
            )
            download_image(image_metadatas[i]["image_id"], image_filepath)
            print("Image downloaded to %s." % (image_filepath))

            if footprint:
                # cropped_image = crop_image_to_projected_polygon(
                #     image_filepath, image_metadatas[i], footprint
                # )
                min_bearing, max_bearing = find_relative_bearing_range(
                    footprint,
                    image_metadatas[i]["lat"],
                    image_metadatas[i]["lon"],
                    image_metadatas[i]["computed_compass_angle"],
                )

                cropped_image = crop_image_based_on_relative_bearing(
                    image_filepath, image_metadatas[i], min_bearing, max_bearing
                )
                cropped_filepath = os.path.join(
                    args.building_dir,
                    args.building_name + "_Cropped" + str(i + 1) + ".jpg",
                )
                cropped_image.save(cropped_filepath)

    else:
        print("No suitable image found.")
