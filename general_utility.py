#!/usr/bin/env python3

import os
import pandas as pd
from unidecode import unidecode

COMMON_ABBREVIATIONS = (\
        ("fort", "ft"),\
        ("saint", "st"),\
        ("avenue", "ave"),\
        ("boulevard", "blvd"),\
        ("circle", "cir"),\
        ("court", "ct"),\
        ("drive", "dr"),\
        ("interstate", "i"),\
        ("lane", "ln"),\
        ("parkway", "pkwy"),\
        ("place", "pl"),\
        ("street", "st"),\
        ("road", "rd"),\
        ("route", "rte"),\
        ("terrace", "ter"),\
        ("trail", "tr"),\
        ("east", "e"),\
        ("north", "n"),\
        ("south", "s"),\
        ("west", "w")
        )

def standardize_string(s):
    """
    Remove accents, make letters lowercase, remove spaces and punctuation.
    This way names from different sources can be compared directly.
    """
    cleaned = unidecode(s).lower().replace(' ', '').replace('-', '').replace('\'', '').strip()  
    for word, abbr in COMMON_ABBREVIATIONS:
        cleaned = cleaned.replace(word, abbr)
    return cleaned

def standardize_city(city):
    city = standardize_string(city)
    if city.endswith("(city)"):
        return city[:-len("(city)")]
    if city.endswith("(town)"):
        return city[:-len("(town)")]
    if city.endswith("(village)"):
        return city[:-len("(village)")]
    if city.startswith("townof"):
        return city[len("townof"):]
    if city.startswith("cityof"):
        return city[len("cityof"):]
    if city.startswith("villageof"):
        return city[len("villageof"):]
    return city

def standardize_county(county):
    county = standardize_string(county)
    if county.endswith("county"):
        return county[:-len("county")]
    if county.startswith("countyof"):
        return county[len("countyof"):]
    return county

def to_camel_case(name, capitalize):
    words = name.split()
    camel_name = ""
    for word in words:
        if capitalize and len(word) > 1:
            word = word[0].upper() + word[1:].lower()
        camel_name += word
    return camel_name

def parse_latlon_string(latlon_string):
    lat,lon = latlon_string.split(',')
    return (float(lat.strip()), float(lon.strip()))

def list_files_recursive(path):
    for entry in os.listdir(path):
        full_path = os.path.join(path, entry)
        if os.path.isdir(full_path):
            yield from list_files_recursive(full_path)
        else:
            yield full_path

def get_time_estimate_string(time_elapsed, num_complete, num_total):
    percent_complete = float(num_complete) / float(num_total) * 100
    time_remaining = int(time_elapsed * (100 - percent_complete) / percent_complete)
    if time_elapsed < 120:
        time_string = "%d seconds, " % (time_elapsed)
    else:
        time_elapsed = int(time_elapsed / 60)
        if time_elapsed < 120:
            time_string = "%d minutes, " % (time_elapsed)
        else:
            time_elapsed = int(time_elapsed / 60)
            time_string = "%d hours, " % (time_elapsed)
    if time_remaining < 120:
        time_string += "%d seconds remaining." % (time_remaining)
    else:
        time_remaining = int(time_remaining / 60)
        if time_remaining < 120:
            time_string += "%d minutes remaining." % (time_remaining)
        else:
            time_remaining = int(time_remaining / 60)
            time_string += "%d hours remaining" % (time_remaining)

    return "Completed %d/%d (%.1f percent) in %s" % (num_complete, num_total, percent_complete, time_string)

def num_rows_in_csv(csv_path):
    df = pd.read_csv(csv_path)
    return df.shape[0]
