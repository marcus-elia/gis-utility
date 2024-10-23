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

from general_utility import parse_latlon_string, standardize_county, latlon_to_crs
from tax_parcel_loader import TaxParcelLoader


class AttributeType(Enum):
    Quantitative = 1
    Qualitative = 2

def main():
    attribute_keys_string = "'year_built', 'school_district', 'acres', 'zip', 'county', 'city', 'property_type', 'market_value', 'building_style', water_description', etc"
    parser = argparse.ArgumentParser(description="Print stats about tax parcel nodes.")
    parcel_source_group = parser.add_mutually_exclusive_group(required=True)
    parcel_source_group.add_argument("-i", "--input-filepath", help="Path to input GIS file of tax parcels if loading from single file.")
    parcel_source_group.add_argument("-d", "--county-parent-dir", help="Path to directory containing a subdir for each county.")
    parser.add_argument("-k", "--parcel-keys-and-values-filepath", required=True, help="Path to JSON file mapping generic key/value names to file-specific names.")
    parser.add_argument("-t", "--parcel-keys-types-filepath", required=True, help="Path to JSON file mapping generic key/value names to types.")
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
    parser.add_argument("--city", required=False, help="Desired city.")
    parser.add_argument("--municipality", required=False, help="Desired municipality.")
    parser.add_argument("--zip-code", required=False, help="Desired zip code.")
    parser.add_argument("--min-beds", required=False, help="Minimum number of bedrooms you want a house to have.")
    parser.add_argument("--min-baths", required=False, help="Minimum number of bathrooms you want a house to have.")
    parser.add_argument("--output-filepath", required=False, help="Save filtered dataframe to filepath.")
    parser.add_argument("--folium-filepath", required=False, help="Save interactive Folium map to HTML file.")
    parser.add_argument("--plot-all-filepath", required=False, help="Plot all points before filtering, save to image path.")
    parser.add_argument("--plot-key", required=False, help="The feature that colors the plot, if any. (%s)" % (attribute_keys_string))
    parser.add_argument("--plot-filtered-filepath", required=False, help="Plot the remaining points after filtering, save to image path.")
    parser.add_argument("--convert-to-centroid", action='store_true', help="If the geometry is polygons, replace with each parcel's centroid.")
    parser.add_argument("--outlier-percentile", required=False, help="Remove outliers for the column used as the plot coloring variable.")
    parser.add_argument("--center-latlon", required=False, help="The lat,lon center of the desired region.")
    parser.add_argument("--radius-meters", required=False, help="The radius, if the desired region is circular.")
    parser.add_argument("--width-meters", required=False, help="The width, if the desired region is rectangular.")
    parser.add_argument("--height-meters", required=False, help="The height, if the desired region is rectangular.")
    parser.add_argument("--county-name", required=False, help="Restrict results to a particular county.")
    parser.add_argument("--colormap", required=False, help="Colormap for the plots. Defaults 'plamsa' for quantitative, 'tab20' for qualitative. Also recommend 'viridis' and 'seismic' and 'bwr'.")
    parser.add_argument("--markersize", required=False, help="Markersize for the plots. Defaults to 15.")
    parser.add_argument("--figsize", required=False, help="Figure size for the plots. Defaults to 10.")
    parser.add_argument("--tile-source", required=False, default='OpenStreetMap.Mapnik', help="Tile source for Folium. Defaults to 'OpenStreetMap.Mapnik'. Some others are 'Esri.WorldImagery', 'Esri.WorldStreetMap', 'CartoDB.Positron', 'CartoDB.Voyager', 'USGS.USImagery', 'TopPlusOpen.Grey', 'Stadia.AlidadeSmooth")
    parser.add_argument("--max-folium-points", required=False, default=40000, help="Max number of points for interactive folium map. Defaults to 40k.")

    args = parser.parse_args()

    # ==================================================================
    #
    #                    Load JSON Data About Keys
    #
    # ==================================================================
    f = open(args.parcel_keys_and_values_filepath, 'r')
    general_name_to_specific_name = json.loads(f.read())
    f.close()

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
    if args.plot_key and (not args.plot_all_filepath and not args.plot_filtered_filepath and not args.folium_filepath):
        raise ValueError("plot-key is present but no plots are being saved.")
    if args.center_latlon and (not args.radius_meters and not args.width_meters):
        raise ValueError("Must specify a radius or a width when center is specified.")
    if args.radius_meters and (args.width_meters or args.height_meters):
        raise ValueError("Cannot specify both a circular and a rectangular region.")
    if not args.center_latlon and (args.radius_meters or args.width_meters or args.height_meters):
        raise ValueError("Must specify a center lat/lon to restrict to a circle or rectangle.")
    if args.county_parent_dir and (not args.center_latlon or (not args.radius_meters and not args.width_meters)):
        raise ValueError("Must specify a center lat/lon and a radius or width when loading from the county parent directory.")
    if args.colormap and (not args.plot_all_filepath and not args.plot_filtered_filepath and not args.folium_filepath):
        raise ValueError("Colormap is present but no plots are being saved.")

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
        if int(args.markersize) <= 0:
            raise ValueError("Markersize must be positive, not %d." % (int(args.markersize)))
        else:
            ms = int(args.markersize)
    else:
        ms = 15

    if args.figsize:
        if int(args.figsize) <= 0:
            raise ValueError("Figure size must be positive, not %d." % (int(args.figsize)))
        else:
            fs = int(args.figsize)
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
            width = 2 * float(args.radius_meters)
            height = width
        elif args.height_meters:
            width = float(args.width_meters)
            height = float(args.height_meters)
        else:
            width = float(args.width_meters)
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
        print("Loading parcels from county files contained in %s." % (args.county_parent_dir))
        loader = TaxParcelLoader(args.county_parent_dir)
        lat, lon = parse_latlon_string(args.center_latlon)
        gdf = loader.load_parcels((lat, lon), width, height)
    num_parcels = len(gdf)
    print("There are %d total parcels within the bounding box." % (num_parcels))

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
        def filter_by_row_value(row, column_name, filter_value):
            return standardize_county(row[column_name]) == filter_value
        gdf = gdf[gdf.apply(filter_by_row_value, axis=1, column_name=county_name_key, filter_value=standardize_county(args.county_name))]
        print("Only %d parcels lie within the the county named %s." % (len(gdf), args.county_name))

    # ==================================================================
    #
    #                    Plot all of the data
    #
    # ==================================================================
    if args.plot_all_filepath:
        if args.plot_key:
            column = general_name_to_specific_name["keys"][args.plot_key]
            ax = gdf.plot(column, figsize=(fs, fs), legend=True, markersize=ms, cmap=colormap)
        else:
            ax = gdf.plot(figsize=(fs, fs), legend=True, markersize=ms, cmap=colormap)
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
    city_key = general_name_to_specific_name["keys"]["city"]
    municipality_key = general_name_to_specific_name["keys"]["municipality"]
    zip_code_key = general_name_to_specific_name["keys"]["zip_code"]
    year_built_key = general_name_to_specific_name["keys"]["year_built"]
    sqft_key = general_name_to_specific_name["keys"]["sqft"]
    acres_key = general_name_to_specific_name["keys"]["acres"]
    beds_key = general_name_to_specific_name["keys"]["bedrooms"]
    baths_key = general_name_to_specific_name["keys"]["bathrooms"]
    school_district_key = general_name_to_specific_name["keys"]["school_district"]
    water_key = general_name_to_specific_name["keys"]["water_type"]
    sewer_key = general_name_to_specific_name["keys"]["sewer_type"]
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

    if args.city:
        gdf = gdf[gdf[city_key] == args.city]
        print("Filtered by city down to %d houses." % (len(gdf)))

    if args.municipality:
        gdf = gdf[gdf[municipality_key] == args.municipality]
        print("Filtered by municipality down to %d houses." % (len(gdf)))

    if args.zip_code:
        gdf = gdf[gdf[zip_code_key] == args.zip_code]
        print("Filtered by zip code down to %d houses." % (len(gdf)))

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
        if args.plot_key:
            column = general_name_to_specific_name["keys"][args.plot_key]
            ax = gdf.plot(column, figsize=(fs, fs), legend=True, markersize=ms, cmap=colormap)
        else:
            ax = gdf.plot(figsize=(fs, fs), legend=True, markersize=ms, cmap=colormap)
        cx.add_basemap(ax, source=cx.providers.Esri.WorldStreetMap)
        ax.figure.savefig(args.plot_filtered_filepath)

    # ==================================================================
    #
    #           Remove undesired keys and rename keys
    #
    # ==================================================================
    gdf = gdf.rename(columns={value: key for key, value in general_name_to_specific_name['keys'].items()})
    desired_keys = list(general_name_to_specific_name['keys'].keys()) + ['geometry']
    gdf = gdf[desired_keys]
    gdf = gdf.round(2)

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
            q_low = gdf[args.plot_key].quantile(float(args.outlier_percentile)) if ignore_outliers  else None
            q_hi  = gdf[args.plot_key].quantile(1 - float(args.outlier_percentile)) if ignore_outliers else None
            column = args.plot_key
            m = gdf.explore(column, legend=True, cmap=colormap, markersize=ms, tiles=args.tile_source, vmin=q_low, vmax=q_hi)
        else:
            m = gdf.explore(markersize=ms, tiles=args.tile_source)
        m.save(args.folium_filepath)
        print("Saved folium map to %s." % (args.folium_filepath))

if __name__ == "__main__":
    main()
