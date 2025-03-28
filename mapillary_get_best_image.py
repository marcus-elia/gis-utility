import argparse
import json
import os
import requests
from shapely import from_geojson, Polygon

from mapillary_nearest_images import image_metadata_name

API_KEY = "MLY|9579478658738838|77aac5cb29c86a35823e17be7aee23ac"
API_BASE_URL = "https://a.mapillary.com/v3/images/"

# Any image further than this from the building is not useful (meters)
MAX_ALLOWED_DISTANCE = 300


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

    polygon = from_geojson(geojson_data["geometry"])

    if not isinstance(polygon, Polygon):
        raise ValueError("The GeoJSON does not contain a valid polygon.")

    return polygon


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
    return 1 - 1 / (1 + 5 * angle + distance)


def sort_images(image_metadatas):
    return sorted(image_metadatas, key=lambda item: score_image_relevance(item))


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

    else:
        print("No suitable image found.")
