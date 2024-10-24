#!/usr/bin/env python3

"""
This is intended to do some analysis of a dataset of tax parcels.
Give the parameters you want a house to have and it will print
some stats about how many there are.
"""

import argparse
import contextily as cx
from enum import Enum
import geopandas
import json
from matplotlib import colormaps
import shapely
import time

from general_utility import parse_latlon_string, standardize_county, latlon_to_crs
from tax_parcel_loader import TaxParcelLoader, AttributeFilter

MAX_LOADING_WIDTH_METERS = 60000

class AttributeType(Enum):
    Quantitative = 1
    Qualitative = 2

def main():
    attribute_keys_string = "'year_built', 'school_district', 'acres', 'zip', 'county', 'city', 'property_type', 'market_value', 'building_style', water_description', etc"
    parser = argparse.ArgumentParser(description="Print stats about tax parcel nodes.")
    parcel_source_group = parser.add_mutually_exclusive_group(required=True)
    parcel_source_group.add_argument("-i", "--input-filepath", help="Path to input GIS file of tax parcels if loading from single file.")
    parcel_source_group.add_argument("-d", "--state-dir", help="Path to directory containing a subdir for each county.")
    parser.add_argument("-k", "--parcel-keys-and-values-filename", required=True, help="Name only of JSON file mapping generic key/value names to file-specific names. This filename can appear both in the state dir and the individual county dirs.")
    parser.add_argument("-t", "--parcel-keys-types-filepath", required=True, help="Path to JSON file mapping generic key/value names to types.")
    parser.add_argument("--already-sfh", action='store_true', help="If the dataset only contains single-family-homes, no need to filter.")
    parser.add_argument("--min-year-built", required=False, type=int, help="Oldest year you want a house to be built in.")
    parser.add_argument("--max-year-built", required=False, type=int, help="Newest year you want a house to be built in.")
    parser.add_argument("--min-sqft", required=False, type=int, help="Minimum square footage you want a house to have.")
    parser.add_argument("--max-sqft", required=False, type=int, help="Maximum square footage you want a house to have.")
    parser.add_argument("--min-acres", required=False, type=float, help="Minimum number of acres you want a house to have.")
    parser.add_argument("--max-acres", required=False, type=float, help="Maximum number of acres you want a house to have.")
    parser.add_argument("--require-connected-water", action='store_true', help="If you want the house to have public water.")
    parser.add_argument("--require-connected-sewer", action='store_true', help="If you want the house to have public sewer.")
    parser.add_argument("--school-district", required=False, help="Desired school district.")
    parser.add_argument("--city", required=False, help="Desired city.")
    parser.add_argument("--municipality", required=False, help="Desired municipality.")
    parser.add_argument("--zip-code", required=False, help="Desired zip code.")
    parser.add_argument("--min-beds", required=False, type=int, help="Minimum number of bedrooms you want a house to have.")
    parser.add_argument("--min-baths", required=False, type=float, help="Minimum number of bathrooms you want a house to have.")
    parser.add_argument("--output-filepath", required=False, help="Save filtered dataframe to filepath.")
    parser.add_argument("--folium-filepath", required=False, help="Save interactive Folium map to HTML file.")
    parser.add_argument("--plot-key", required=False, help="The feature that colors the plot, if any. (%s)" % (attribute_keys_string))
    parser.add_argument("--plot-filtered-filepath", required=False, help="Plot the remaining points after filtering, save to image path.")
    parser.add_argument("--convert-to-centroid", action='store_true', help="If the geometry is polygons, replace with each parcel's centroid.")
    parser.add_argument("--outlier-percentile", required=False, type=float, help="Remove outliers for the column used as the plot coloring variable. E.g. 0.05 removes <5th percentile and >95th percentile.")
    parser.add_argument("--center-latlon", required=False, help="The lat,lon center of the desired region.")
    parser.add_argument("--radius-meters", required=False, type=float, help="The radius, if the desired region is circular.")
    parser.add_argument("--width-meters", required=False, type=float, help="The width, if the desired region is rectangular.")
    parser.add_argument("--height-meters", required=False, type=float, help="The height, if the desired region is rectangular.")
    parser.add_argument("--county", required=False, help="Restrict results to a particular county.")
    parser.add_argument("--colormap", required=False, help="Colormap for the plots. Defaults 'plamsa' for quantitative, 'tab20' for qualitative. Also recommend 'viridis' and 'seismic' and 'bwr'.")
    parser.add_argument("--markersize", required=False, type=int, help="Markersize for the plots. Defaults to 15.")
    parser.add_argument("--figsize", required=False, type=int, help="Figure size for the plots. Defaults to 10.")
    parser.add_argument("--tile-source", required=False, default='OpenStreetMap.Mapnik', help="Tile source for Folium. Defaults to 'OpenStreetMap.Mapnik'. Some others are 'Esri.WorldImagery', 'Esri.WorldStreetMap', 'CartoDB.Positron', 'CartoDB.Voyager', 'USGS.USImagery', 'TopPlusOpen.Grey', 'Stadia.AlidadeSmooth")
    parser.add_argument("--max-folium-points", required=False, default=40000, help="Max number of points for interactive folium map. Defaults to 40k.")

    args = parser.parse_args()
    start_time = time.time()

    # ==================================================================
    #
    #                    Load JSON Data About Keys
    #
    # ==================================================================
    f = open(args.parcel_keys_types_filepath, 'r')
    general_name_to_type = json.loads(f.read())
    f.close()
    for name in general_name_to_type:
        if general_name_to_type[name] in ('int', 'float'):
            general_name_to_type[name] = AttributeType.Quantitative
        else:
            general_name_to_type[name] = AttributeType.Qualitative

    # ==================================================================
    #
    #                          Verify Args
    #
    # ==================================================================
    if args.plot_key and (not args.plot_filtered_filepath and not args.folium_filepath):
        raise ValueError("plot-key is present but no plots are being saved.")
    if args.center_latlon and (not args.radius_meters and not args.width_meters):
        raise ValueError("Must specify a radius or a width when center is specified.")
    if args.radius_meters and (args.width_meters or args.height_meters):
        raise ValueError("Cannot specify both a circular and a rectangular region.")
    if not args.center_latlon and (args.radius_meters or args.width_meters or args.height_meters):
        raise ValueError("Must specify a center lat/lon to restrict to a circle or rectangle.")
    if args.state_dir and (not args.center_latlon or (not args.radius_meters and not args.width_meters)):
        raise ValueError("Must specify a center lat/lon and a radius or width when loading from the county parent directory.")
    if args.colormap and (not args.plot_filtered_filepath and not args.folium_filepath):
        raise ValueError("Colormap is present but no plots are being saved.")
    if args.radius_meters and 2*args.radius_meters > MAX_LOADING_WIDTH_METERS:
        raise ValueError("Requested radius (%d meters) is greater than max allowed radius (%d meters)." % (args.radius_meters, MAX_LOADING_WIDTH_METERS/2))
    if args.width_meters and args.width_meters > MAX_LOADING_WIDTH_METERS:
        raise ValueError("Requested width (%d meters) is greater than max allowed width (%d meters)." % (args.width_meters, MAX_LOADING_WIDTH_METERS))
    if args.height_meters and args.height_meters > MAX_LOADING_WIDTH_METERS:
        raise ValueError("Requested height (%d meters) is greater than max allowed height (%d meters)." % (args.height_meters, MAX_LOADING_HEIGHT_METERS))

    plot_attribute_type = general_name_to_type[args.plot_key] if args.plot_key else None
    if args.colormap:
        if not args.colormap in list(colormaps):
            raise ValueError("The specified colormap (%s) is not in the list of options: " % (args.colormap) + list(colormaps))
        else:
            colormap = args.colormap
    else:
        if plot_attribute_type == AttributeType.Quantitative:
            colormap = 'plasma'
        else:
            colormap = 'tab20'

    if args.markersize:
        if args.markersize <= 0:
            raise ValueError("Markersize must be positive, not %d." % (args.markersize))
        else:
            ms = args.markersize
    else:
        ms = 15

    if args.figsize:
        if args.figsize <= 0:
            raise ValueError("Figure size must be positive, not %d." % (args.figsize))
        else:
            fs = args.figsize
    else:
        fs = 10

    # ==================================================================
    #
    #             Convert center point from degrees to meters
    #
    # ==================================================================
    if args.center_latlon:
        lat, lon = parse_latlon_string(args.center_latlon)
        center_x, center_y = latlon_to_crs(lat, lon, 3857)

    # ==================================================================
    #
    #                          Load the data
    #
    # ==================================================================
    if args.center_latlon:
        if args.radius_meters:
            width = 2 * args.radius_meters
            height = width
        elif args.height_meters:
            width = args.width_meters
            height = args.height_meters
        else:
            width = args.width_meters
            height = width

    if args.input_filepath:
        print("Loading %s." % (args.input_filepath))
        if args.center_latlon:    
            bbox = geopandas.GeoSeries([\
                        shapely.Point(center_x - width/2, center_y - height/2),\
                        shapely.Point(center_x + width/2, center_y + height/2)\
                        ], crs="EPSG:3857")
            gdf = geopandas.read_file(args.input_filepath, bbox=bbox, engine='fiona')
        else:
            # For a single file, it is allowed to load the entire file with no bbox.
            gdf = geopandas.read_file(args.input_filepath)
    else:
        print("Loading parcels from county files contained in %s." % (args.state_dir))
        attribute_filter = AttributeFilter(args.already_sfh, args.require_connected_water, args.require_connected_sewer, args.min_year_built, args.max_year_built, args.min_sqft, args.max_sqft, args.min_acres, args.max_acres, args.min_beds, args.min_baths, args.county, args.school_district, args.city, args.municipality, args.zip_code)
        loader = TaxParcelLoader(args.state_dir, args.parcel_keys_and_values_filename)
        lat, lon = parse_latlon_string(args.center_latlon)
        gdf = loader.load_parcels((lat, lon), width, height, attribute_filter)
    num_parcels = len(gdf)
    print("There are %d total parcels within the bounding box." % (num_parcels))

    # ==================================================================
    #
    #                    Use the data's centroids
    #
    # ==================================================================
    if args.convert_to_centroid:
        gdf['geometry'] = gdf['geometry'].centroid

    # ==================================================================
    #
    #               Restrict the data to a radius
    #
    # ==================================================================
    if args.radius_meters:
        gdf['distance_to_center'] = gdf['geometry'].centroid.distance(shapely.Point((center_x, center_y)))
        gdf = gdf[gdf['distance_to_center'] <= args.radius_meters]
        gdf.drop('distance_to_center', axis='columns', inplace=True)
        print("Only %d parcels lie within the %.2f meter radius." % (len(gdf), args.radius_meters))

    # ==================================================================
    #
    #              Save the filtered dataframe to a GIS file
    #
    # ==================================================================
    if args.output_filepath:
        gdf.to_file(args.output_filepath)
        print("Saved filtered dataframe to %s." % (args.output_filepath))

    # ==================================================================
    #
    #                    Plot the filtered data
    #
    # ==================================================================
    if args.plot_filtered_filepath:
        if args.plot_key:
            if gdf[args.plot_key].isnull().values.all(axis=0):
                raise ValueError("Cannot make plot with %s as the key because that column is all null." % (args.plot_key))
            ax = gdf.plot(args.plot_key, figsize=(fs, fs), legend=True, markersize=ms, cmap=colormap)
        else:
            ax = gdf.plot(figsize=(fs, fs), legend=True, markersize=ms, cmap=colormap)
        cx.add_basemap(ax, source=cx.providers.Esri.WorldStreetMap)
        ax.figure.savefig(args.plot_filtered_filepath)
        print("Saved filtered plot to %s." % (args.plot_filtered_filepath))

    # ==================================================================
    #
    #              Save an interactive map to HTML
    #
    # ==================================================================
    if len(gdf) > args.max_folium_points:
        print("Warning! Too many points. Randomly dropping %d parcels." % (len(gdf) - args.max_folium_points))
        gdf = gdf.sample(frac=args.max_folium_points / len(gdf))
    if args.folium_filepath:
        if args.plot_key:
            ignore_outliers = args.outlier_percentile != None and plot_attribute_type == AttributeType.Quantitative
            q_low = gdf[args.plot_key].quantile(args.outlier_percentile) if ignore_outliers  else None
            q_hi  = gdf[args.plot_key].quantile(1 - args.outlier_percentile) if ignore_outliers else None
            if gdf[args.plot_key].isnull().values.all(axis=0):
                raise ValueError("Cannot make folium map with %s as the key because that column is all null." % (args.plot_key))
            m = gdf.explore(args.plot_key, legend=True, cmap=colormap, markersize=ms, tiles=args.tile_source, vmin=q_low, vmax=q_hi)
        else:
            m = gdf.explore(markersize=ms, tiles=args.tile_source)
        m.save(args.folium_filepath)
        print("Saved folium map to %s." % (args.folium_filepath))
    print("Total time: %.2f" % (time.time() - start_time))

if __name__ == "__main__":
    main()
