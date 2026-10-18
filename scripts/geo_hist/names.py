"""Display names and sovereigns ("sub") for the historical world layer.

Three sources need cleaning:
  * historical-basemaps (HB) snapshots: NAME/SUBJECTO are inconsistent (typos, "(UK)" suffixes, SUBJECTO values
    such as "3" or "UK", a few clear dating errors). hb_props() returns the display name and sovereign per
    snapshot and per polygon part (some multipolygons mix a metropole and its colonies).
  * CShapes-Europe (1816-1885 rows only): cse_props().
  * CShapes 2.0 (GW version): cs_periods() splits a CShapes country-period at the dates where its common name
    changed (e.g. Persia -> Iran 1935-03-21) and names the sovereign of dependencies from the CShapes owner code.
FILLS lists small territories that CShapes 2.0 does not map at all (microstates, island colonies, Greenland,
Svalbard...), filled from Natural Earth 1:50m with a hand-coded sovereignty timeline.
"""
import re

# ----------------------------------------------------------------------------------------------- HB snapshots

def brit(S):
    return 'England' if S <= 1700 else ('Great Britain' if S <= 1800 else 'United Kingdom')


def dutch(S):
    return 'Dutch Republic' if S <= 1783 else ('Batavian Republic' if S == 1800 else 'Netherlands')


def habs(S):
    return 'Habsburg Monarchy' if S <= 1800 else ('Austrian Empire' if S == 1815 else 'Austria-Hungary')


def dk(S):
    return 'Denmark-Norway' if S <= 1800 else 'Denmark'


def russia(S):
    return 'Tsardom of Russia' if S <= 1715 else 'Russian Empire'


def china(S):
    return 'Ming Empire' if S == 1600 else 'Qing Empire'


SOVEREIGN = {  # raw SUBJECTO value -> function(S) or fixed display name of the sovereign
    'United Kingdom': brit, 'UK': brit, 'Great Britain': brit, 'England': brit,
    'United Kingdom of Great Britain and Ireland': brit, 'British East India Company': brit,
    'Netherlands': dutch, 'Neterlands': dutch, 'Dutch East Indies': dutch,
    'Spanish Habsburg': 'Spain', 'Spain': 'Spain',
    'Austrian Empire': habs, 'Austria': habs, 'Habsburg Austria': habs,
    'Danemark': dk, 'Denmark': dk, 'Denmark-Norway': dk,
    'Manchu Empire': china, 'Portugal': 'Portugal', 'France': 'France', 'Ottoman Empire': 'Ottoman Empire',
    'Prussia': 'Prussia', 'Savoy-Piedmont': 'Savoy', 'Egypt': 'Egypt', 'Russian Empire': russia,
}

SUFFIX = re.compile(r'^(.*?)\s*\((UK|FR|GB|Spain|Portugal|Dutch|Danemark|Austria|Egypt|Netherlands)\)$')
SUFFIX_SOV = {'UK': brit, 'GB': brit, 'FR': 'France', 'Spain': 'Spain', 'Portugal': 'Portugal', 'Dutch': dutch,
              'Danemark': dk, 'Austria': habs, 'Egypt': 'Egypt', 'Netherlands': dutch}

# Global renames of HB names (spelling, anachronistic or modern-sounding names).
RENAME = {
    'Austria Hungary': 'Austria-Hungary', 'British Raj': 'British India',
    'British East India Company': 'British India (East India Company)',
    'Imperial Japan': 'Japan', 'Japan (Warring States)': 'Japan', 'Tokugawa shogunate': 'Japan',
    'Manchu Empire': 'Qing Empire', 'Ming Chinese Empire': 'Ming Empire', 'Kingdom of Brazil': 'Empire of Brazil',
    'M?ori': 'Māori', 'Maori': 'Māori', 'Maoris': 'Māori', 'Sultinate of Zanzibar': 'Sultanate of Zanzibar',
    'United Kingdom of Great Britain and Ireland': 'United Kingdom', 'United States of America': 'United States',
    'Germany': 'German Empire', 'Netherlands Indies': 'Dutch East Indies', 'Papua New Guinea': 'New Guinea',
    'Tsardom of Muscovy': 'Tsardom of Russia', 'Rattanakosin Kingdom': 'Siam',
    'Arakan (Indian princely state)': 'Arakan', 'Mysore (Indian princely state)': 'Mysore',
    'Sikkim (Indian princely state)': 'Sikkim', '       ': 'United Kingdom of the Netherlands',
    'Athabaskan': 'Athabascan', 'Hopie': 'Hopi', 'Winebago': 'Winnebago', 'Navaho': 'Navajo',
    'Imerina': 'Merina Kingdom', 'Bokhara Khanate': 'Emirate of Bukhara', 'central Asian khanates': 'Central Asian khanates',
    'Harer (Egypt)': 'Harar', 'Luisiana': 'Louisiana', 'Habsburg Netherlands': 'Spanish Netherlands',
    'Milano (Austria)': 'Milan', 'Guiana': 'Dutch Guiana', 'Guyana (Netherlands)': 'Dutch Guiana',
    'Surinam': 'Suriname', 'Acadian Peninsula (UK)': 'Nova Scotia', 'British American colonies': 'British America',
    'Ceylon (Dutch)': 'Ceylon', 'French Indochina': 'French Cochinchina', 'Trucial Oman': 'Trucial States',
    'Virgin Islands (Danemark)': 'Danish West Indies', 'United States Virgin Islands': 'Danish West Indies',
    'American Samoa': 'Samoa', 'Netherlands Antilles': 'Dutch Antilles', 'Madras': 'Madras Presidency',
    'Bengal': 'Bengal', 'Circars': 'Northern Circars', 'Sweden–Norway': 'Sweden–Norway',
    'Algeria (FR)': 'Algeria', 'Senegal (FR)': 'Senegal', 'Gold Coast (GB)': 'Gold Coast', 'Angola (Portugal)': 'Angola',
    'Kuril Islands': 'Kuril Islands', 'Polish–Lithuanian Commonwealth': 'Polish–Lithuanian Commonwealth',
}

