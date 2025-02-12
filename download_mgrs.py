"""
Some websites have data files stored in Military Grid Reference System tiles.
Each tile's filename is directly based on the coordinates.
For example, 18TVN005145.las is a tile's filename, indicating UTM zone 18T, and VN
specifying which 100km x 100km square it is located in. The 005 and 145 are the x and
y coordinates of the 1km x 1km tile that the data is for.
18TVN005160 is directly north and 18TVN020145 is directly east. The pattern is that
x and y both increase by 15.
"""

import argparse
import os
import requests
import time

from general_utility import get_time_estimate_string

def next_letter(letter):
    """
    UTM/MGRS skip I and O.
    """
    val = ord(letter) + 1
    if val == 73 or val == 79 or val == 105 or val == 111:
        val += 1
    return chr(val)

def starting_square_identifier_x(utm_zone):
    if utm_zone % 3 == 1:
        return 'A'
    elif utm_zone % 3 == 2:
        return 'J'
    else:
        return 'S'

def ending_square_identifier_x(utm_zone):
    if utm_zone % 3 == 1:
        return 'H'
    elif utm_zone % 3 == 2:
        return 'R'
    else:
        return 'Z'

def starting_square_identifier_y(utm_zone):
    if utm_zone % 2 == 0:
        return 'F'
    else:
        return 'A'

def ending_square_identifier_y(utm_zone):
    if utm_zone % 2 == 0:
        return 'P'
    else:
        return 'J'

class MGRSTile():
    def __init__(self, utm_zone, utm_letter, square_identifier_x, square_identifier_y, x, y, num_digits):
        self.utm_zone = utm_zone
        self.utm_letter = utm_letter
        self.square_identifier_x = square_identifier_x
        self.square_identifier_y = square_identifier_y
        self.x = x
        self.y = y
        self.num_digits = num_digits

    def string(self, capitalize=True):
        s = str(self.utm_zone)
        s += (self.utm_letter.upper() if capitalize else self.utm_letter.lower())
        s += (self.square_identifier_x.upper() if capitalize else self.square_identifier_x.lower())
        s += (self.square_identifier_y.upper() if capitalize else self.square_identifier_y.lower())
        s += str(self.x).zfill(self.num_digits) 
        s += str(self.y).zfill(self.num_digits)
        return s

    def copy(self):
        return MGRSTile(self.utm_zone, self.utm_letter, self.square_identifier_x, self.square_identifier_y, self.x, self.y, self.num_digits)

    def __eq__(self, other):
        return self.string() == other.string()

    def next_tile_east(self, delta):
        new_x = self.x + delta
        if new_x >= 10 ** self.num_digits:
            new_x -= 10 ** self.num_digits
            if ending_square_identifier_x(self.utm_zone) == self.square_identifier_x.upper():
                new_utm_zone = self.utm_zone + 1 if self.utm_zone < 60 else 1
                new_square_identifier_x = starting_square_identifier_x(new_utm_zone)
            else:
                new_utm_zone = self.utm_zone
                new_square_identifier_x = next_letter(self.square_identifier_x)
            return MGRSTile(new_utm_zone, self.utm_letter, new_square_identifier_x, self.square_identifier_y, new_x, self.y, self.num_digits)
        return MGRSTile(self.utm_zone, self.utm_letter, self.square_identifier_x, self.square_identifier_y, new_x, self.y, self.num_digits)

    def next_tile_north(self, delta):
        new_y = self.y + delta
        if new_y >= 10 ** self.num_digits:
            new_y -= 10 ** self.num_digits
            if ending_square_identifier_y(self.utm_zone) == self.square_identifier_y.upper():
                new_utm_letter = next_letter(self.utm_letter)
                new_square_identifier_y = starting_square_identifier_y(self.utm_zone)
            else:
                new_utm_letter = self.utm_letter
                new_square_identifier_y = next_letter(self.square_identifier_y)
            return MGRSTile(self.utm_zone, new_utm_letter, self.square_identifier_x, new_square_identifier_y, self.x, new_y, self.num_digits)
        return MGRSTile(self.utm_zone, self.utm_letter, self.square_identifier_x, self.square_identifier_y, self.x, new_y, self.num_digits)

