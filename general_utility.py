#!/usr/bin/env python3

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
        ("street", "st"),\
        ("road", "rd"),\
        ("terrace", "ter"))

def standardize_string(s):
    """
    Remove accents, make letters lowercase, remove spaces and punctuation.
    This way names from different sources can be compared directly.
    """
    cleaned = unidecode(s).lower().replace(' ', '').replace('-', '').replace('\'', '').strip()  
    for word, abbr in COMMON_ABBREVIATIONS:
        cleaned = cleaned.replace(word, abbr)
    return cleaned