# Sovereign by (display) name, for colonies HB leaves without SUBJECTO. value: fn(S) | str | {S: str}
SUB_BY_NAME = {
    'Anguilla': brit, 'Antigua and Barbuda': brit, 'Montserrat': brit, 'Barbados': brit, 'Bahamas': brit,
    'Turks and Caicos Islands': brit, 'Saint Kitts and Nevis': brit, 'British West Indies': brit,
    'Dominica': {1715: '', 1783: 'Great Britain', 1800: 'Great Britain', 1815: 'United Kingdom', 1878: 'United Kingdom', 1880: 'United Kingdom'},
    'Grenada': {1715: 'France', 1815: 'United Kingdom'}, 'Saint Lucia': {1715: 'France', 1815: 'United Kingdom'},
    'Saint Vincent and the Grenadines': {1715: '', 1815: 'United Kingdom'}, 'Trinidad': {1715: 'Spain', 1815: 'United Kingdom'},
    'Guadeloupe': 'France', 'Martinique': 'France', 'French West Indies': 'France', 'Saint Martin': 'France',
    'Saint Barthelemy': {1715: 'France', 1783: 'France', 1800: 'Sweden', 1815: 'Sweden', 1878: 'Sweden', 1880: 'France'},
    'Dutch Antilles': dutch, 'Danish West Indies': dk, 'Spanish West Indies': 'Spain',
    'British Guiana': brit, 'Dutch Guiana': dutch, 'French Guiana': 'France', 'Cayenne': 'France', 'Essequibo': dutch,
    'Suriname': {1650: '', 1700: 'Dutch Republic'}, 'British Honduras': brit, 'Mosquito Coast': brit,
    "Rupert's Land": brit, 'Nova Scotia': brit, 'British America': brit, 'British North America': brit,
    'Massachusetts Bay': brit, 'Virginia': brit, 'South Carolina': brit, 'New France': 'France', 'Louisiana': 'France',
    'Quebec': brit, 'Florida': 'Spain', 'Spanish Florida': 'Spain', 'Cuba': 'Spain', 'Hispaniola': 'Spain',
    'Santo Domingo': 'Spain', 'Jamaica': brit, 'Virgin Islands': brit, 'Saint-Domingue': 'France',
    'Viceroyalty of New Spain': 'Spain', 'Viceroyalty of Peru': 'Spain', 'Viceroyalty of New Granada': 'Spain',
    'Viceroyalty of the Río de la Plata': 'Spain', 'Viceroyalty of Brazil': 'Portugal', 'Portuguese Brazil': 'Portugal',
    'Philippines': 'Spain', 'Dutch East Indies': dutch, 'Dutch Gold Coast': dutch, 'Goa': 'Portugal',
    'Delagoa Bay': 'Portugal', 'Portuguese East Africa': 'Portugal', 'Portuguese Guinea': 'Portugal',
    'Mozambique': 'Portugal', 'Angola': {1815: 'Portugal', 1878: 'Portugal', 1880: 'Portugal'},
    'Sierra Leone': brit, 'Gambia': brit, 'Lagos': brit, 'Gold Coast': brit, 'Natal': brit, 'Basutoland': brit,
    'Griqualand West': brit, 'Cape Colony': {1715: 'Dutch Republic', 1783: 'Dutch Republic', 1800: 'Great Britain', 1815: 'United Kingdom', 1878: 'United Kingdom', 1880: 'United Kingdom'},
    'Gabon': 'France', 'Ivory Coast': 'France', 'Cotonou': 'France', 'Algeria': 'France', 'Spanish Guinea': 'Spain',
    'Senegal': {1815: 'France', 1878: 'France', 1880: 'France'}, 'French Congo': 'France', 'French Cochinchina': 'France',
    'Malta': brit, 'Ceylon': {1800: 'Great Britain', 1815: 'United Kingdom', 1878: 'United Kingdom', 1880: 'United Kingdom'},
    'British India': brit, 'British India (East India Company)': brit, 'Bengal Presidency': brit,
    'Madras Presidency': brit, 'Northern Circars': brit, 'Hong Kong': brit,
    'New South Wales': brit, 'Queensland': brit, 'Victoria': brit, 'South Australia': brit, 'Western Australia': brit,
    'Northern Territory': brit, 'Tasmania': brit, "Van Diemen's Land": brit, 'Fiji': {1878: 'United Kingdom', 1880: 'United Kingdom'},
    'Greenland': 'Denmark', 'Iceland': 'Denmark', 'Russian America': 'Russian Empire',
    'Emirate of Bukhara': 'Russian Empire', 'Trucial States': brit, 'Harar': 'Egypt', 'Kingdom of Ireland': brit,
    'Spanish Netherlands': 'Spain', 'Austrian Netherlands': habs, 'Milan': {1600: 'Spain', 1650: 'Spain', 1700: 'Spain', 1715: 'Habsburg Monarchy', 1783: 'Habsburg Monarchy'},
    'Naples': {1600: 'Spain', 1650: 'Spain', 1700: 'Spain', 1715: 'Habsburg Monarchy'},
    'Sicily': {1600: 'Spain', 1650: 'Spain', 1700: 'Spain', 1715: 'Savoy'},
    'Sardinia': {1600: 'Spain', 1650: 'Spain', 1700: 'Spain', 1715: 'Habsburg Monarchy'},
    'Franche-Comté': {1650: 'Spain', 1700: 'France'}, 'Lombardy': {1783: 'Habsburg Monarchy', 1815: 'Austrian Empire'},
    'Venetia': {1815: 'Austrian Empire'}, 'Finnmark': dk, 'New Netherland': 'Dutch Republic', 'New York': 'England',
    'Essequibo and Demerara': 'Dutch Republic', 'Cochin': {1783: 'Dutch Republic', 1800: 'Great Britain'},
    'Malabar': {1783: 'Dutch Republic', 1800: 'Great Britain'}, 'Crimean Khanate': 'Ottoman Empire',
    'Egypt': {1878: 'Ottoman Empire', 1880: 'Ottoman Empire'}, 'Brandenburg': 'Prussia',
}

