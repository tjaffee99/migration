"""Origin registry and label crosswalk.

Every source reports origins in its own vocabulary ("Canada & Newfoundland", "U.S.S.R.",
"Northern Irish (Ulster)", "Bight of Biafra"...). This module maps each source label to one
origin unit with a stable id, a display name, a region group and the present-day ISO3 codes
used to shade it on the world map.
"""
import csv
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Region groups, in stacking order. slot = categorical colour slot (9 = neutral "other").
GROUPS = [
    {"id": "bri", "name": "Britain & Ireland", "short": "Britain & Ireland", "slot": 1},
    {"id": "nwe", "name": "Northern & Western Europe", "short": "N. & W. Europe", "slot": 2},
    {"id": "see", "name": "Southern & Eastern Europe", "short": "S. & E. Europe", "slot": 3},
    {"id": "afr", "name": "Africa", "short": "Africa", "slot": 4},
    {"id": "asi", "name": "Asia & Middle East", "short": "Asia & Mid. East", "slot": 5},
    {"id": "mex", "name": "Mexico", "short": "Mexico", "slot": 6},
    {"id": "lat", "name": "Caribbean & Latin America", "short": "Carib. & Lat. Am.", "slot": 7},
    {"id": "can", "name": "Canada", "short": "Canada", "slot": 8},
    {"id": "oth", "name": "Oceania & not specified", "short": "Oceania & other", "slot": 9},
]

NWE = {"DEU", "NLD", "BEL", "LUX", "FRA", "CHE", "NOR", "SWE", "DNK", "ISL", "FIN", "LIE", "MCO", "FRO", "ALA", "SJM", "GRL"}
BRI = {"GBR", "IRL", "IMN", "JEY", "GGY", "GIB"}
SEE = {"ITA", "ESP", "PRT", "GRC", "AUT", "HUN", "CZE", "SVK", "POL", "RUS", "UKR", "BLR", "LTU", "LVA", "EST", "MDA",
       "ROU", "BGR", "SRB", "HRV", "SVN", "BIH", "MNE", "MKD", "ALB", "XKX", "MLT", "AND", "SMR", "VAT"}

# Display names that read better than the geometry file's.
NAME_OVERRIDES = {
    "TUR": "Turkey", "CIV": "Côte d'Ivoire", "COD": "DR Congo", "COG": "Republic of the Congo", "CZE": "Czechia",
    "KOR": "South Korea", "PRK": "North Korea", "MMR": "Myanmar (Burma)", "MKD": "North Macedonia",
    "GBR": "United Kingdom (not specified)", "CPV": "Cabo Verde", "SWZ": "Eswatini", "VCT": "St. Vincent & Grenadines",
    "KNA": "St. Kitts & Nevis", "LCA": "St. Lucia", "TTO": "Trinidad & Tobago", "ATG": "Antigua & Barbuda",
    "BIH": "Bosnia & Herzegovina", "PSE": "Palestine", "USA": "United States",
}
SHORT = {"United Kingdom (not specified)": "UK", "Russia / Soviet Union": "Russia/USSR", "Dominican Republic": "Dominican Rep.",
         "Austria-Hungary": "Austria-Hung.", "Czechoslovakia": "Czechoslov.", "Philippines": "Philippines",
         "Netherlands": "Netherlands", "El Salvador": "El Salvador", "Canada": "Canada"}

