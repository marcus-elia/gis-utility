import argparse
import geojson
import json
import math
import mercantile
import os
import requests
import time
from geopy.distance import geodesic
from pyproj import Transformer
from vt2geojson.tools import vt_bytes_to_geojson

# Configuration
access_token = "MLY|9579478658738838|77aac5cb29c86a35823e17be7aee23ac"  # Replace with your Mapillary access token
tile_layer = "image"
tile_endpoint = "mly1_public"
tile_zoom_level = 14
image_points_name = "mapillary_image_points.geojson"
image_metadata_name = "mapillary_images_with_metadata.geojson"

transformer_to_web_mercator = Transformer.from_crs(
    "EPSG:4326", "EPSG:3857", always_xy=True
)
transformer_to_latlon = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)


def calculate_fov(normalized_focal_length, image_width, image_height):
    """
    Calculate horizontal and vertical FOVs assuming the focal length is normalized by image width.

    Args:
        focal_length (normalized).
        image_width (int): Image width in pixels.
        image_height (int): Image height in pixels.

    Returns:
        tuple: (horizontal_fov, vertical_fov) in degrees.
    """
    # Calculate focal length in pixels (denormalizing it)
    focal_length_pixels = normalized_focal_length * image_width

    # Horizontal and vertical FOV calculations (in degrees)
    horizontal_fov = (
        2 * math.atan(image_width / (2 * focal_length_pixels)) * (180 / math.pi)
    )
    vertical_fov = (
        2 * math.atan(image_height / (2 * focal_length_pixels)) * (180 / math.pi)
    )

    return horizontal_fov, vertical_fov


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


# Create bounding box of radius r meters around (lat, lon)
def create_bounding_box(lat, lon, r):
    x, y = transformer_to_web_mercator.transform(lon, lat)
    x_min, y_min = x - r, y - r
    x_max, y_max = x + r, y + r
    lon_min, lat_min = transformer_to_latlon.transform(x_min, y_min)
    lon_max, lat_max = transformer_to_latlon.transform(x_max, y_max)
    return lon_min, lat_min, lon_max, lat_max


# Step 1: Fetch image IDs around the point and save to GeoJSON
def fetch_image_points(lat, lon, zoom, n, search_radius_meters, output_file):
    lon_min, lat_min, lon_max, lat_max = create_bounding_box(
        lat, lon, search_radius_meters
    )
    tiles = list(mercantile.tiles(lon_min, lat_min, lon_max, lat_max, zoom))
    output = {"type": "FeatureCollection", "features": []}

    for tile in tiles:
        tile_url = f"https://tiles.mapillary.com/maps/vtp/{tile_endpoint}/2/{tile.z}/{tile.x}/{tile.y}?access_token={access_token}"
        response = requests.get(tile_url)
        tile_data = vt_bytes_to_geojson(
            response.content, tile.x, tile.y, tile.z, layer=tile_layer
        )

        for feature in tile_data["features"]:
            properties = feature.get("properties", {})
            image_id = properties.get("id")
            compass_angle = properties.get("compass_angle")
            is_pano = properties.get("is_pano")

            if image_id and lon and lat:
                distance = math.sqrt(
                    (lon - feature["geometry"]["coordinates"][0]) ** 2
                    + (lat - feature["geometry"]["coordinates"][1]) ** 2
                )
                output["features"].append(
                    {
                        "type": "Feature",
                        "geometry": feature["geometry"],
                        "properties": {
                            "image_id": image_id,
                            "compass_angle": compass_angle,
                            "is_pano": is_pano,
                            "captured_at": properties.get("captured_at"),
                            "distance": distance,
                        },
                    }
                )

    # Sort by distance and keep only the n closest points
    output["features"].sort(key=lambda x: x["properties"]["distance"])
    output["features"] = output["features"][:n]

    # Save filtered points to GeoJSON
    with open(output_file, "w") as f:
        json.dump(output, f)
    print(f"Saved {len(output['features'])} closest image points to {output_file}")


