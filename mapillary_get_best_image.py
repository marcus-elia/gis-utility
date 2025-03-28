import argparse
import json
import math
import os
import requests
from geopy.distance import geodesic

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


def parse_lat_lon(lat_lon_str):
    """Parse latitude and longitude from the input string."""
    try:
        lat, lon = map(float, lat_lon_str.split(","))
        return lat, lon
    except ValueError:
        raise argparse.ArgumentTypeError(
            "Invalid format for latitude/longitude. Use 'lat,lon'."
        )


# def bearing(lat1, lon1, lat2, lon2):
#     """Calculate the bearing from (lat1, lon1) to (lat2, lon2)."""
#     delta_lon = math.radians(lon2 - lon1)
#     lat1, lat2 = math.radians(lat1), math.radians(lat2)

#     x = math.sin(delta_lon) * math.cos(lat2)
#     y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(
#         delta_lon
#     )
#     initial_bearing = math.atan2(x, y)
#     return (math.degrees(initial_bearing) + 360) % 360


# def is_within_fov(target_bearing, image_bearing, horizontal_fov):
#     """Check if the target bearing falls within the image's horizontal field of view."""
#     half_fov = horizontal_fov / 2
#     min_bearing = (image_bearing - half_fov) % 360
#     max_bearing = (image_bearing + half_fov) % 360

#     if min_bearing < max_bearing:
#         return min_bearing <= target_bearing <= max_bearing
#     else:
#         return target_bearing >= min_bearing or target_bearing <= max_bearing


def get_image_metadatas(geojson_file):
    with open(geojson_file, "r") as file:
        data = json.load(file)
    return [feature["properties"] for feature in data["features"]]


# def find_best_images(target_point, num_images, geojson_file):
#     """Find the best image that is facing the target point."""
#     with open(geojson_file, "r") as file:
#         data = json.load(file)

#     images = []

#     for feature in data["features"]:
#         props = feature["properties"]
#         coords = feature["geometry"]["coordinates"]
#         image_lat, image_lon = coords[1], coords[0]
#         if not "computed_compass_angle" in props:
#             continue
#         compass_angle = props["computed_compass_angle"]
#         horizontal_fov = props["horizontal_fov"]

#         # Calculate distance and bearing to target point
#         distance_to_target = geodesic((image_lat, image_lon), target_point).meters
#         target_bearing = bearing(image_lat, image_lon, *target_point)

#         # Check if target is within the image's field of view and close enough
#         if distance_to_target < MAX_ALLOWED_DISTANCE and is_within_fov(
#             target_bearing, compass_angle, horizontal_fov
#         ):
#             images.append(
#                 {
#                     "image_id": props["image_id"],
#                     "latitude": image_lat,
#                     "longitude": image_lon,
#                     "distance_to_target": distance_to_target,
#                     "bearing_to_target": target_bearing,
#                     "compass_angle": compass_angle,
#                     "horizontal_fov": horizontal_fov,
#                     "image_url": props["image_url"],
#                 }
#             )

#     return images if len(images) <= num_images else images[:num_images]


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
    # image_metadatas = find_best_images(
    #     args.target, args.num_images, image_point_geojson_path
    # )
    image_metadatas = get_image_metadatas(image_point_geojson_path)
    if image_metadatas:
        for i in range(min(len(image_metadatas), args.num_images)):
            print("Image #%d:" % (i + 1))
            print(json.dumps(image_metadatas[i], indent=4))

            image_filepath = os.path.join(
                args.building_dir, args.building_name + str(i + 1) + ".jpg"
            )
            download_image(image_metadatas[i]["image_id"], image_filepath)
            print("Image downloaded to %s." % (image_filepath))

    else:
        print("No suitable image found.")
