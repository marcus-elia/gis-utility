import argparse
import os
import subprocess

from mapillary_nearest_images import image_metadata_name


def main():
    parser = argparse.ArgumentParser(
        description="Download a Mapillary image that contains a given building."
    )
    parser.add_argument(
        "--latlon",
        type=str,
        required=True,
        help="Lat,lon of the center of the building",
    )
    parser.add_argument(
        "-n",
        "--num-images",
        type=int,
        default=30,
        help="Number of closest images to fetch",
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
        "--downloaded-image-filename",
        type=str,
        help="Name for downloaded image that gets chosen.",
    )
    parser.add_argument(
        "-o", "--output-dir", type=str, required=True, help="Output directory"
    )
    args = parser.parse_args()

    # Run the script to create a GeoJSON containing all nearby image points with the necessary metadata.
    print("Executing `mapillary_nearest_images.py`.")
    p = subprocess.Popen(
        [
            "python3",
            "mapillary_nearest_images.py",
            "--latlon",
            args.latlon,
            "-n",
            str(args.num_images),
            "-r",
            str(args.search_radius_meters),
            "-t",
            str(args.sleep_time),
            "-o",
            args.output_dir,
        ]
    )
    p.communicate()

    geojson_path = os.path.join(args.output_dir, image_metadata_name)
    image_path = os.path.join(args.output_dir, args.downloaded_image_filename)

    # Run the script to get the best image from the GeoJSON that was just generated.
    print("Executing `mapillary_get_best_image.py`.")
    p = subprocess.Popen(
        [
            "python3",
            "mapillary_get_best_image.py",
            "--target",
            args.latlon,
            "--geojson-path",
            geojson_path,
            "--downloaded-image-filepath",
            image_path,
        ]
    )
    p.communicate()

    print("Image downloaded to %s." % (image_path))


if __name__ == "__main__":
    main()