# Sovereign values that are not sovereigns (or are wrong) -> no sub.
NO_SUB = {'3', '', '(Russian and Japanese claim)', 'Papu', 'Gros Ventre', None}

# Per-snapshot overrides keyed by raw HB NAME: (name, sub) ; sub None = derive.
OVERRIDE = {
    (1650, 'New Amsterdam'): ('New Netherland', 'Dutch Republic'),
    (1700, 'New Amsterdam'): ('New York', 'England'),
    (1700, 'Dutch Brazil'): ('Portuguese Brazil', 'Portugal'),
    (1700, 'Dutch Formosa'): ('Qing Empire', ''),
    (1783, 'British Guiana'): ('Essequibo and Demerara', 'Dutch Republic'),
    (1715, 'Haiti'): ('Saint-Domingue', 'France'),
    (1815, 'Canada'): ('British North America', 'United Kingdom'),
    (1815, 'United Provinces of the Río de la Plata'): ('United Provinces of the Río de la Plata', ''),
    (1815, 'Modena'): ('Modena', ''), (1815, 'Parma'): ('Parma', ''),
    (1800, 'Hanover'): ('Hanover', ''), (1800, 'Mecklenburg-Strelitz'): ('Mecklenburg-Strelitz', ''),
    (1800, 'Kingdom of Ireland'): ('Kingdom of Ireland', 'Great Britain'),
    (1715, 'Belize'): ('British Honduras', 'Great Britain'), (1878, 'Belize'): ('British Honduras', 'United Kingdom'),
    (1880, 'Belize'): ('British Honduras', 'United Kingdom'),
    (1783, 'India'): ('British India (East India Company)', 'Great Britain'),
    (1783, 'Bengal'): ('Bengal Presidency', 'Great Britain'),
    (1783, 'Madras'): ('Madras Presidency', 'Great Britain'),
    (1715, 'United Kingdom'): ('Great Britain', ''), (1783, 'United Kingdom'): ('Great Britain', ''),
    (1800, 'United Kingdom'): ('Great Britain', ''),
    (1783, 'Quebec'): ('Quebec', 'Great Britain'), (1800, 'Quebec'): ('Quebec', 'Great Britain'),
    (1783, 'Luisiana'): ('Louisiana', 'Spain'), (1800, 'Luisiana'): ('Louisiana', 'Spain'),
    (1715, 'Louisiana'): ('Louisiana', 'France'),
    (1800, 'Travancore'): ('Travancore', ''), (1783, 'Travancore'): ('Travancore', ''), (1815, 'Travancore'): ('Travancore', ''),
    (1878, 'Canada'): ('Canada', ''), (1880, 'Canada'): ('Canada', ''),
    (1878, 'Congo'): ('French Congo', 'France'), (1880, 'Congo'): ('French Congo', 'France'),
    (1878, 'Taiwan'): ('Qing Empire', ''), (1880, 'Taiwan'): ('Qing Empire', ''),
    (1600, 'Hispaniola (Spain)'): ('Hispaniola', 'Spain'), (1600, 'Cuba (Spain)'): ('Cuba', 'Spain'),
    (1600, 'Viceroyalty of New Spain'): ('Viceroyalty of New Spain', 'Spain'),
    (1600, 'Inca Empire'): ('Viceroyalty of Peru', 'Spain'),       # the Inca state ended in 1572
    (1715, 'Saint Barthelemy'): ('Saint Barthélemy', 'France'), (1783, 'Saint Barthelemy'): ('Saint Barthélemy', 'France'),
    (1800, 'Saint Barthelemy'): ('Saint Barthélemy', 'Sweden'), (1815, 'Saint Barthelemy'): ('Saint Barthélemy', 'Sweden'),
    (1878, 'Saint Barthelemy'): ('Saint Barthélemy', 'Sweden'), (1880, 'Saint Barthelemy'): ('Saint Barthélemy', 'France'),
    (1815, 'Senegal'): ('Senegal', 'France'),
}
for _S in (1650, 1700, 1715, 1783, 1800, 1815):
    OVERRIDE[(_S, 'Hong Kong')] = ('Qing Empire', '')       # no British Hong Kong before 1841
for _S in (1650, 1700, 1715, 1783, 1800):
    OVERRIDE[(_S, 'Austrian Empire')] = ('Habsburg Monarchy', '')
for _S in (1650, 1700):
    OVERRIDE[(_S, 'Spain')] = ('Spain', '')
for _S in (1600, 1650, 1700, 1715, 1783, 1800):
    OVERRIDE[(_S, 'Hindu kingdoms')] = ('Hindu kingdoms', '')