# Step 2: Fetch metadata (like FOV and elevation) using the Graph API and update the GeoJSON
# Also filter down to the desired number of metadatas by selecting only images containing the
# building in their FOVs.
def fetch_image_metadata(
    target_lat, target_lon, input_file, num_metadatas, output_file, sleep_time
):
    with open(input_file, "r") as f:
        geojson_data = json.load(f)
    print(
        "Making %d requests to get metadata for %d images."
        % (len(geojson_data["features"]), len(geojson_data["features"]))
    )

    num_complete = 0

    # Sort by distance from target
    geojson_data["features"].sort(
        key=lambda item: geodesic(
            (target_lat, target_lon),
            (item["geometry"]["coordinates"][1], item["geometry"]["coordinates"][0]),
        ).meters
    )

    # Iterate over the images and calculate metadata for the first n that are pointed at the building.
    features_with_metadata = []
    for feature in geojson_data["features"]:
        image_id = feature["properties"]["image_id"]
        metadata_url = f"https://graph.mapillary.com/{image_id}?fields=id,altitude,camera_parameters,width,height,compass_angle,computed_altitude,computed_compass_angle,geometry&access_token={access_token}"
        response = requests.get(metadata_url)
        metadata = response.json()

        # Extract metadata
        altitude = metadata.get("altitude")
        computed_altitude = metadata.get("computed_altitude")
        compass_angle = metadata.get("compass_angle")
        computed_compass_angle = metadata.get("computed_compass_angle")
        camera_parameters = metadata.get("camera_parameters")
        distance = (
            geodesic(
                (target_lat, target_lon),
                (
                    feature["geometry"]["coordinates"][1],
                    feature["geometry"]["coordinates"][0],
                ),
            ).km
            * 1000
        )

        width = metadata.get("width")
        height = metadata.get("height")
        focal_length = (
            camera_parameters[0]
            if camera_parameters and len(camera_parameters) > 0
            else None
        )

        # if compass_angle == computed_compass_angle:
        #    # If the reported angle wasn't corrected, it is likely incorrect
        #    continue

        # Compute FOV
        if focal_length == None or width == None or height == None:
            # If we can't determine the FOV, we can't use this image.
            continue
        horizontal_fov, vertical_fov = calculate_fov(focal_length, width, height)

        # Check if the building is within the image's FOV
        target_bearing = bearing(
            feature["geometry"]["coordinates"][1],
            feature["geometry"]["coordinates"][0],
            target_lat,
            target_lon,
        )

        # Check if target is within the image's field of view and close enough
        if is_within_fov(target_bearing, compass_angle, horizontal_fov):
            properties = {
                "altitude": altitude,
                "angle_delta": abs(target_bearing - computed_compass_angle),
                "computed_altitude": computed_altitude,
                "compass_angle": compass_angle,
                "computed_compass_angle": computed_compass_angle,
                "distance_from_target": distance,
                "focal_length": focal_length,
                "image_id": image_id,
                "image_width": width,
                "image_height": height,
                "horizontal_fov": horizontal_fov,
                "vertical_fov": vertical_fov,
                "image_url": f"https://www.mapillary.com/app/?pKey={image_id}",
            }
            feature_with_metadata = geojson.Feature(
                geometry=feature["geometry"], properties=properties
            )
            features_with_metadata.append(feature_with_metadata)
            if len(features_with_metadata) == num_metadatas:
                break

        time.sleep(sleep_time)
        num_complete += 1
        print(
            "Checked %d/%d images. Kept %d/%d so far."
            % (
                num_complete,
                len(geojson_data["features"]),
                len(features_with_metadata),
                num_metadatas,
            ),
            end="\r",
        )

    # Save the updated GeoJSON with metadata
    with open(output_file, "w") as f:
        json.dump(geojson.FeatureCollection(features=features_with_metadata), f)
    print(f"\nSaved image metadata to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Mapillary image data and metadata near a point."
    )
    parser.add_argument(
        "--latlon",
        type=str,
        required=True,
        help="Lat,lon of the center point",
    )
    parser.add_argument(
        "--num-candidates",
        type=int,
        default=100,
        help="Get the ids of this many images",
    )
    parser.add_argument(
        "--num-metadatas",
        type=int,
        default=30,
        help="Get the metadata for this many images",
    )
    parser.add_argument(
        "-r",
        "--search-radius-meters",
        type=float,
        default=200,
        help="Radius to search for nearby images",
    )
    parser.add_argument(
        "-t",
        "--sleep-time",
        type=float,
        default=0,
        help="Time to wait between each image metadata request",
    )
    parser.add_argument(
        "-o", "--output-dir", type=str, required=True, help="Output directory"
    )
    args = parser.parse_args()
    lat, lon = (float(x.strip()) for x in args.latlon.split(","))

    os.makedirs(args.output_dir, exist_ok=True)
    points_file = os.path.join(args.output_dir, image_points_name)
    metadata_file = os.path.join(args.output_dir, image_metadata_name)

    # Step 1: Fetch and filter image points around the given lat/lon
    fetch_image_points(
        lat,
        lon,
        tile_zoom_level,
        args.num_candidates,
        args.search_radius_meters,
        points_file,
    )

    # Step 2: Fetch detailed metadata and update the GeoJSON
    fetch_image_metadata(
        lat, lon, points_file, args.num_metadatas, metadata_file, args.sleep_time
    )


if __name__ == "__main__":
    main()
