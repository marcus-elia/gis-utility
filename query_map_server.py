import argparse
import requests
import json
import time

# Configurable variables
OUTPUT_FILE = "output.geojson"
FIELDS = "*"  # Fields to retrieve, '*' for all fields
FORMAT = "geojson"  # Response format

# Helper function to build query
def build_query(minX, minY, maxX, maxY):
    return {
        "where": "1=1",  # Get all features in this geometry
        "geometry": f"{minX},{minY},{maxX},{maxY}",
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": FIELDS,
        "f": FORMAT
    }

# Save GeoJSON data to a file
def save_geojson(data, file_name):
    with open(file_name, "w") as f:
        json.dump(data, f)

# Main function to query the server
def query_all_data(base_url, output_geojson_filepath, minX, minY, maxX, maxY, wait_time, grid_size):
    features = []

    num_total = ((maxX - minX) // grid_size) * ((maxY - minY) // grid_size)
    num_complete = 0
    # Iterate over the bounding box in a grid pattern
    x = minX
    while x < maxX:
        y = minY
        while y < maxY:
            # Define the small grid's corners
            x_max = min(x + grid_size, maxX)
            y_max = min(y + grid_size, maxY)
            
            # Build and execute the query
            query = build_query(x, y, x_max, y_max)
            response = requests.get(base_url, params=query)
            
            if response.status_code == 200:
                data = response.json()
                if "features" in data:
                    features.extend(data["features"])
                    print(f"Retrieved {len(data['features'])} features from ({x}, {y}) to ({x_max}, {y_max})")
            else:
                print(f"Error: {response.status_code} for query at ({x}, {y})")
            
            # Move to next grid and pause
            y += grid_size
            num_complete += 1
            print("%d / %d complete." % (num_complete, num_total))
            time.sleep(wait_time)
        x += grid_size
    
    # Save the results as GeoJSON
    geojson_output = {
        "type": "FeatureCollection",
        "features": features
    }
    save_geojson(geojson_output, output_geojson_filepath)
    print(f"Saved {len(features)} features to {output_geojson_filepath}")

def main():
    parser = argparse.ArgumentParser(description="Query data from a MapServer.")
    parser.add_argument("-X", "--min-x", required=True, type=float, help="West border of query region")
    parser.add_argument("-Y", "--min-y", required=True, type=float, help="South border of query region")
    parser.add_argument("-U", "--max-x", required=True, type=float, help="East border of query region")
    parser.add_argument("-V", "--max-y", required=True, type=float, help="North border of query region")
    parser.add_argument("--base-url", required=True, help="MapServer url (ending with /MapServer/<number>/query)")
    parser.add_argument("--wait-time", type=float, required=True, help="Seconds between queries")
    parser.add_argument("--grid-size", required=False, type=float, help="Grid size (defaults to degrees)")
    parser.add_argument("--output-geojson-filepath", required=True, help="Output geojson filepath")

    args = parser.parse_args()

    query_all_data(args.base_url, args.output_geojson_filepath, args.min_x, args.min_y, args.max_x, args.max_y, args.wait_time, args.grid_size if args.grid_size else 0.001)

if __name__ == "__main__":
    main()