def hb_props(S, raw_name, raw_sub, cx, cy):
    """Display (name, sub) for one polygon part of an HB feature. cx, cy: the part's representative point.
    Returns (None, None) for unnamed parts (handled geometrically) and ('', '') for parts to drop."""
    n = raw_name
    if n is None:
        if raw_sub == 'Dutch East Indies':            # 1815 unnamed Indonesian islands
            return 'Dutch East Indies', 'Netherlands'
        return None, None
    # location-dependent splits of mixed multipolygons
    if cx < -30 and n in ('United Kingdom', 'United Kingdom of Great Britain and Ireland'):
        return 'British West Indies', brit(S)
    if cx < -30 and n == 'France':
        return 'French West Indies', 'France'
    if cx < -30 and n == 'Spain':
        return 'Spanish West Indies', 'Spain'
    if S == 1815 and n == 'Denmark':
        if cx < -30:
            return 'Greenland', 'Denmark'
        if cx < -12 and cy > 62:
            return 'Iceland', 'Denmark'
    if n == 'Russian Empire' and -172.5 <= cx <= -125:
        if S in (1878, 1880):
            return '', ''                            # duplicates of US Alaska in these files
        return 'Russian America', 'Russian Empire'
    if S == 1815 and n == 'Dutch East Indies' and cx < 40:
        return 'Cape Colony', 'United Kingdom'       # mislabelled Cape polygon
    if S in (1715, 1783) and n == 'Netherlands' and cy < 20:
        return 'Dutch Gold Coast', dutch(S)
    if (S, n) in OVERRIDE:
        name, sub = OVERRIDE[(S, n)]
        return name, sub
    m = SUFFIX.match(n)
    sub_hint = None
    if m:
        n, suf = m.group(1), m.group(2)
        v = SUFFIX_SOV[suf]
        sub_hint = v(S) if callable(v) else v
    name = RENAME.get(n, RENAME.get(raw_name, n))
    if name == 'Austrian Empire' and S <= 1800:
        name = 'Habsburg Monarchy'
    # sovereign
    sub = None
    if name in SUB_BY_NAME:
        v = SUB_BY_NAME[name]
        if isinstance(v, dict):
            sub = v.get(S)
        else:
            sub = v(S) if callable(v) else v
    if sub is None and sub_hint is not None:
        sub = sub_hint
    if sub is None:
        rs = raw_sub
        if rs in NO_SUB or rs == raw_name or rs == n or rs == name:
            sub = ''
        elif rs in SOVEREIGN:
            v = SOVEREIGN[rs]
            sub = v(S) if callable(v) else v
        else:
            sub = ''                                  # SUBJECTO used as a region label, not a sovereign
    if sub == name:
        sub = ''
    return name, sub


# ------------------------------------------------------------------------------------------- CShapes-Europe

CSE_NAME = {
    10037: 'Brunswick', 10023: 'Kingdom of Sardinia', 10016: 'Kingdom of the Two Sicilies', 275: 'Hesse-Darmstadt',
    273: 'Hesse-Kassel', 10031: 'Saxe-Hildburghausen', 10033: 'Saxe-Weimar-Eisenach', 10034: 'Schaumburg-Lippe',
    10017: 'Lippe', 10007: 'Chechnya', 10009: 'Free City of Kraków', 10010: 'Free City of Frankfurt',
    365: 'Russian Empire', 640: 'Ottoman Empire', 380: 'Sweden–Norway', 616: 'Tunisia',
    10030: 'Saxe-Gotha-Altenburg', 10002: 'Anhalt-Bernburg',
}


def cse_props(row_id, name, holder, year):
    """(name, sub) for a CShapes-Europe row valid in `year` (1816-1885)."""
    if row_id == 255:
        n = 'Prussia' if year <= 1866 else ('North German Confederation' if year <= 1870 else 'German Empire')
    elif row_id == 300:
        n = 'Austrian Empire' if year <= 1866 else 'Austria-Hungary'
    elif row_id == 210:
        n = 'United Kingdom of the Netherlands' if year <= 1830 else 'Netherlands'
    elif row_id == 651:
        n = 'Egypt'
    else:
        n = CSE_NAME.get(row_id, name)
    sub = ''
    if holder != row_id:
        sub = {200: 'United Kingdom', 390: 'Denmark'}.get(holder, '')
    return n, sub


# ------------------------------------------------------------------------------------------- CShapes 2.0

