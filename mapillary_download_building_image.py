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
        "--num-images-to-download",
        type=int,
        default=4,
        help="Max number of images to download",
    )
    parser.add_argument(
        "-b",
        "--building-name",
        type=str,
        help="Name to identify building that will be used as filename prefix",
    )
    parser.add_argument(
        "-o", "--output-dir", type=str, required=True, help="Output directory"
    )
    args = parser.parse_args()

    building_dir = os.path.join(args.output_dir, args.building_name)

    # Run the script to create a GeoJSON containing all nearby image points with the necessary metadata.
    print("Executing `mapillary_nearest_images.py`.")
    p = subprocess.Popen(
        [
            "python3",
            "mapillary_nearest_images.py",
            "--latlon",
            args.latlon,
            "-r",
            str(args.search_radius_meters),
            "-t",
            str(args.sleep_time),
            "-o",
            building_dir,
        ]
    )
    p.communicate()

    # Run the script to get the best image from the GeoJSON that was just generated.
    print("Executing `mapillary_get_best_image.py`.")
    p = subprocess.Popen(
        [
            "python3",
            "mapillary_get_best_image.py",
            "--target",
            args.latlon,
            "--num-images",
            str(args.num_images_to_download),
            "-b",
            args.building_name,
            "-o",
            building_dir,
        ]
    )
    p.communicate()


if __name__ == "__main__":
    main()
