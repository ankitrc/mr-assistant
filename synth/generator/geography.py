"""geography: zone -> region -> HQ -> territory -> patch, one row per patch.

Each territory belongs to one SBU and has 6 HQ patches, 1 ex-HQ patch
(neighbouring town) and 1 outstation patch, the usual Indian field
structure. Coordinates are patch centres (approximate).
"""

import pandas as pd

from generator import config

ZONES = {9401: "North", 9402: "South", 9403: "East", 9404: "West"}

# territory_id: (territory_name, sbu, hq_id, hq_name, region_id, region_name, zone_id, state, patches)
# patches: (patch_name, city, state, lat, lon) - state None = territory state
TERRITORIES = {
    900001: ("Chennai T01", config.RESPI_BU, 9201, "Chennai", 9301, "Tamil Nadu", 9402, "Tamil Nadu", [
        ("T. Nagar", "Chennai", None, 13.0418, 80.2341), ("Anna Nagar", "Chennai", None, 13.0850, 80.2101),
        ("Adyar", "Chennai", None, 13.0012, 80.2565), ("Mylapore", "Chennai", None, 13.0368, 80.2676),
        ("Velachery", "Chennai", None, 12.9815, 80.2180), ("Tambaram", "Chennai", None, 12.9249, 80.1000),
        ("Chengalpattu", "Chengalpattu", None, 12.6921, 79.9707), ("Kanchipuram", "Kanchipuram", None, 12.8342, 79.7036)]),
    900002: ("Pune T01", config.RESPI_BU, 9202, "Pune", 9302, "Maharashtra", 9404, "Maharashtra", [
        ("Shivajinagar", "Pune", None, 18.5308, 73.8475), ("Kothrud", "Pune", None, 18.5074, 73.8077),
        ("Aundh", "Pune", None, 18.5590, 73.8078), ("Hadapsar", "Pune", None, 18.5089, 73.9260),
        ("Viman Nagar", "Pune", None, 18.5679, 73.9143), ("Pimpri-Chinchwad", "Pimpri-Chinchwad", None, 18.6298, 73.7997),
        ("Talegaon Dabhade", "Talegaon Dabhade", None, 18.7350, 73.6755), ("Baramati", "Baramati", None, 18.1515, 74.5777)]),
    900003: ("Kolkata T01", config.RESPI_BU, 9203, "Kolkata", 9303, "West Bengal", 9403, "West Bengal", [
        ("Park Street", "Kolkata", None, 22.5535, 88.3520), ("Salt Lake", "Kolkata", None, 22.5867, 88.4171),
        ("Ballygunge", "Kolkata", None, 22.5276, 88.3644), ("Behala", "Kolkata", None, 22.4980, 88.3105),
        ("Dum Dum", "Kolkata", None, 22.6260, 88.4220), ("Garia", "Kolkata", None, 22.4637, 88.3920),
        ("Howrah", "Howrah", None, 22.5958, 88.2636), ("Barasat", "Barasat", None, 22.7230, 88.4810)]),
    900004: ("Mumbai T01", config.CARDIO_BU, 9211, "Mumbai", 9311, "Mumbai", 9404, "Maharashtra", [
        ("Bandra", "Mumbai", None, 19.0596, 72.8295), ("Andheri", "Mumbai", None, 19.1136, 72.8697),
        ("Dadar", "Mumbai", None, 19.0178, 72.8478), ("Ghatkopar", "Mumbai", None, 19.0860, 72.9081),
        ("Borivali", "Mumbai", None, 19.2307, 72.8567), ("Chembur", "Mumbai", None, 19.0522, 72.9005),
        ("Thane", "Thane", None, 19.2183, 72.9781), ("Vashi", "Navi Mumbai", None, 19.0771, 72.9986)]),
    900005: ("Delhi T01", config.CARDIO_BU, 9212, "Delhi", 9312, "Delhi NCR", 9401, "Delhi", [
        ("Karol Bagh", "New Delhi", None, 28.6519, 77.1909), ("Lajpat Nagar", "New Delhi", None, 28.5677, 77.2433),
        ("Rohini", "New Delhi", None, 28.7495, 77.0565), ("Dwarka", "New Delhi", None, 28.5921, 77.0460),
        ("Janakpuri", "New Delhi", None, 28.6219, 77.0878), ("Preet Vihar", "New Delhi", None, 28.6417, 77.2950),
        ("Noida Sector 18", "Noida", "Uttar Pradesh", 28.5708, 77.3260), ("Gurugram", "Gurugram", "Haryana", 28.4595, 77.0266)]),
}


def build() -> None:
    rows = []
    for territory_id, (t_name, sbu, hq_id, hq_name, region_id, region_name, zone_id, state, patches) in TERRITORIES.items():
        for i, (p_name, city, p_state, lat, lon) in enumerate(patches, start=1):
            rows.append({
                "patch_id": territory_id * 100 + i,      # e.g. 90000101
                "patch_name": p_name,
                "territory_id": territory_id,
                "territory_name": t_name,
                "hq_id": hq_id, "hq_name": hq_name,
                "region_id": region_id, "region_name": region_name,
                "zone_id": zone_id, "zone_name": ZONES[zone_id],
                "business_unit_id": sbu,
                "city": city, "state": p_state or state,
                "latitude": lat, "longitude": lon,
                "is_active": True,
            })

    from generator.common import write_parquet
    write_parquet("geography", pd.DataFrame(rows), """
    patch_id          BIGINT  PRIMARY KEY,
    patch_name        VARCHAR NOT NULL,
    territory_id      BIGINT  NOT NULL,
    territory_name    VARCHAR NOT NULL,
    hq_id             BIGINT  NOT NULL,
    hq_name           VARCHAR NOT NULL,
    region_id         BIGINT  NOT NULL,
    region_name       VARCHAR NOT NULL,
    zone_id           BIGINT  NOT NULL,
    zone_name         VARCHAR NOT NULL,
    business_unit_id  BIGINT  NOT NULL,
    city              VARCHAR NOT NULL,
    state             VARCHAR NOT NULL,
    latitude          DOUBLE  NOT NULL,
    longitude         DOUBLE  NOT NULL,
    is_active         BOOLEAN NOT NULL""".strip("\n"))
