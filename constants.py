import os

# AWS & S3
S3_BUCKET = "s3://inno-clinicaltrial-v2-bucket/test/rdb_parquet/ct_500"
TABLES = {
    "base": f"{S3_BUCKET}/base/*.parquet",
    "location": f"{S3_BUCKET}/locations/*.parquet",
    "phases": f"{S3_BUCKET}/phases/*.parquet"
}

# UI Settings
COLORS = {"primary": "#007BFF", "success": "#28A745"}
DEFAULT_PHASES = ["Phase 1", "Phase 2", "Phase 3"]