BASE = {  # gwcode -> common name (overridden by NAMES_BY_DATE where the name changed)
    2: 'United States', 3: 'Alaska', 4: 'Hawaii', 6: 'Puerto Rico', 20: 'Canada', 21: 'Newfoundland', 31: 'Bahamas',
    40: 'Cuba', 41: 'Haiti', 42: 'Dominican Republic', 51: 'Jamaica', 52: 'Trinidad and Tobago', 53: 'Barbados',
    65: 'Guadeloupe', 66: 'Martinique', 70: 'Mexico', 90: 'Guatemala', 91: 'Honduras', 92: 'El Salvador',
    93: 'Nicaragua', 94: 'Costa Rica', 95: 'Panama', 100: 'Colombia', 101: 'Venezuela', 120: 'French Guiana',
    130: 'Ecuador', 135: 'Peru', 140: 'Brazil', 145: 'Bolivia', 150: 'Paraguay', 155: 'Chile', 160: 'Argentina',
    165: 'Uruguay', 200: 'United Kingdom', 210: 'Netherlands', 211: 'Belgium', 212: 'Luxembourg', 220: 'France',
    225: 'Switzerland', 230: 'Spain', 235: 'Portugal', 290: 'Poland', 291: 'Free City of Danzig',
    300: 'Austria-Hungary', 305: 'Austria', 310: 'Hungary', 315: 'Czechoslovakia', 316: 'Czech Republic',
    317: 'Slovakia', 325: 'Italy', 338: 'Malta', 339: 'Albania', 340: 'Serbia', 341: 'Montenegro', 344: 'Croatia',
    346: 'Bosnia and Herzegovina', 347: 'Kosovo', 349: 'Slovenia', 350: 'Greece', 352: 'Cyprus', 355: 'Bulgaria',
    359: 'Moldova', 360: 'Romania', 366: 'Estonia', 367: 'Latvia', 368: 'Lithuania', 369: 'Ukraine', 370: 'Belarus',
    371: 'Armenia', 372: 'Georgia', 373: 'Azerbaijan', 375: 'Finland', 380: 'Sweden', 385: 'Norway', 390: 'Denmark',
    395: 'Iceland', 402: 'Cape Verde', 420: 'Gambia', 430: 'French West Africa', 433: 'Senegal', 435: 'Mauritania',
    436: 'Niger', 450: 'Liberia', 451: 'Sierra Leone', 462: 'British Togoland', 470: 'Kamerun',
    472: 'British Cameroons', 475: 'Nigeria', 481: 'Gabon', 483: 'Chad', 500: 'Uganda', 511: 'Zanzibar',
    515: 'Ruanda-Urundi', 516: 'Burundi', 517: 'Rwanda', 520: 'Somalia', 521: 'British Somaliland',
    530: 'Ethiopia', 531: 'Eritrea', 540: 'Angola', 541: 'Mozambique',
    550: 'Federation of Rhodesia and Nyasaland', 561: 'Cape Colony', 562: 'Natal', 581: 'Comoros', 585: 'Réunion',
    590: 'Mauritius', 602: 'Spanish Morocco', 609: 'Spanish Sahara', 610: 'Spanish West Africa', 615: 'Algeria',
    616: 'Tunisia', 620: 'Libya', 626: 'South Sudan', 645: 'Iraq', 651: 'Egypt', 652: 'Syria', 660: 'Lebanon',
    665: 'Mandatory Palestine', 666: 'Israel', 670: 'Saudi Arabia', 680: 'South Yemen', 681: 'Aden',
    690: 'Kuwait', 692: 'Bahrain', 694: 'Qatar', 700: 'Afghanistan', 701: 'Turkmenistan', 702: 'Tajikistan',
    703: 'Kyrgyzstan', 704: 'Uzbekistan', 705: 'Kazakhstan', 711: 'Tibet', 712: 'Mongolia', 713: 'Taiwan',
    730: 'Korea', 740: 'Japan', 760: 'Bhutan', 770: 'Pakistan', 771: 'Bangladesh', 781: 'Maldives', 790: 'Nepal',
    811: 'Cambodia', 812: 'Laos', 817: 'South Vietnam', 821: 'Federated Malay States',
    822: 'Unfederated Malay States', 823: 'North Borneo', 824: 'Sarawak', 827: 'Straits Settlements',
    830: 'Singapore', 835: 'Brunei', 840: 'Philippines', 900: 'Australia', 901: 'New South Wales',
    902: 'Western Australia', 903: 'South Australia', 904: 'Victoria', 905: 'Queensland', 906: 'Tasmania',
    920: 'New Zealand', 930: 'New Caledonia', 950: 'Fiji', 960: 'French Polynesia', 1201: 'Inini',
    3461: 'Bosnia', 3462: 'Herzegovina', 4781: 'Lagos', 4782: 'Oil Rivers Protectorate', 4783: 'Southern Nigeria',
    4784: 'Northern Nigeria', 5200: 'Italian Somaliland', 5518: 'North-Eastern Rhodesia',
    5519: 'North-Western Rhodesia', 5612: 'British Bechuanaland', 6021: 'Spanish Morocco (southern zone)',
    6511: 'Gaza Strip', 6631: 'West Bank', 6801: 'Federation of South Arabia', 6812: 'East Aden Protectorate',
    7020: 'Emirate of Bukhara', 7030: 'Khanate of Khiva', 7351: 'Karafuto (South Sakhalin)',
    7506: 'Jammu and Kashmir', 7708: 'Azad Kashmir', 8201: 'Perak', 8202: 'Selangor', 8203: 'Pahang',
    9401: 'German Solomon Islands', 940: 'Solomon Islands',
}

