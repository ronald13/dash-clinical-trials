import os

# AWS & S3
S3_BUCKET = "s3://inno-clinicaltrial-v2-bucket/test/rdb_parquet/ct_500"
TABLES = {
    "base":          f"{S3_BUCKET}/base/*.parquet",
    "location":      f"{S3_BUCKET}/locations/*.parquet",
    "phases":        f"{S3_BUCKET}/phases/*.parquet",
    "interventions": f"{S3_BUCKET}/arm_inerventions/arm_interventions_parquet3_full_light.parquet",
    "conditions":    f"{S3_BUCKET}/conditions/derivedsection_conditions_lvl.parquet",
    "outcomes":      f"{S3_BUCKET}/outcomes/outcomes_parquet3_full_light_timefix (1).parquet",
}

# Long ClinicalTrials.gov column name aliases
SPONSOR_COL           = "protocolsection_sponsorcollaboratorsmodule_leadsponsor_name"
COUNTRY_COL           = "protocolsection_contactslocationsmodule_locations_country"
INTERVENTION_TYPE_COL = "protocolsection_armsinterventionsmodule_interventions_type"
INTERVENTION_NAME_COL = "protocolsection_armsinterventionsmodule_interventions_name"
CONDITIONS_NAME_COL   = "condition_name"

# Outcomes table column aliases
OUTCOME_TYPE_COL    = "resultssection_outcomemeasuresmodule_outcomemeasures_type"
OUTCOME_TITLE_COL   = "resultssection_outcomemeasuresmodule_outcomemeasures_title"
OUTCOME_PARAM_COL   = "resultssection_outcomemeasuresmodule_outcomemeasures_paramtype"
OUTCOME_STATUS_COL  = "resultssection_outcomemeasuresmodule_outcomemeasures_reportingstatus"
SPONSOR_CLASS_COL   = "protocolsection_sponsorcollaboratorsmodule_leadsponsor_class"
PRIMARY_PURPOSE_COL = "protocolsection_designmodule_designinfo_primarypurpose"
PHASE_COL           = "protocolsection_designmodule_phases"
OVERALL_STATUS_COL  = "protocolsection_statusmodule_overallstatus"

# Business logic — statuses that count as "Delayed"
DELAYED_STATUSES = [
    "TERMINATED", "WITHDRAWN", "SUSPENDED", "WITHHELD", "NO_LONGER_AVAILABLE"
]

# UI
COLORS = {"primary": "#007BFF", "success": "#28A745"}