def tile_difference(tile1, tile2, increment):
    difference_x = 0
    while tile1.utm_zone != tile2.utm_zone or ord(tile1.square_identifier_x.upper()) < ord(tile2.square_identifier_x.upper()) or tile1.x < tile2.x:
        tile1 = tile1.next_tile_east(increment)
        difference_x += 1
    difference_y = 0
    while tile1.utm_letter != tile2.utm_letter or ord(tile1.square_identifier_y.upper()) < ord(tile2.square_identifier_y.upper()) or tile1.y < tile2.y:
        tile1 = tile1.next_tile_north(increment)
        difference_y += 1
    return (difference_x, difference_y)

def main():
    parser = argparse.ArgumentParser(description="Download multiple files from MGRS tiles.")
    parser.add_argument("--base-url", required=True, help="The base path before each filename")
    parser.add_argument("--start-utm-zone", required=True, type=int, help="The utm zone number that starts each filename")
    parser.add_argument("--start-utm-letter", required=True, help="The utm zone letter following the zone number")
    parser.add_argument("--start-square-identifier-x", required=True, help="The letter representing the x-component of the 100km square")
    parser.add_argument("--start-square-identifier-y", required=True, help="The letter representing the y-component of the 100km square")
    parser.add_argument("--start-x", required=True, type=int, help="The x-value of the bottom left tile")
    parser.add_argument("--start-y", required=True, type=int, help="The y-value of the bottom left tile")
    parser.add_argument("--end-utm-zone", required=True, type=int, help="The utm zone number that starts each filename")
    parser.add_argument("--end-utm-letter", required=True, help="The utm zone letter following the zone number")
    parser.add_argument("--end-square-identifier-x", required=True, help="The letter representing the x-component of the 100km square")
    parser.add_argument("--end-square-identifier-y", required=True, help="The letter representing the y-component of the 100km square")
    parser.add_argument("--end-x", required=True, type=int, help="The x-value of the bottom left tile")
    parser.add_argument("--end-y", required=True, type=int, help="The y-value of the bottom left tile")
    parser.add_argument("--num-digits", required=True, type=int, help="How many digits the coordinates have in each filename")
    parser.add_argument("--increment", type=int, required=True, help="How much the number changes between consecutive tiles")
    parser.add_argument("--filename-suffix", required=True, help="The constant suffix of each filename, like '.las'")
    parser.add_argument("-o", "--output-directory", required=True, help="Output directory where files are downloaded to")
    parser.add_argument("--dry-run", action='store_true', help="Don't actually run, print files that would be downloaded")
    parser.add_argument("--capitalize", action='store_true', help="Capitalize all UTM/MGRS letters")

    args = parser.parse_args()

    tile1 = MGRSTile(args.start_utm_zone, args.start_utm_letter, args.start_square_identifier_x, args.start_square_identifier_y,\
            args.start_x, args.start_y, args.num_digits)
    tile2 = MGRSTile(args.end_utm_zone, args.end_utm_letter, args.end_square_identifier_x, args.end_square_identifier_y,\
            args.end_x, args.end_y, args.num_digits)

    num_tiles_x, num_tiles_y = tile_difference(tile1, tile2, args.increment)
    num_tiles_x += 1
    num_tiles_y += 1
    num_tiles = num_tiles_x * num_tiles_y
    num_complete = 0
    start_time = time.time()
    col_start_tile = tile1.copy()
    num_failures = 0
    print("There are %d tiles in this area." % (num_tiles))
    for i in range(num_tiles_x):
        current_tile = col_start_tile.copy()
        for j in range(num_tiles_y):
            tile_name = current_tile.string(args.num_digits)
            filename = tile_name + args.filename_suffix
            full_url = args.base_url + filename
            num_complete += 1
            if args.dry_run:
                print("Would download %s." % (full_url))
            else:
                output_filepath = os.path.join(args.output_directory, filename)
                response = requests.get(full_url)
                if response.status_code == 200:
                    with open(output_filepath, 'wb') as f:
                        f.write(response.content)
                    print("Downloaded %s." % (full_url))
                else:
                    num_failures += 1
                    print("Failed to download %s." % (full_url))
                print(get_time_estimate_string(time.time() - start_time, num_complete, num_tiles))
            current_tile = current_tile.next_tile_north(args.increment)
        col_start_tile = col_start_tile.next_tile_east(args.increment)
    if num_failures != 0:
        print("%d failed to download." % (num_failures))

if __name__ == "__main__":
    main()
