#!/usr/bin/env python3

"""
Take a CSV dataset of house sales that does not have lat/lon, but does have addresses.
Use a separate geojson file of address to try to associate each house with a location.
Any houses that succeeded get written to a geojson file. Any houses that didn't get
matched are saved in a CSV file.
Optionally, pass in a json file mapping city/village names to the names of the towns
containing them. This is because datasets may be inconsistent about whether a house in
Fayetteville is in Fayetteville (the proper village) or Manlius (the surrounding town).
"""

import argparse
import csv
import geojson
import json
import time

from general_utility import standardize_string, standardize_city, get_time_estimate_string, num_rows_in_csv

class CantParseAddressError(Exception):
    pass

def string_fraction_to_value(s):
    """
    Perform division if string is a fraction.
    Return None otherwise.
    """
    split = s.split('/')
    if len(split) != 2:
        return None
    try:
        a = int(split[0])
        b = int(split[1])
        return a / b
    except ValueError:
        return None

def split_address(address):
    number_road_pieces = address.split()
    if len(number_road_pieces) < 2:
        raise CantParseAddressError("%s does not have both a number and a street." % (address))
    try:
        number = int(number_road_pieces[0])
    except ValueError:
        raise CantParseAddressError("%s does not start with a number." % (address))

    # Handle the case of "30 1/2 Main St"
    maybe_fraction_value = string_fraction_to_value(number_road_pieces[1])
    if maybe_fraction_value != None and len(number_road_pieces) > 2:
        number += maybe_fraction_value
        road = standardize_string("".join(number_road_pieces[2:]))
    else:
        road = standardize_string("".join(number_road_pieces[1:]))

    return (number, road)

def main():
    parser = argparse.ArgumentParser(description="Create a geojson file from CSV of addresses with sale info by combining with geojson file of addresses.")
    parser.add_argument("-i", "--input-csv-path", required=True, help="Path to input CSV file")
    parser.add_argument("-a", "--addresses-filepath", required=True, help="Path to geojson file containing addresses.")
    parser.add_argument("-o", "--output-geojson-path", required=True, help="Path to output geojson file.")
    parser.add_argument("-s", "--single-state", required=False, help="If you know everything is in one state.")
    parser.add_argument("-u", "--unmatched-csv-path", required=True, help="Path to output csv lines that weren't matched.")
    parser.add_argument("--state-column-name", required=False, help="Label of the state column in the CSV.")
    parser.add_argument("--city-column-name", required=True, help="Label of the municipality column in the CSV.")
    parser.add_argument("--address-column-name", required=True, help="Label of the address column in the CSV.")
    parser.add_argument("--price-column-name", required=True, help="Label of the sale price column in the CSV.")
    parser.add_argument("--date-column-name", required=True, help="Label of the sale date column in the CSV.")
    parser.add_argument("--school-column-name", required=True, help="Label of the school district column in the CSV.")
    parser.add_argument("--containing-towns-json", required=False, help="Path to json file mapping cities/villages to their containing towns.")
    parser.add_argument("--max-price", required=False, help="Ignore outlier sales.")

    args = parser.parse_args()

    containing_towns = {}
    if args.containing_towns_json:
        f = open(args.containing_towns_json, 'r', encoding="utf8")
        containing_towns = json.loads(f.read())
        f.close()

    # Load all of the address points
    print("Loading file of address points.")
    start_time = time.time()
    f = open(args.addresses_filepath, 'r', encoding="utf8")
    geojson_contents = geojson.loads(f.read())
    f.close()
    print("Loaded address points in %f seconds." % (time.time() - start_time))

    # Store the address points by [state][city][street][number]
    print("Storing address points in dictionary.")
    num_completed = 0
    start_time = time.time()
    num_points = len(geojson_contents['features'])
    address_points = {}
    for geojson_feature in geojson_contents['features']:
        # Extract the state, city, number, and address from the tags.
        props = geojson_feature.properties
        if args.single_state:
            state = standardize_string(args.single_state)
        elif not args.state_column_name in props or not props[args.state_column_name]:
            continue
        else:
            state = standardize_string(props[args.state_column_name])
        if not args.city_column_name in props or not props[args.city_column_name]:
            continue
        city = standardize_string(props[args.city_column_name])
        if not args.address_column_name in props or not props[args.address_column_name]:
            continue
        address = props[args.address_column_name]
        try:
            number, street = split_address(address)
        except CantParseAddressError:
            continue

        # Insert the coords into the dictionary.
        latlon_point = (geojson_feature.geometry["coordinates"][1], geojson_feature.geometry["coordinates"][0])
        try:
            address_points[state][city][street][number] = latlon_point
        except KeyError:
            try:
                address_points[state][city][street] = {number : latlon_point}
            except KeyError:
                try:
                    address_points[state][city] = {street : {number : latlon_point}}
                except KeyError:
                    address_points[state] = {city : {street : {number : latlon_point}}}
        # Log the status
        num_completed += 1
        time_elapsed = int(time.time() - start_time)
        print(get_time_estimate_string(time_elapsed, num_completed, num_points), end='\r')
    print()

    del(geojson_contents)

    # Iterate over the CSV house sale rows and try to match them with address points.
    unmatched_csv_rows = []
    geojson_features = []
    num_houses = num_rows_in_csv(args.input_csv_path)
    fieldnames = []
    with open(args.input_csv_path, 'r', encoding="utf8") as csvfile:
        print("Finding addresses for CSV rows.")
        num_completed = 0
        start_time = time.time()
        csv_reader = csv.DictReader(csvfile)
        for row in csv_reader:
            if not fieldnames:
                fieldnames = list(row.keys())
            if args.max_price and int(row[args.price_column_name]) > int(args.max_price):
                continue
            state = standardize_string(args.single_state) if args.single_state else standardize_string(row[args.state_column_name])
            city = standardize_city(row[args.city_column_name])
            try:
                number, road = split_address(row[args.address_column_name])
                found = False
                try:
                    lat, lon = address_points[state][city][road][number]
                    found = True
                except KeyError:
                    if city in containing_towns:
                        try:
                            lat, lon = address_points[state][containing_towns[city]][road][number]
                            found = True
                        except KeyError:
                            pass
                if found:
                    geojson_point = geojson.Point([lon, lat])
                    props = {\
                            args.city_column_name : row[args.city_column_name],\
                            args.address_column_name : row[args.address_column_name],\
                            args.price_column_name : int(row[args.price_column_name]),\
                            args.date_column_name : row[args.date_column_name],\
                            args.school_column_name : row[args.school_column_name]\
                            }
                    feature = geojson.Feature(geometry=geojson_point, properties=props)
                    geojson_features.append(feature)
                else:
                    unmatched_csv_rows.append(row)

            except CantParseAddressError:
                unmatched_csv_rows.append(row)
            # Log the status
            num_completed += 1
            time_elapsed = int(time.time() - start_time)
            print(get_time_estimate_string(time_elapsed, num_completed, num_houses), end='\r')
        print()

    print("Found addresses for %d houses." % (len(geojson_features)))
    dump = geojson.dumps(geojson.FeatureCollection(features=geojson_features))
    f = open(args.output_geojson_path, 'w')
    f.write(dump)
    f.close()

    print("Did not find addresses for %d houses." % (len(unmatched_csv_rows)))
    with open(args.unmatched_csv_path, 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        for row in unmatched_csv_rows:
            try:
                writer.writerow(row)
            except UnicodeEncodeError:
                pass

if __name__ == "__main__":
    main()
