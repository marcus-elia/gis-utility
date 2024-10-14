#!/usr/bin/env python3

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
