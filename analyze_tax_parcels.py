#!/usr/bin/env python3

"""
This is intended to do some analysis of a dataset of tax parcels.
Give the parameters you want a house to have and it will print
some stats about how many there are.
"""

import argparse
import contextily as cx
import geopandas
import json
import shapely

from general_utility import parse_latlon_string, standardize_county

def main():
    parser = argparse.ArgumentParser(description="Print stats about tax parcel nodes.")
    parser.add_argument("-i", "--input-filepath", required=True, help="Path to input GIS file of tax parcels.")
    parser.add_argument("-k", "--parcel-keys-and-values-filepath", required=True, help="Path to JSON file mapping generic key/value names to file-specific names.")
    parser.add_argument("--already-sfh", action='store_true', help="If the dataset only contains single-family-homes, no need to filter.")
    parser.add_argument("--min-year-built", required=False, help="Oldest year you want a house to be built in.")
    parser.add_argument("--max-year-built", required=False, help="Newest year you want a house to be built in.")
    parser.add_argument("--min-sqft", required=False, help="Minimum square footage you want a house to have.")
    parser.add_argument("--max-sqft", required=False, help="Maximum square footage you want a house to have.")
    parser.add_argument("--min-acres", required=False, help="Minimum number of acres you want a house to have.")
    parser.add_argument("--max-acres", required=False, help="Maximum number of acres you want a house to have.")
    parser.add_argument("--require-connected-water", action='store_true', help="If you want the house to have public water.")
    parser.add_argument("--require-connected-sewer", action='store_true', help="If you want the house to have public sewer.")
    parser.add_argument("--school-district", required=False, help="Desired school district.")
    parser.add_argument("--min-beds", required=False, help="Minimum number of bedrooms you want a house to have.")
    parser.add_argument("--min-baths", required=False, help="Minimum number of bathrooms you want a house to have.")
    parser.add_argument("--output-filepath", required=False, help="Save filtered dataframe to filepath.")
    parser.add_argument("--plot-all-filepath", required=False, help="Plot all points before filtering, save to image path.")
    parser.add_argument("--plot-all-key", required=False, help="The feature of the full plot, if any. ('year_built', 'school_district', etc)")
    parser.add_argument("--plot-filtered-filepath", required=False, help="Plot the remaining points after filtering, save to image path.")
    parser.add_argument("--plot-filtered-key", required=False, help="The feature of the filtered plot, if any. ('year_built', 'school_district', etc)")
    parser.add_argument("--convert-to-centroid", action='store_true', help="If the geometry is polygons, replace with each parcel's centroid.")
    parser.add_argument("--center-latlon", required=False, help="The lat,lon center of the desired region.")
    parser.add_argument("--radius-meters", required=False, help="The radius, if the desired region is circular.")
    parser.add_argument("--width-meters", required=False, help="The width, if the desired region is rectangular.")
    parser.add_argument("--height-meters", required=False, help="The height, if the desired region is rectangular.")
    parser.add_argument("--county-name", required=False, help="Restrict results to a particular county.")

    args = parser.parse_args()

    # ==================================================================
    #
    #                          Verify Args
    #
    # ==================================================================
    if args.plot_all_key and not args.plot_all_filepath:
        raise ValueError("plot-all-key is present but plot-all-filepath is absent.")
    if args.plot_filtered_key and not args.plot_filtered_filepath:
        raise ValueError("plot-filtered-key is present but plot-filtered-filepath is absent.")
    if args.center_latlon and (not args.radius_meters and not args.width_meters):
        raise ValueError("Must specify a radius or a width when center is specified.")
    if args.radius_meters and (args.width_meters or args.height_meters):
        raise ValueError("Cannot specify both a circular and a rectangular region.")
    if not args.center_latlon and (args.radius_meters or args.width_meters or args.height_meters):
        raise ValueError("Must specify a center lat/lon to restrict to a circle or rectangle.")

    # ==================================================================
    #
    #             Convert center point from degrees to meters
    #
    # ==================================================================
    if args.center_latlon:
        lat, lon = parse_latlon_string(args.center_latlon)
        gdf_center = geopandas.GeoDataFrame({'geometry':[shapely.Point(lon, lat)]}, crs=4326)
        gdf_center = gdf_center.to_crs(3857)
        center_x, center_y = gdf_center.loc[0]['geometry'].x, gdf_center.loc[0]['geometry'].y
        print(center_x, center_y)

    # ==================================================================
    #
    #                          Load the data
    #
    # ==================================================================
    print("Loading %s." % (args.input_filepath))
    if args.center_latlon:
        if args.radius_meters:
            bbox = geopandas.GeoSeries([\
                    shapely.Point(center_x - float(args.radius_meters), center_y - float(args.radius_meters)),\
                    shapely.Point(center_x + float(args.radius_meters), center_y + float(args.radius_meters))\
                    ], crs="EPSG:3857")
        elif args.height_meters:
            bbox = geopandas.GeoSeries([\
                    shapely.Point(center_x - float(args.width_meters)/2, center_y - float(args.height_meters)/2),\
                    shapely.Point(center_x + float(args.width_meters)/2, center_y + float(args.height_meters)/2)\
                    ], crs="EPSG:3857")
        else:
            bbox = geopandas.GeoSeries([\
                    shapely.Point(center_x - float(args.width_meters)/2, center_y - float(args.width_meters)/2),\
                    shapely.Point(center_x + float(args.width_meters)/2, center_y + float(args.width_meters)/2)\
                    ], crs="EPSG:3857")
        gdf = geopandas.read_file(args.input_filepath, bbox=bbox, engine='fiona')
    else:
        gdf = geopandas.read_file(args.input_filepath)
    num_parcels = len(gdf)
    print("There are %d total parcels within the bounding box." % (num_parcels))

    f = open(args.parcel_keys_and_values_filepath, 'r')
    general_name_to_specific_name = json.loads(f.read())
    f.close()

    # ==================================================================
    #
    #               Convert CRS from degrees to meters
    #
    # ==================================================================
    
    # Convert to this projection. Needed for the contextily basemaps and enforcing a radius.
    gdf = gdf.to_crs(epsg=3857)

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
        gdf = gdf[gdf['distance_to_center'] <= float(args.radius_meters)]
        gdf.drop('distance_to_center', axis='columns', inplace=True)
        print("Only %d parcels lie within the %.2f meter radius." % (len(gdf), float(args.radius_meters)))

    # ==================================================================
    #
    #               Restrict the data to a county
    #
    # ==================================================================
    if args.county_name:
        county_name_key = general_name_to_specific_name["keys"]["county"]
        gdf = gdf[standardize_county(gdf[county_name_key]) == standardize_county(args.county_name)]
        print("Only %d parcels lie within the the county named %s." % (len(gdf), args.county_name))

    # ==================================================================
    #
    #                    Plot all of the data
    #
    # ==================================================================
    if args.plot_all_filepath:
        if args.plot_all_key:
            column = general_name_to_specific_name["keys"][args.plot_all_key]
            ax = gdf.plot(column, figsize=(10, 10), legend=True, markersize=10)
        else:
            ax = gdf.plot(figsize=(10, 10), legend=True, markersize=10)
        cx.add_basemap(ax, source=cx.providers.Esri.WorldStreetMap)
        ax.figure.savefig(args.plot_all_filepath)

    # ==================================================================
    #
    #               Set the variables for filtering
    #
    # ==================================================================
    min_year = int(args.min_year_built) if args.min_year_built else 0
    max_year = int(args.max_year_built) if args.max_year_built else 9999
    min_sqft = float(args.min_sqft) if args.min_sqft else 0
    max_sqft = float(args.max_sqft) if args.max_sqft else 99999
    min_acres = float(args.min_acres) if args.min_acres else 0
    max_acres = float(args.max_acres) if args.max_acres else 99999
    min_beds = int(args.min_beds) if args.min_beds else 0
    min_baths = float(args.min_baths) if args.min_baths else 0

    property_type_key = general_name_to_specific_name["keys"]["property_type"]
    year_built_key = general_name_to_specific_name["keys"]["year_built"]
    sqft_key = general_name_to_specific_name["keys"]["sqft"]
    acres_key = general_name_to_specific_name["keys"]["acres"]
    beds_key = general_name_to_specific_name["keys"]["bedrooms"]
    baths_key = general_name_to_specific_name["keys"]["bathrooms"]
    school_district_key = general_name_to_specific_name["keys"]["school_district"]
    water_key = general_name_to_specific_name["keys"]["water"]
    sewer_key = general_name_to_specific_name["keys"]["sewer"]
    single_family_home_value = general_name_to_specific_name["values"]["single_family_home"]
    connected_water_value = general_name_to_specific_name["values"]["connected_water"]
    connected_sewer_value = general_name_to_specific_name["values"]["connected_sewer"]

    # ==================================================================
    #
    #               Filter to only get the desired houses
    #
    # ==================================================================
    if not args.already_sfh:
        gdf = gdf[gdf[property_type_key] == single_family_home_value]
        print("Filtered down to %d single-family-homes." % (len(gdf)))

    if args.min_year_built or args.max_year_built:
        gdf = gdf[(gdf[year_built_key] >= min_year) & (gdf[year_built_key] <= max_year)]
        print("Filtered by year down to %d houses." % (len(gdf)))

    if args.min_sqft or args.max_sqft:
        gdf = gdf[(gdf[sqft_key] >= min_sqft) & (gdf[sqft_key] <= max_sqft)]
        print("Filtered by square footage down to %d houses." % (len(gdf)))

    if args.min_acres or args.max_acres:
        gdf = gdf[(gdf[acres_key] >= min_acres) & (gdf[acres_key] <= max_acres)]
        print("Filtered by square footage down to %d houses." % (len(gdf)))

    if args.min_beds:
        gdf = gdf[(gdf[beds_key] >= min_beds)]
        print("Filtered by number of bedrooms down to %d houses." % (len(gdf)))

    if args.min_baths:
        gdf = gdf[(gdf[baths_key] >= min_baths)]
        print("Filtered by number of bathrooms down to %d houses." % (len(gdf)))

    if args.require_connected_water:
        gdf = gdf[(gdf[water_key] == connected_water_value)]
        print("Filtered by water type down to %d houses." % (len(gdf)))

    if args.require_connected_sewer:
        gdf = gdf[(gdf[sewer_key] == connected_sewer_value)]
        print("Filtered by sewer type down to %d houses." % (len(gdf)))

    if args.school_district:
        gdf = gdf[gdf[school_district_key] == args.school_district]
        print("Filtered by school district down to %d houses." % (len(gdf)))
    else:
        districts = gdf[school_district_key].unique()
        print("Houses per school district:")
        for district in districts:
            print("%s: %d" % (district, len(gdf[gdf[school_district_key] == district])))
    
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
        if args.plot_filtered_key:
            column = general_name_to_specific_name["keys"][args.plot_filtered_key]
            ax = gdf.plot(column, figsize=(10, 10), legend=True, markersize=10)
        else:
            ax = gdf.plot(figsize=(10, 10), legend=True, markersize=10)
        cx.add_basemap(ax, source=cx.providers.Esri.WorldStreetMap)
        ax.figure.savefig(args.plot_filtered_filepath)

if __name__ == "__main__":
    main()
