#!/usr/bin/env python3

"""
The TaxParcelLoader will load tax parcels in a bbox by looking through
a directory hierarchy of counties.
"""

import geopandas
import json
import os
import pandas as pd
import shapely

from general_utility import latlon_to_crs

class AttributeFilter():
    def __init__(self, already_sfh, require_connected_water, require_connected_sewer, min_year_built, max_year_built, min_sqft, max_sqft, min_acres, max_acres, min_beds, min_baths, county, school_district, city, municipality, zip_code):
        self.dont_filter_to_sfh = already_sfh
        self.require_connected_water = require_connected_water
        self.require_connected_sewer = require_connected_sewer
        self.min_year_built = min_year_built if min_year_built else 0
        self.max_year_built = max_year_built if max_year_built else 9999
        self.min_sqft = min_sqft if min_sqft else 0
        self.max_sqft = max_sqft if max_sqft else 99999
        self.min_acres = min_acres if min_acres else 0
        self.max_acres = max_acres if max_acres else 99999
        self.min_beds = min_beds if min_beds else 0
        self.min_baths = min_baths if min_baths else 0
        self.county = county
        self.school_district = school_district
        self.city = city
        self.municipality = municipality
        self.zip_code = zip_code

    def apply_filter(self, gdf, general_name_to_specific_name):
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

        if not self.dont_filter_to_sfh:
            gdf = gdf[gdf[property_type_key] == single_family_home_value]

        if self.min_year_built or self.max_year_built:
            gdf = gdf[(gdf[year_built_key] >= self.min_year_built) & (gdf[year_built_key] <= self.max_year_built)]

        if self.min_sqft or self.max_sqft:
            gdf = gdf[(gdf[sqft_key] >= self.min_sqft) & (gdf[sqft_key] <= self.max_sqft)]

        if self.min_acres or self.max_acres:
            gdf = gdf[(gdf[acres_key] >= self.min_acres) & (gdf[acres_key] <= self.max_acres)]

        if self.min_beds:
            gdf = gdf[(gdf[beds_key] >= self.min_beds)]

        if self.min_baths:
            gdf = gdf[(gdf[baths_key] >= self.min_baths)]

        if self.require_connected_water:
            gdf = gdf[(gdf[water_key] == connected_water_value)]

        if self.require_connected_sewer:
            gdf = gdf[(gdf[sewer_key] == connected_sewer_value)]

        if self.city:
            gdf = gdf[gdf[city_key] == self.city]

        if self.municipality:
            gdf = gdf[gdf[municipality_key] == self.municipality]

        if self.zip_code:
            gdf = gdf[gdf[zip_code_key] == self.zip_code]

        if self.school_district:
            gdf = gdf[gdf[school_district_key] == self.school_district]

        return gdf

class TaxParcelLoader():
    def __init__(self, state_dir, keys_and_values_filename):
        # Directory containing a subdirectory for each county
        self.state_dir = state_dir
        self.keys_and_values_filename = keys_and_values_filename

    def load_parcels(self, center_latlon, width_meters, height_meters, attribute_filter):
        # Get the requested bounding box in the EPSG 3857 projection.
        x, y = latlon_to_crs(center_latlon[0], center_latlon[1], 3857)
        requested_bbox = geopandas.GeoSeries([\
                shapely.Polygon((\
                    (x - width_meters/2, y - height_meters/2),\
                    (x + width_meters/2, y - height_meters/2),\
                    (x + width_meters/2, y + height_meters/2),\
                    (x - width_meters/2, y + height_meters/2),\
                    (x - width_meters/2, y - height_meters/2)))\
                    ], crs="EPSG:3857")

        # First load the keys/values for the state. Most counties will use this.
        f = open(os.path.join(self.state_dir, self.keys_and_values_filename), 'r')
        statewide_general_name_to_specific_name = json.loads(f.read())
        f.close()

        # Start with an empty dataframe to add things to.
        combined_gdf = geopandas.GeoDataFrame()

        # Iterate over each "...County" directory
        for entry in os.listdir(self.state_dir):
            full_path = os.path.join(self.state_dir, entry)
            if entry.endswith("County") and os.path.isdir(full_path):
                if attribute_filter.county and standardize_county(attribute_filter.county) != standardize_county(entry[:-len("County")]):
                    # If restricting to a single county, don't even try any others.
                    continue
                # Load the county's bbox and check if it is sufficiently close to the requested bbox.
                bbox_filepath = os.path.join(self.state_dir, entry, entry + "Bbox.geojson")
                if not os.path.exists(bbox_filepath):
                    raise ValueError("%s does not exist." % (bbox_filepath))
                county_bbox = geopandas.GeoSeries.from_file(bbox_filepath)
                if not county_bbox[0].intersects(requested_bbox[0]):
                    continue

                # Load the parcels that are within the requested bounds.
                parcels_filepath = os.path.join(self.state_dir, entry, entry[:-len("County")] + "TaxParcelCentroids.geojson")
                if not os.path.exists(parcels_filepath):
                    raise ValueError("%s does not exist." % (parcels_filepath))
                gdf = geopandas.read_file(parcels_filepath, bbox=requested_bbox, engine='fiona')

                # Filter the data
                county_keys_and_values_filepath = os.path.join(full_path, self.keys_and_values_filename)
                if os.path.exists(county_keys_and_values_filepath):
                    f = open(county_keys_and_values_filepath, 'r')
                    county_general_name_to_specific_name = json.loads(f.read())
                    f.close()
                else:
                    county_general_name_to_specific_name = statewide_general_name_to_specific_name

                gdf = attribute_filter.apply_filter(gdf, county_general_name_to_specific_name)

                # Remove unwanted columns and rename the rest.
                gdf = gdf.rename(columns={value: key for key, value in county_general_name_to_specific_name['keys'].items()})
                desired_keys = list(county_general_name_to_specific_name['keys'].keys()) + ['geometry']
                gdf = gdf[desired_keys]
                gdf = gdf.round(2)

                # Add the parcels to the existing dataframe.
                if len(gdf) != 0:
                    combined_gdf = pd.concat([combined_gdf, gdf])
                print("%d in %s" % (len(gdf), entry))
        return combined_gdf.to_crs("EPSG:3857")