# Units that are not single present-day countries.
CUSTOM = {
    # British Isles
    "ENG": ("England", "bri", ["GBR"]),
    "SCT": ("Scotland", "bri", ["GBR"]),
    "WLS": ("Wales", "bri", ["GBR"]),
    "NIR": ("Northern Ireland", "bri", ["GBR"]),
    # historical European states and unions
    "AUH": ("Austria-Hungary", "see", ["AUT", "HUN", "CZE", "SVK", "SVN", "HRV", "BIH"]),
    "CSK": ("Czechoslovakia", "see", ["CZE", "SVK"]),
    "YUG": ("Yugoslavia", "see", ["SVN", "HRV", "BIH", "SRB", "MNE", "MKD", "XKX"]),
    "SUN": ("Russia / Soviet Union", "see", ["RUS", "UKR", "BLR", "LTU", "LVA", "EST", "MDA", "GEO", "ARM", "AZE",
                                             "KAZ", "UZB", "TKM", "KGZ", "TJK"]),
    "NOS": ("Norway & Sweden", "nwe", ["NOR", "SWE"]),
    "SCG": ("Serbia & Montenegro", "see", ["SRB", "MNE", "XKX"]),
    "OTE": ("Turkey in Europe", "see", ["TUR"]),
    "OTA": ("Turkey in Asia (Ottoman)", "asi", ["TUR", "SYR", "LBN", "ISR", "PSE", "JOR", "IRQ"]),
    "HAW": ("Hawaii (before annexation)", "oth", []),
    # forced migration: SlaveVoyages embarkation regions
    "AF_SEN": ("Senegambia", "afr", ["SEN", "GMB", "GNB", "MLI"]),
    "AF_SLE": ("Sierra Leone coast", "afr", ["SLE", "GIN"]),
    "AF_WIN": ("Windward Coast", "afr", ["LBR", "CIV"]),
    "AF_GOL": ("Gold Coast", "afr", ["GHA"]),
    "AF_BEN": ("Bight of Benin", "afr", ["TGO", "BEN", "NGA"]),
    "AF_BIA": ("Bight of Biafra", "afr", ["NGA", "CMR", "GNQ", "GAB"]),
    "AF_WCA": ("West Central Africa", "afr", ["COG", "COD", "AGO"]),
    "AF_SEA": ("Southeast Africa", "afr", ["MOZ", "MDG", "TZA"]),
    "AF_CAR": ("Enslaved, via the Caribbean", "afr", []),
    # residual categories
    "XEU": ("Europe, other or not specified", "oth", []),
    "XNW": ("Other Northern & Western Europe", "nwe", []),
    "XSE": ("Other Southern & Eastern Europe", "see", []),
    "XAS": ("Asia, other or not specified", "asi", []),
    "XAF": ("Africa, other or not specified", "afr", []),
    "XLA": ("Latin America, other or not specified", "lat", []),
    "XCB": ("Caribbean, other or not specified", "lat", []),
    "XNA": ("Other North America", "oth", []),
    "XOC": ("Oceania, other or not specified", "oth", []),
    "XNS": ("Not specified", "oth", []),
    "XNT": ("Not tabulated by country (nonwhite)", "oth", []),
}

FORCED = {k for k in CUSTOM if k.startswith("AF_")}

# Where an origin's arrow starts on the map (lon, lat). Countries default to the centre of their
# largest polygon; these override it with the region most emigrants left from, and place the
# units that aren't single countries.
ANCHORS = {
    "ENG": (-1.5, 52.6), "SCT": (-4.2, 56.6), "WLS": (-3.7, 52.3), "NIR": (-6.6, 54.6), "GBR": (-2.0, 53.5),
    "AUH": (17.5, 48.0), "CSK": (16.6, 49.4), "YUG": (19.5, 44.2), "SCG": (20.5, 43.8), "SUN": (28.0, 53.5),
    "RUS": (37.6, 55.8), "NOS": (13.0, 61.0), "OTE": (27.5, 41.4), "OTA": (36.5, 36.5), "HAW": (-157.0, 20.6),
    "CAN": (-84.0, 50.5), "MEX": (-101.5, 20.5), "USA": None,
    "AF_SEN": (-15.5, 14.0), "AF_SLE": (-12.5, 9.0), "AF_WIN": (-8.5, 6.2), "AF_GOL": (-1.5, 6.8),
    "AF_BEN": (2.4, 7.2), "AF_BIA": (7.8, 5.2), "AF_WCA": (14.5, -6.5), "AF_SEA": (36.5, -16.0),
    "AF_CAR": (-70.0, 18.0),
    "XEU": (12.0, 50.0), "XNW": (6.0, 51.0), "XSE": (22.0, 44.0), "XAS": (100.0, 28.0), "XAF": (20.0, 6.0),
    "XLA": (-62.0, -12.0), "XCB": (-71.0, 18.5), "XNA": (-64.0, 46.0), "XOC": (160.0, -12.0),
}
MAP_CUT = 90.0  # the page centres the world map on 90°W, so its edge runs along 90°E
CENTRAL_AMERICA = {"BLZ", "GTM", "HND", "SLV", "NIC", "CRI", "PAN"}