# gwcode -> [(first date with this name, name), ...] (sorted). Applied on top of BASE; the feature is split at
# each date that falls inside a CShapes period.
NAMES_BY_DATE = {
    80: [('1886-01-01', 'British Honduras'), ('1973-06-01', 'Belize')],
    110: [('1886-01-01', 'British Guiana'), ('1966-05-26', 'Guyana')],
    115: [('1886-01-01', 'Dutch Guiana'), ('1975-11-25', 'Suriname')],
    205: [('1921-12-06', 'Irish Free State'), ('1937-12-29', 'Ireland')],
    255: [('1886-01-01', 'German Empire'), ('1918-11-09', 'Germany')],
    260: [('1945-05-08', 'Allied-occupied Germany (western zones)'), ('1949-09-21', 'West Germany'), ('1990-10-03', 'Germany')],
    265: [('1945-05-08', 'Soviet-occupied Germany'), ('1949-10-05', 'East Germany')],
    343: [('1991-11-20', 'Macedonia'), ('2019-02-12', 'North Macedonia')],
    345: [('1918-12-01', 'Kingdom of Serbs, Croats and Slovenes'), ('1929-10-03', 'Yugoslavia'),
          ('1992-04-27', 'Yugoslavia (Serbia and Montenegro)'), ('2003-02-04', 'Serbia and Montenegro')],
    380: [('1886-01-01', 'Sweden–Norway'), ('1905-08-26', 'Sweden')],
    365: [('1886-01-01', 'Russian Empire'), ('1917-03-15', 'Russia'), ('1922-12-30', 'Soviet Union'), ('1991-12-26', 'Russia')],
    404: [('1886-01-01', 'Portuguese Guinea'), ('1974-09-10', 'Guinea-Bissau')],
    411: [('1886-01-01', 'Spanish Guinea'), ('1968-10-12', 'Equatorial Guinea')],
    432: [('1905-01-01', 'French Sudan'), ('1960-09-22', 'Mali')],
    434: [('1895-01-01', 'Dahomey'), ('1975-11-30', 'Benin')],
    437: [('1889-01-10', 'Ivory Coast'), ('1960-08-07', "Côte d'Ivoire")],
    438: [('1894-01-01', 'French Guinea'), ('1958-10-02', 'Guinea')],
    439: [('1919-03-01', 'Upper Volta'), ('1984-08-04', 'Burkina Faso')],
    452: [('1886-01-01', 'Gold Coast'), ('1957-03-06', 'Ghana')],
    460: [('1886-01-01', 'Togoland')],
    461: [('1922-07-20', 'French Togoland'), ('1960-04-27', 'Togo')],
    471: [('1919-06-28', 'French Cameroons'), ('1960-01-01', 'Cameroon')],
    482: [('1906-02-11', 'Ubangi-Shari'), ('1960-08-13', 'Central African Republic')],
    484: [('1886-01-01', 'French Congo'), ('1906-02-11', 'Middle Congo'), ('1960-08-15', 'Republic of the Congo')],
    490: [('1886-01-01', 'Congo Free State'), ('1908-10-18', 'Belgian Congo'), ('1960-06-30', 'Congo (Léopoldville)'),
          ('1971-10-27', 'Zaire'), ('1997-05-17', 'DR Congo')],
    501: [('1888-10-15', 'British East Africa'), ('1920-07-23', 'Kenya')],
    510: [('1891-01-01', 'German East Africa'), ('1916-10-09', 'Tanganyika'), ('1964-04-26', 'Tanzania')],
    522: [('1886-01-01', 'French Somaliland'), ('1967-07-05', 'French Territory of the Afars and the Issas'), ('1977-06-27', 'Djibouti')],
    551: [('1911-08-18', 'Northern Rhodesia'), ('1964-01-22', 'Zambia')],
    552: [('1889-01-01', 'Southern Rhodesia'), ('1965-11-11', 'Rhodesia'), ('1980-04-18', 'Zimbabwe')],
    553: [('1891-06-10', 'Nyasaland'), ('1964-07-06', 'Malawi')],
    560: [('1910-05-31', 'Union of South Africa'), ('1961-05-31', 'South Africa')],
    563: [('1886-01-01', 'South African Republic (Transvaal)'), ('1902-05-31', 'Transvaal Colony')],
    564: [('1886-01-01', 'Orange Free State'), ('1902-05-31', 'Orange River Colony')],
    565: [('1886-01-01', 'German South West Africa'), ('1915-08-16', 'South West Africa'), ('1990-03-21', 'Namibia')],
    570: [('1886-01-01', 'Basutoland'), ('1966-10-04', 'Lesotho')],
    571: [('1886-01-01', 'Bechuanaland Protectorate'), ('1966-09-30', 'Botswana')],
    572: [('1895-02-21', 'Swaziland'), ('2018-04-19', 'Eswatini')],
    580: [('1886-01-01', 'Kingdom of Madagascar'), ('1896-08-06', 'Madagascar')],
    600: [('1886-01-01', 'Morocco'), ('1912-11-27', 'French Morocco'), ('1956-03-02', 'Morocco')],
    625: [('1899-01-19', 'Anglo-Egyptian Sudan'), ('1956-01-01', 'Sudan')],
    630: [('1886-01-01', 'Persia'), ('1935-03-21', 'Iran')],
    640: [('1886-01-01', 'Ottoman Empire'), ('1923-10-14', 'Turkey')],
    663: [('1920-04-26', 'Transjordan'), ('1949-04-26', 'Jordan')],
    678: [('1918-10-30', 'Kingdom of Yemen'), ('1962-09-26', 'North Yemen'), ('1990-05-22', 'Yemen')],
    696: [('1892-03-08', 'Trucial States'), ('1971-12-02', 'United Arab Emirates')],
    698: [('1886-01-01', 'Muscat and Oman'), ('1970-08-09', 'Oman')],
    710: [('1886-01-01', 'Qing Empire'), ('1912-01-01', 'China')],
    731: [('1945-08-15', 'Soviet-occupied Korea'), ('1948-09-09', 'North Korea')],
    732: [('1945-08-15', 'US-occupied Korea'), ('1948-08-15', 'South Korea')],
    750: [('1886-01-01', 'British India'), ('1947-08-15', 'India')],
    775: [('1937-04-01', 'Burma'), ('1989-06-18', 'Myanmar')],
    780: [('1886-01-01', 'Ceylon'), ('1972-05-22', 'Sri Lanka')],
    800: [('1886-01-01', 'Siam'), ('1939-06-24', 'Thailand')],
    815: [('1886-01-01', 'Annam and Tonkin'), ('1893-01-02', 'Vietnam (French Indochina)')],
    816: [('1954-05-01', 'North Vietnam'), ('1975-05-01', 'Vietnam')],
    820: [('1946-04-01', 'Malaya'), ('1963-09-16', 'Malaysia')],
    850: [('1886-01-01', 'Dutch East Indies'), ('1945-08-17', 'Indonesia')],
    851: [('1949-12-29', 'Netherlands New Guinea'), ('1962-08-15', 'West New Guinea (UNTEA)'), ('1963-05-01', 'West Irian')],
    860: [('1886-01-01', 'Portuguese Timor'), ('2002-05-20', 'East Timor')],
    910: [('1949-07-01', 'Territory of Papua and New Guinea'), ('1975-09-16', 'Papua New Guinea')],
    911: [('1886-01-01', 'British New Guinea'), ('1905-11-16', 'Territory of Papua')],
    912: [('1886-01-01', 'German New Guinea'), ('1914-11-11', 'New Guinea (Australian occupation)'), ('1920-06-28', 'Territory of New Guinea')],
    940: [('1893-03-15', 'British Solomon Islands'), ('1978-07-07', 'Solomon Islands')],
}

OWNER_NAME = {0: 'League of Nations', 1: 'United Nations', 2: 'United States', 200: 'United Kingdom', 210: 'Netherlands',
              211: 'Belgium', 220: 'France', 230: 'Spain', 235: 'Portugal', 325: 'Italy', 300: 'Austria-Hungary',
              390: 'Denmark', 563: 'South African Republic (Transvaal)', 651: 'Egypt', 663: 'Jordan', 740: 'Japan',
              750: 'India', 770: 'Pakistan', 850: 'Indonesia', 900: 'Australia'}


def cs_name_on(gw, date):
    """Common name of CShapes gwcode `gw` on `date` (YYYY-MM-DD)."""
    if gw in NAMES_BY_DATE:
        name = NAMES_BY_DATE[gw][0][1]
        for d, n in NAMES_BY_DATE[gw]:
            if d <= date:
                name = n
        return name
    return BASE.get(gw)


