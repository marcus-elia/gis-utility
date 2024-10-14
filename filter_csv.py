#!/usr/bin/env python3

import argparse
import pandas as pd

def main():
    parser = argparse.ArgumentParser(description="Drop all rows from a CSV that don't have the given column value.")
    parser.add_argument("-i", "--input-csv-path", required=True, help="Path to input CSV file")
    parser.add_argument("-k", "--key", required=True, help="Key (column name) that we are filtering on.")
    parser.add_argument("-v", "--value", required=True, help="Desired value that we are filtering on.")
    parser.add_argument("-o", "--output-csv-path", required=True, help="Path to output csv file.")

    args = parser.parse_args()

    df = pd.read_csv(args.input_csv_path, encoding = "ISO-8859-1")
    df = df[df[args.key] == args.value]
    df.to_csv(args.output_csv_path)

if __name__ == "__main__":
    main()
