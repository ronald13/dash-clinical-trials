import os

# AWS & S3
S3_BUCKET = "s3://inno-clinicaltrial-v2-bucket/test/rdb_parquet/ct_500"
TABLES = {
    "base":     f"{S3_BUCKET}/base/*.parquet",
    "location": f"{S3_BUCKET}/locations/*.parquet",
    "phases":   f"{S3_BUCKET}/phases/*.parquet",
}

# Long ClinicalTrials.gov column name aliases
SPONSOR_COL = "protocolsection_sponsorcollaboratorsmodule_leadsponsor_name"
COUNTRY_COL  = "protocolsection_contactslocationsmodule_locations_country"

# Business logic — statuses that count as "Delayed"
DELAYED_STATUSES = [
    "TERMINATED", "WITHDRAWN", "SUSPENDED", "WITHHELD", "NO_LONGER_AVAILABLE"
]

# UI
COLORS = {"primary": "#007BFF", "success": "#28A745"}