NOTES = {
    "SUN": "Reported as Russia before 1917 and as the Soviet Union until 1991; covers the present-day successor states.",
    "AUH": "Reported as one empire until 1918 in some years; split into Austria and Hungary in others.",
    "ENG": "Before 1820, includes the English share of British arrivals estimated by historians.",
    "IRL": "The whole island before 1925; includes Ulster Scots-Irish in the colonial era.",
    "DEU": "German states before 1871.",
    "AF_CAR": "People already enslaved in the Caribbean and shipped on to North America. Most were born in Africa.",
    "XNT": "The 1940 and 1950 censuses tabulated country of birth for white residents only.",
}


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.lower().strip()
    s = re.sub(r"\s+\d+(/\s*\d+/?)*\s*$", "", s)  # trailing footnote numbers like "17/ 18/"
    s = re.sub(r"\s*\((total|former|eire|total\)|derived)\)", "", s)
    s = s.replace("&", "and").replace(".", "").replace(",", "").replace("'", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


# label -> id (normalized). Year-dependent cases are handled in resolve().
ALIASES = {
    "england": "ENG", "scotland": "SCT", "wales": "WLS", "northern ireland": "NIR", "england and wales": "ENG",
    "great britain": "GBR", "great britain nec": "GBR", "united kingdom": "GBR", "united kingdom inc crown dependencies": "GBR",
    "united kingdom excluding england and scotland": "GBR", "british (chesapeake immigrants)": "ENG", "british": "ENG",
    "english": "ENG", "english (great migration)": "ENG", "european (mostly british)": "ENG", "scots": "SCT", "welsh": "WLS",
    "convicts and prisoners (mostly scottish)": "SCT",
    "ireland": "IRL", "northern irish (ulster)": "IRL", "southern irish": "IRL",
    "germans": "DEU", "germany": "DEU", "german-speaking": "DEU",
    "new netherland colonists (dutch and other europeans)": "NLD",
    "other europeans (mostly swedish and german)": "XNW", "other europeans": "XNW", "all european origins": "XEU",
    "acadians (french)": "FRA", "canary islanders (islenos)": "ESP",
    "austria-hungary": "AUH", "czechoslovakia": "CSK", "czechoslovakia includes czech republic and slovakia": "CSK",
    "yugoslavia": "YUG", "yugoslavia remainder": "YUG",
    "soviet union": "SUN", "ussr": "SUN", "ussr nec": "SUN",
    "norway-sweden": "NOS", "turkey in europe": "OTE", "turkey in asia": "OTA", "sandwich islands (hawaii)": "HAW",
    "canada and newfoundland": "CAN", "canada-french": "CAN", "canada-other": "CAN", "newfoundland": "CAN", "canada": "CAN",
    "azores": "PRT", "azores islands": "PRT", "portugal remainder": "PRT", "portugal": "PRT",
    "china excluding hong kong and taiwan": "CHN", "china peoples republic": "CHN", "china": "CHN",
    "korea": "KOR", "korea south": "KOR", "korea north": "PRK",
    "burma": "MMR", "burma (myanmar)": "MMR", "ivory coast": "CIV", "ivory coast (cote divoire)": "CIV", "cote divoire": "CIV",
    "zaire (democratic republic of congo)": "COD", "democratic republic of congo (zaire)": "COD", "congo democratic republic": "COD",
    "congo republic": "COG", "congo": "COG", "columbia": "COL", "cape verde": "CPV", "cabo verde": "CPV",
    "cape verde (1960-1970: other atlantic islands)": "CPV", "rumania": "ROU", "macedonia": "MKD",
    "north macedonia (macedonia)": "MKD", "samoa (western samoa)": "WSM", "turmenistan": "TKM", "kosovo": "XKX",
    "st kitts-nevis": "KNA", "saint kitts and nevis": "KNA", "st lucia": "LCA", "st vincent and the grenadines": "VCT",
    "saint vincent and the grenadines": "VCT", "trinidad and tobago": "TTO", "antigua and barbuda": "ATG",
    "virgin islands british": "VGB", "saint martin (french)": "MAF", "netherlands antilles": "CUW", "curacao": "CUW",
    "palestine": "PSE", "syria": "SYR", "laos": "LAO", "vietnam": "VNM", "iran": "IRN", "russia": "RUS", "turkey": "TUR",
    "czechia": "CZE", "czech republic": "CZE", "eswatini": "SWZ", "swaziland": "SWZ", "brunei": "BRN", "macau": "MAC",
    "micronesia federated states of": "FSM", "bosnia and herzegovina": "BIH", "moldova": "MDA", "tanzania": "TZA",
    "bahamas": "BHS", "gambia": "GMB", "korea (total)": "KOR",
    "united kingdom (inc crown dependencies)": "GBR", "czechoslovakia (includes czech republic and slovakia)": "CSK",
    "micronesia federated states": "FSM", "micronesia (incl federated states of micronesia)": "FSM",
    "germany east": "DEU", "germany west": "DEU", "gernany west": "DEU", "yemen (aden)": "YEM", "yemen (sanaa)": "YEM",
    "gambia the": "GMB", "guinea bissau": "GNB", "st helena": "SHN", "antigua-barbuda": "ATG", "bahamas the": "BHS",
    "us virgin islands": "VIR", "bosnia-herzegovina": "BIH", "wallis and futuna islands": "WLF",
    "st pierre and miquelon": "SPM", "slovak republic": "SVK", "cocos islands": "CCK", "pitcairn island": "PCN",
    "saint kitts-nevis": "KNA", "serbia and montenegro": "SCG", "eswatini (formerly swaziland)": "SWZ",
    "north macedonia (formerly macedonia)": "MKD",
    "russia and lithuania": "SUN", "jugo-slavia": "YUG",
    "west indies": "XCB", "atlantic islands": "XAF", "born at sea": "XNS",
    "foreign born races other than white (country of birth not tabulated)": "XNT",
}

RESIDUAL_BY_PARENT = [
    (r"northern and western europe|northern europe|western europe|scandinavia|low countries", "XNW"),
    (r"southern and eastern europe|southern europe|eastern europe|yugoslavia|soviet", "XSE"),
    (r"europe", "XEU"),
    (r"asia|middle east", "XAS"),
    (r"africa", "XAF"),
    (r"caribbean", "XCB"),
    (r"central america|south america|latin america|^america|americas", "XLA"),
    (r"northern america|north america", "XNA"),
    (r"oceania|pacific|melanesia|micronesia|polynesia|australia", "XOC"),
]


def residual_for(label, parent):
    text = (label + " " + parent).lower()
    for pat, rid in RESIDUAL_BY_PARENT:
        if re.search(pat, text):
            return rid
    return "XNS"


class Registry:
    def __init__(self):
        self.units = {}
        self.unmatched = {}
        with open(ROOT / "web" / "geo" / "world_countries.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.iso_rows = {r["iso3"]: r for r in rows if r["iso3"]}
        self.by_name = {norm(r["name"]): r["iso3"] for r in rows if r["iso3"]}

    def group_for_iso(self, iso):
        r = self.iso_rows.get(iso, {})
        cont, sub = r.get("continent", ""), r.get("subregion", "")
        if iso in BRI:
            return "bri"
        if iso in NWE:
            return "nwe"
        if iso in SEE:
            return "see"
        if iso == "MEX":
            return "mex"
        if iso == "CAN":
            return "can"
        if cont == "Africa":
            return "afr"
        if cont == "Asia" or iso in ("CYP",):
            return "asi"
        if cont == "South America" or sub in ("Caribbean", "Central America"):
            return "lat"
        if cont == "Europe":
            return "see"
        return "oth"

    def unit(self, uid):
        if uid not in self.units:
            if uid in CUSTOM:
                name, group, iso = CUSTOM[uid]
            else:
                r = self.iso_rows[uid]
                name, group, iso = NAME_OVERRIDES.get(uid, r["name"]), self.group_for_iso(uid), [uid]
            u = {"id": uid, "name": name, "group": group, "iso": iso}
            if name in SHORT:
                u["short"] = SHORT[name]
            if uid in FORCED:
                u["forced"] = True
            if uid.startswith("X"):
                u["residual"] = True
            if uid in NOTES:
                u["note"] = NOTES[uid]
            self.units[uid] = u
        return self.units[uid]

    def anchor(self, uid):
        """Arrow start [lon, lat] for an origin, or None for origins that can't be placed."""
        if uid in ANCHORS:
            a = ANCHORS[uid]
        elif uid in self.iso_rows and self.iso_rows[uid]["lon"]:
            a = (float(self.iso_rows[uid]["lon"]), float(self.iso_rows[uid]["lat"]))
        else:
            a = None
        return [round(a[0], 2), round(a[1], 2)] if a else None

    def coast(self, uid):
        """Schematic point of arrival: east, florida, border, west or north (forced = by landing region)."""
        u = self.units[uid]
        g = u["group"]
        if u.get("forced"):
            return "forced"
        lon = self.anchor(uid)[0]
        if g == "can" or uid == "XNA":
            return "north"
        if g == "mex" or uid in CENTRAL_AMERICA:
            return "border"
        if g == "lat":
            return "florida"
        if lon > MAP_CUT or lon < -140:
            return "west"
        return "east"

    def resolve(self, label, level="country", parent="", year=None):
        """Return an origin id for a source label (registering the unit), or None."""
        n = norm(label)
        if level == "residual" or n.startswith(("other ", "all other")) or " nec" in n or "not specified" in n \
                or "not reported" in n or n in ("unknown", "no country detail in source"):
            if n in ALIASES:
                return self.unit(ALIASES[n])["id"]
            return self.unit(residual_for(label, parent))["id"]
        if n in ("russia", "soviet union", "ussr", "russia / soviet union") and year is not None:
            uid = "SUN" if year < 1992 else "RUS"
            return self.unit(uid)["id"]
        if n in ALIASES:
            return self.unit(ALIASES[n])["id"]
        for prefix, uid in (("turkey in asia", "OTA"),):
            if n.startswith(prefix):
                return self.unit(uid)["id"]
        if n in self.by_name:
            return self.unit(self.by_name[n])["id"]
        self.unmatched[(label, parent)] = self.unmatched.get((label, parent), 0) + 1
        return None