def owner_name(owner, date):
    if owner in OWNER_NAME:
        return OWNER_NAME[owner]
    if owner == 255:
        return 'German Empire' if date < '1918-11-09' else 'Germany'
    if owner == 560:
        return 'Union of South Africa' if date < '1961-05-31' else 'South Africa'
    return cs_name_on(owner, date) or ''


# Corrections to CShapes status/ownership (documented in WORLD_HIST_NOTES.md):
#   Transvaal and Orange Free State became British colonies by the Treaty of Vereeniging (1902-05-31);
#   CShapes keeps both "independent" until the Union of 1910.
SUB_OVERRIDE = {  # (gwcode, first day, last day): sub
    (563, '1902-05-31', '1910-05-30'): 'United Kingdom', (564, '1902-05-31', '1910-05-30'): 'United Kingdom',
    (260, '1945-05-08', '1949-09-20'): 'Allied occupation (US, UK, France)',
}


def cs_periods(gw, country_name, start, end, status, owner):
    """Split one CShapes 2.0 country-period at name changes. Returns [(from, to, name, sub)]."""
    cuts = [d for d, _ in NAMES_BY_DATE.get(gw, []) if start < d <= end]
    bounds = [start] + cuts
    out = []
    for i, b in enumerate(bounds):
        e = end if i == len(bounds) - 1 else _prev_day(bounds[i + 1])
        name = cs_name_on(gw, b) or country_name
        sub = ''
        if status != 'independent' and owner not in (gw, None):
            sub = owner_name(owner, b)
        for (g2, d0, d1), s2 in SUB_OVERRIDE.items():
            if g2 == gw and d0 <= b <= d1:
                sub = s2
        out.append((b, e, name, sub))
    return out


def _prev_day(d):
    import datetime as dt
    return (dt.date.fromisoformat(d) - dt.timedelta(days=1)).isoformat()


# ------------------------------------------------------------------------------------------ Natural Earth fills
# Territories absent from CShapes 2.0 for (part of) 1886-2026. Each entry: NE 1:50m country name (or
# (name, bbox) to take only the parts inside lon0,lat0,lon1,lat1), then [(from, to, display name, sub)].
# Geometry used = NE shape minus every CShapes polygon valid during the interval (so fills never overlap).
E = '2026-12-31'
UK, FR, NL, US, DK, NZ, AU, JP, PT, ES, DE = ('United Kingdom', 'France', 'Netherlands', 'United States', 'Denmark',
                                              'New Zealand', 'Australia', 'Japan', 'Portugal', 'Spain', 'German Empire')
