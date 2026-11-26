"""Map areas the planner ships with. Pick one with the RUN_REGION environment variable (default: verdun).

Each area becomes its own map file (map-data.json / map-data.bin for Verdun, map-data-<id>.* for others).
"""
import os

REGIONS = {
    "verdun": {
        "bbox": (-73.74, 45.36, -73.42, 45.56),     # southwest Montréal, downtown, the Plateau, the islands
        "lat0": 45.46,                               # latitude for metres-per-degree
        "address_bbox": (-73.60, 45.44, -73.54, 45.48),
        "home": {"postcode": "H4G2Z5"},              # 5e Avenue, Verdun
    },
    "st-berthevin": {
        "bbox": (-1.00, 47.96, -0.66, 48.18),        # Saint-Berthevin, Laval and the countryside around (Mayenne)
        "lat0": 48.07,
        "address_bbox": (-0.88, 48.04, -0.79, 48.10),
        "home": {"street": "Avenue Saint Exupery", "postcode": "53940"},  # as the address data spells it
    },
}
ID = os.environ.get("RUN_REGION", "verdun")
R = REGIONS[ID]
