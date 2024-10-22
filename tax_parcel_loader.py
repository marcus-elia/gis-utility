#!/usr/bin/env python3

"""
The TaxParcelLoader will load tax parcels in a bbox by looking through
a directory hierarchy of counties.
"""

import geopandas
import os
import pandas as pd
import shapely

from general_utility import latlon_to_crs

class TaxParcelLoader():
    def __init__(self, parent_dir):
        # Directory containing a subdirectory for each county
        self.parent_dir = parent_dir

    def load_parcels(self, center_latlon, width_meters, height_meters):
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

        combined_gdf = geopandas.GeoDataFrame()
        # Iterate over each "...County" directory
        for entry in os.listdir(self.parent_dir):
            full_path = os.path.join(self.parent_dir, entry)
            if entry.endswith("County") and os.path.isdir(full_path):
                # Load the county's bbox and check if it is sufficiently close to the requested bbox.
                bbox_filepath = os.path.join(self.parent_dir, entry, entry + "Bbox.geojson")
                if not os.path.exists(bbox_filepath):
                    raise ValueError("%s does not exist." % (bbox_filepath))
                county_bbox = geopandas.GeoSeries.from_file(bbox_filepath)
                if not county_bbox[0].intersects(requested_bbox[0]):
                    continue

                # Load the parcels that are within the requested bounds.
                parcels_filepath = os.path.join(self.parent_dir, entry, entry[:-len("County")] + "TaxParcelCentroids.geojson")
                if not os.path.exists(parcels_filepath):
                    raise ValueError("%s does not exist." % (parcels_filepath))
                gdf = geopandas.read_file(parcels_filepath, bbox=requested_bbox, engine='fiona')
                if len(gdf) != 0:
                    combined_gdf = pd.concat([combined_gdf, gdf])
                print("%d in %s" % (len(gdf), entry))
        return combined_gdf.to_crs("EPSG:3857")