FILLS = [
    ('Greenland', [('1886-01-01', E, 'Greenland', DK)]),
    (('Norway', (0, 74, 40, 81)), [('1925-08-14', E, 'Svalbard', 'Norway')]),
    (('Russia', (40, 79, 66, 82.5)), [('1926-04-15', '1991-12-25', 'Franz Josef Land', 'Soviet Union'), ('1991-12-26', E, 'Franz Josef Land', 'Russia')]),
    (('Russia', (88, 77.5, 108, 81.5)), [('1926-04-15', '1991-12-25', 'Severnaya Zemlya', 'Soviet Union'), ('1991-12-26', E, 'Severnaya Zemlya', 'Russia')]),
    ('Falkland Islands', [('1886-01-01', E, 'Falkland Islands', UK)]),
    ('South Georgia', [('1886-01-01', E, 'South Georgia', UK)]),
    ('French Southern and Antarctic Lands', [('1893-01-01', E, 'French Southern Lands', FR)]),
    ('Heard Island and McDonald Islands', [('1910-01-01', '1947-12-25', 'Heard Island', UK), ('1947-12-26', E, 'Heard Island', AU)]),
    ('Faroe Islands', [('1886-01-01', E, 'Faroe Islands', DK)]),
    ('Isle of Man', [('1886-01-01', E, 'Isle of Man', UK)]),
    ('Jersey', [('1886-01-01', E, 'Jersey', UK)]),
    ('Guernsey', [('1886-01-01', E, 'Guernsey', UK)]),
    ('Andorra', [('1886-01-01', E, 'Andorra', '')]),
    ('Liechtenstein', [('1886-01-01', E, 'Liechtenstein', '')]),
    ('Monaco', [('1886-01-01', E, 'Monaco', '')]),
    ('San Marino', [('1886-01-01', E, 'San Marino', '')]),
    ('Bermuda', [('1886-01-01', E, 'Bermuda', UK)]),
    ('Cayman Islands', [('1886-01-01', E, 'Cayman Islands', UK)]),
    ('Turks and Caicos Islands', [('1886-01-01', E, 'Turks and Caicos Islands', UK)]),
    ('British Virgin Islands', [('1886-01-01', E, 'British Virgin Islands', UK)]),
    ('Anguilla', [('1886-01-01', E, 'Anguilla', UK)]),
    ('Montserrat', [('1886-01-01', E, 'Montserrat', UK)]),
    ('Antigua and Barbuda', [('1886-01-01', '1981-10-31', 'Antigua', UK), ('1981-11-01', E, 'Antigua and Barbuda', '')]),
    ('Saint Kitts and Nevis', [('1886-01-01', '1983-09-18', 'Saint Kitts and Nevis', UK), ('1983-09-19', E, 'Saint Kitts and Nevis', '')]),
    ('Dominica', [('1886-01-01', '1978-11-02', 'Dominica', UK), ('1978-11-03', E, 'Dominica', '')]),
    ('Saint Lucia', [('1886-01-01', '1979-02-21', 'Saint Lucia', UK), ('1979-02-22', E, 'Saint Lucia', '')]),
    ('Saint Vincent and the Grenadines', [('1886-01-01', '1979-10-26', 'Saint Vincent', UK), ('1979-10-27', E, 'Saint Vincent and the Grenadines', '')]),
    ('Grenada', [('1886-01-01', '1974-02-06', 'Grenada', UK), ('1974-02-07', E, 'Grenada', '')]),
    ('United States Virgin Islands', [('1886-01-01', '1917-03-30', 'Danish West Indies', DK), ('1917-03-31', E, 'US Virgin Islands', US)]),
    ('Aruba', [('1886-01-01', E, 'Aruba', NL)]),
    ('Curaçao', [('1886-01-01', E, 'Curaçao', NL)]),
    ('Sint Maarten', [('1886-01-01', E, 'Sint Maarten', NL)]),
    ('Saint Martin', [('1886-01-01', E, 'Saint-Martin', FR)]),
    ('Saint Barthélemy', [('1886-01-01', E, 'Saint-Barthélemy', FR)]),
    ('Saint Pierre and Miquelon', [('1886-01-01', E, 'Saint-Pierre and Miquelon', FR)]),
    ('Samoa', [('1886-01-01', '1899-12-01', 'Samoa', ''), ('1899-12-02', '1914-08-28', 'German Samoa', DE),
               ('1914-08-29', '1961-12-31', 'Western Samoa', NZ), ('1962-01-01', '1997-07-03', 'Western Samoa', ''),
               ('1997-07-04', E, 'Samoa', '')]),
    ('American Samoa', [('1886-01-01', '1899-12-01', 'Samoa', ''), ('1899-12-02', E, 'American Samoa', US)]),
    ('Tonga', [('1886-01-01', '1900-05-17', 'Tonga', ''), ('1900-05-18', '1970-06-03', 'Tonga', UK), ('1970-06-04', E, 'Tonga', '')]),
    ('Kiribati', [('1892-05-27', '1979-07-11', 'Gilbert Islands', UK), ('1979-07-12', E, 'Kiribati', '')]),
    ('Nauru', [('1888-10-02', '1914-11-05', 'Nauru', DE), ('1914-11-06', '1968-01-30', 'Nauru', AU), ('1968-01-31', E, 'Nauru', '')]),
    ('Marshall Islands', [('1886-01-01', '1914-09-29', 'Marshall Islands', DE), ('1914-09-30', '1944-01-31', 'Marshall Islands', JP),
                          ('1944-02-01', '1986-10-20', 'Marshall Islands', US), ('1986-10-21', E, 'Marshall Islands', '')]),
    ('Micronesia', [('1886-01-01', '1899-06-29', 'Caroline Islands', ES), ('1899-06-30', '1914-10-06', 'Caroline Islands', DE),
                    ('1914-10-07', '1944-12-31', 'Caroline Islands', JP), ('1945-01-01', '1986-11-02', 'Caroline Islands', US),
                    ('1986-11-03', E, 'Micronesia', '')]),
    ('Palau', [('1886-01-01', '1899-06-29', 'Palau', ES), ('1899-06-30', '1914-10-06', 'Palau', DE),
               ('1914-10-07', '1944-12-31', 'Palau', JP), ('1945-01-01', '1994-09-30', 'Palau', US), ('1994-10-01', E, 'Palau', '')]),
    ('Northern Mariana Islands', [('1886-01-01', '1899-06-29', 'Mariana Islands', ES), ('1899-06-30', '1914-10-13', 'Mariana Islands', DE),
                                  ('1914-10-14', '1944-08-09', 'Mariana Islands', JP), ('1944-08-10', E, 'Northern Mariana Islands', US)]),
    ('Guam', [('1886-01-01', '1898-12-09', 'Guam', ES), ('1898-12-10', E, 'Guam', US)]),
    ('Cook Islands', [('1888-09-27', '1901-06-10', 'Cook Islands', UK), ('1901-06-11', E, 'Cook Islands', NZ)]),
    ('Niue', [('1900-04-21', '1901-06-10', 'Niue', UK), ('1901-06-11', E, 'Niue', NZ)]),
    ('Wallis and Futuna', [('1887-11-19', E, 'Wallis and Futuna', FR)]),
    ('Pitcairn Islands', [('1886-01-01', E, 'Pitcairn Islands', UK)]),
    ('Norfolk Island', [('1886-01-01', '1913-12-31', 'Norfolk Island', UK), ('1914-01-01', E, 'Norfolk Island', AU)]),
    ('Vanuatu', [('1906-10-20', '1980-07-29', 'New Hebrides', 'United Kingdom and France'), ('1980-07-30', E, 'Vanuatu', '')]),
    ('French Polynesia', [('1886-01-01', E, 'French Polynesia', FR)]),
    ('São Tomé and Príncipe', [('1886-01-01', '1975-07-11', 'São Tomé and Príncipe', PT), ('1975-07-12', E, 'São Tomé and Príncipe', '')]),
    ('Seychelles', [('1886-01-01', '1976-06-28', 'Seychelles', UK), ('1976-06-29', E, 'Seychelles', '')]),
    ('Comoros', [('1886-01-01', E, 'Comoros', FR)]),
    ('Saint Helena, Ascension and Tristan da Cunha', [('1886-01-01', E, 'Saint Helena', UK)]),
    ('British Indian Ocean Territory', [('1886-01-01', E, 'Chagos Archipelago', UK)]),
    ('Hong Kong', [('1886-01-01', '1997-06-30', 'Hong Kong', UK), ('1997-07-01', E, 'Hong Kong', 'China')]),
    ('Macau', [('1887-12-01', '1999-12-19', 'Macau', PT), ('1999-12-20', E, 'Macau', 'China')]),
    ('Bahrain', [('1886-01-01', '1971-08-14', 'Bahrain', UK)]),
    ('Kuwait', [('1899-01-23', '1961-06-18', 'Kuwait', UK)]),
    ('Qatar', [('1886-01-01', '1916-11-02', 'Qatar', '')]),
]
# Kingdom of Hawaii (CShapes maps Hawaii only from US annexation, 1898-07-06): CShapes' own Hawaii polygon.
HAWAII = [('1886-01-01', '1893-01-16', 'Kingdom of Hawaii', ''), ('1893-01-17', '1894-07-03', 'Provisional Government of Hawaii', ''),
          ('1894-07-04', '1898-07-05', 'Republic of Hawaii', '')]
