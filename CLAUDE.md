# Clinical Trials Analytics Dashboard — Project Guide

## Overview
Multi-tab Plotly Dash analytics dashboard over ClinicalTrials.gov data stored in AWS S3 as Parquet files. DuckDB queries S3 directly via httpfs — no local data copies.

## How to run
```
python index.py          # starts on http://localhost:8050
```
AWS credentials must be configured (used by `aws_client.py` to set up DuckDB S3 auth).

## Architecture

```
index.py              ← app entry point: layout, sidebar, tab wiring
app.py                ← Dash app singleton (FLATLY theme + Bootstrap Icons)
aws_client.py         ← sets up DuckDB httpfs S3 auth from env/profile
constants.py          ← S3 paths, column name aliases, business constants
data_engine.py        ← DataEngine class: all SQL queries, one engine singleton
tabs/
  overview.py         ← Overview tab: layout + callbacks
  interventions.py    ← Interventions tab: layout + callbacks
  conditions.py       ← Conditions tab: layout + callbacks
  outcomes.py         ← Outcomes tab: layout + callbacks  [TODO]
```

## Data sources (S3 Parquet)

| Key | S3 path | Notes |
|-----|---------|-------|
| `base` | `.../base/*.parquet` | Core trial metadata |
| `location` | `.../locations/*.parquet` | Trial locations by country |
| `phases` | `.../phases/*.parquet` | Trial phase rows (one row per phase) |
| `interventions` | `.../arm_inerventions/arm_interventions_parquet3_full_light.parquet` | Intervention rows; typo in path is intentional (matches data team naming) |
| `conditions` | `.../conditions/derivedsection_conditions_lvl.parquet` | MeSH hierarchy: `level_1`–`level_9`, `condition_id`, `condition_name` |
| `outcomes` | `.../outcomes/outcomes_parquet3_full_light_timefix (1).parquet` | Pre-joined: includes trial metadata, geo, phases inline — no joins needed |

## Key column aliases (constants.py)
```python
SPONSOR_COL           = "protocolsection_sponsorcollaboratorsmodule_leadsponsor_name"
COUNTRY_COL           = "protocolsection_contactslocationsmodule_locations_country"
INTERVENTION_TYPE_COL = "protocolsection_armsinterventionsmodule_interventions_type"
INTERVENTION_NAME_COL = "protocolsection_armsinterventionsmodule_interventions_name"
CONDITIONS_NAME_COL   = "condition_name"
```

## DataEngine patterns

### Global filter CTE
`_build_filter_cte(phases, statuses, countries, study_types, sponsor)` returns a `WITH filtered_trials AS (...)` CTE string. All tabs extend it by appending more CTEs with commas.

### Threading
DuckDB connection is not thread-safe. All queries go through `self._lock = threading.Lock()`. Each public method (`get_*_data`) acquires the lock and delegates to `_get_*_data_impl`. This prevents race conditions when multiple tab callbacks fire simultaneously on page load.

### Filter options
Loaded once at startup via `_load_filter_options()` using an isolated `tmp` DuckDB connection so S3 failures during startup can't corrupt the main `self.con`.

### Outcomes table — no joins needed
The outcomes parquet is pre-joined and includes: `main_country`, `top2_country`, `top3_country`, `other_countries`, `protocolsection_designmodule_phases`, sponsor fields, dates, enrollment, etc. Query it standalone — no JOIN with base/location/phases.

## Tab structure (each tab file)
1. Helper functions: `_fmt_label`, `_empty_fig`, `_chart_card`, `_kpi_card`, `_label`
2. Color maps (stable, named) for cross-filter consistency
3. `render_layout()` — returns the full tab HTML/component tree
4. Cross-filter callbacks (optional `dcc.Store` + badge toggle)
5. Main `@callback` — reads from `engine.get_*_data()`, renders all charts

## Conventions
- All commits go directly to `main` (solo developer, no PRs)
- `_empty_fig(msg)` for charts with no data — never crash
- Plotly 6.x geo: use `showcountries/countrycolor/countrywidth` (not `showborders/*`)
- Chart colors are always named maps (dict), not positional sequences, so cross-filter dimming works correctly
- Table NCT IDs are rendered as markdown links: `[NCT...](https://clinicaltrials.gov/study/NCT...)`
- `prevent_initial_call=True` on cross-filter callbacks; main data callback fires on initial load

## Sidebar global filters (all tabs respond)
Phase, Status, Country, Study Type, Sponsor → `apply-filters-btn` → each tab's main callback reads these as `State` inputs.

## Outcomes-specific columns (short aliases used in code)
```
nctid          = protocolsection_identificationmodule_nctid
outcome_type   = resultssection_outcomemeasuresmodule_outcomemeasures_type        (PRIMARY/SECONDARY)
outcome_title  = resultssection_outcomemeasuresmodule_outcomemeasures_title
param_type     = resultssection_outcomemeasuresmodule_outcomemeasures_paramtype   (MEAN/MEDIAN/COUNT…)
reporting_status = resultssection_outcomemeasuresmodule_outcomemeasures_reportingstatus
pvalue_mean    = pvalue_mean
pvalue_min     = pvalue_min
num_pvalues    = num_pvalues
effect_mean    = effect_mean
num_effect     = num_effect
ci_range_mean  = ci_range_mean
main_country   = main_country
phase          = protocolsection_designmodule_phases
sponsor_class  = protocolsection_sponsorcollaboratorsmodule_leadsponsor_class     (INDUSTRY/NIH/OTHER)
primary_purpose = protocolsection_designmodule_designinfo_primarypurpose
```
