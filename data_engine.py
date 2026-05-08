import duckdb
import threading
from datetime import datetime
from aws_client import setup_duckdb_s3
from constants import (TABLES, SPONSOR_COL, COUNTRY_COL, DELAYED_STATUSES,
                       INTERVENTION_TYPE_COL, INTERVENTION_NAME_COL, CONDITIONS_NAME_COL,
                       OUTCOME_TYPE_COL, OUTCOME_TITLE_COL, OUTCOME_PARAM_COL,
                       OUTCOME_STATUS_COL, SPONSOR_CLASS_COL, PRIMARY_PURPOSE_COL,
                       PHASE_COL, OVERALL_STATUS_COL)


class DataEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self.con = duckdb.connect(database=':memory:')
        setup_duckdb_s3(self.con)
        self._initialize_views()
        self.filter_options = self._load_filter_options()

    # ------------------------------------------------------------------
    # Init helpers
    # ------------------------------------------------------------------

    def _initialize_views(self):
        """Create lazy views for S3 Parquet files. No data is transferred yet."""
        for name, path in TABLES.items():
            try:
                self.con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{path}')")
            except Exception as e:
                print(f"View creation error for {name}: {e}")

    def _load_filter_options(self):
        """Load unique values for each filter dropdown once at startup.

        Uses a dedicated temporary connection so any S3 failure during loading
        cannot corrupt self.con (the main query connection).
        """
        try:
            tmp = duckdb.connect(':memory:')
            setup_duckdb_s3(tmp)
            for name, path in TABLES.items():
                try:
                    tmp.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{path}')")
                except Exception as e:
                    print(f"Filter-options view error ({name}): {e}")
        except Exception as e:
            print(f"Filter-options connection error: {e}")
            return {}

        def _fetch(sql):
            try:
                return [r[0] for r in tmp.execute(sql).fetchall()]
            except Exception as e:
                print(f"Filter options load error: {e}")
                return []

        result = {
            "phases": _fetch(
                "SELECT DISTINCT protocolsection_designmodule_phases "
                "FROM phases WHERE protocolsection_designmodule_phases IS NOT NULL ORDER BY 1"
            ),
            "statuses": _fetch(
                "SELECT DISTINCT protocolsection_statusmodule_overallstatus "
                "FROM base WHERE protocolsection_statusmodule_overallstatus IS NOT NULL ORDER BY 1"
            ),
            "study_types": _fetch(
                "SELECT DISTINCT protocolsection_designmodule_studytype "
                "FROM base WHERE protocolsection_designmodule_studytype IS NOT NULL ORDER BY 1"
            ),
            "countries": _fetch(
                f"SELECT DISTINCT {COUNTRY_COL} "
                f"FROM location WHERE {COUNTRY_COL} IS NOT NULL ORDER BY 1"
            ),
            "int_sem_level_1": _fetch(
                "SELECT DISTINCT sem_level_1 FROM interventions "
                "WHERE sem_level_1 IS NOT NULL ORDER BY 1"
            ),
            "int_sem_level_2": _fetch(
                "SELECT DISTINCT sem_level_2 FROM interventions "
                "WHERE sem_level_2 IS NOT NULL ORDER BY 1"
            ),
            "int_sem_level_3": _fetch(
                "SELECT DISTINCT sem_level_3 FROM interventions "
                "WHERE sem_level_3 IS NOT NULL ORDER BY 1"
            ),
            "int_types": _fetch(
                f"SELECT DISTINCT {INTERVENTION_TYPE_COL} FROM interventions "
                f"WHERE {INTERVENTION_TYPE_COL} IS NOT NULL ORDER BY 1"
            ),
            "outcome_types": _fetch(
                f"SELECT DISTINCT {OUTCOME_TYPE_COL} FROM outcomes "
                f"WHERE {OUTCOME_TYPE_COL} IS NOT NULL ORDER BY 1"
            ),
            "sponsor_classes": _fetch(
                f"SELECT DISTINCT {SPONSOR_CLASS_COL} FROM outcomes "
                f"WHERE {SPONSOR_CLASS_COL} IS NOT NULL ORDER BY 1"
            ),
            "primary_purposes": _fetch(
                f"SELECT DISTINCT {PRIMARY_PURPOSE_COL} FROM outcomes "
                f"WHERE {PRIMARY_PURPOSE_COL} IS NOT NULL ORDER BY 1"
            ),
            "reporting_statuses": _fetch(
                f"SELECT DISTINCT {OUTCOME_STATUS_COL} FROM outcomes "
                f"WHERE {OUTCOME_STATUS_COL} IS NOT NULL ORDER BY 1"
            ),
        }
        try:
            tmp.close()
        except Exception:
            pass
        return result

    # ------------------------------------------------------------------
    # Query builder
    # ------------------------------------------------------------------

    def _build_filter_cte(self, phases=None, statuses=None, countries=None,
                          study_types=None, sponsor=None):
        """
        Returns a WITH clause that resolves to filtered_trials(nctid).
        Only adds JOINs for active filters to keep S3 pushdown efficient.
        """
        joins = []
        conditions = ["1=1"]

        if phases:
            joins.append(
                "JOIN phases p "
                "ON b.protocolsection_identificationmodule_nctid "
                "= p.protocolsection_identificationmodule_nctid"
            )
            sql = ", ".join(f"'{p}'" for p in phases)
            conditions.append(f"p.protocolsection_designmodule_phases IN ({sql})")

        if statuses:
            sql = ", ".join(f"'{s}'" for s in statuses)
            conditions.append(
                f"b.protocolsection_statusmodule_overallstatus IN ({sql})"
            )

        if study_types:
            sql = ", ".join(f"'{t}'" for t in study_types)
            conditions.append(f"b.protocolsection_designmodule_studytype IN ({sql})")

        if sponsor:
            safe = sponsor.replace("'", "''")
            conditions.append(f"b.{SPONSOR_COL} ILIKE '%{safe}%'")

        if countries:
            joins.append(
                "JOIN location l "
                "ON b.protocolsection_identificationmodule_nctid "
                "= l.protocolsection_identificationmodule_nctid"
            )
            sql = ", ".join(f"'{c}'" for c in countries)
            conditions.append(f"l.{COUNTRY_COL} IN ({sql})")

        joins_sql = "\n            ".join(joins)
        where_sql  = " AND ".join(conditions)

        return f"""
            WITH filtered_trials AS (
                SELECT DISTINCT b.protocolsection_identificationmodule_nctid AS nctid
                FROM base b
                {joins_sql}
                WHERE {where_sql}
            )
        """

    # ------------------------------------------------------------------
    # Main data method
    # ------------------------------------------------------------------

    def get_overview_data(self, phases=None, statuses=None, countries=None,
                          study_types=None, sponsor=None):
        with self._lock:
            return self._get_overview_data_impl(phases, statuses, countries, study_types, sponsor)

    def _get_overview_data_impl(self, phases=None, statuses=None, countries=None,
                                study_types=None, sponsor=None):
        base_cte = self._build_filter_cte(phases, statuses, countries, study_types, sponsor)
        delayed_sql = ", ".join(f"'{s}'" for s in DELAYED_STATUSES)

        # ── KPIs ──────────────────────────────────────────────────────
        try:
            kpi_row = self.con.execute(f"""
                {base_cte}
                SELECT
                    COUNT(b.protocolsection_identificationmodule_nctid)                        AS total_trials,
                    SUM(b.protocolsection_designmodule_enrollmentinfo_count)                   AS total_enrollment,
                    SUM(b.hasresults)                                                          AS trials_with_results,
                    SUM(CASE WHEN b.protocolsection_statusmodule_overallstatus = 'COMPLETED'
                             THEN 1 ELSE 0 END)                                                AS completed_trials,
                    MAX(b.protocolsection_statusmodule_lastupdatepostdatestruct_date)          AS last_update,
                    COUNT(CASE WHEN regexp_extract(
                        b.protocolsection_statusmodule_studyfirstpostdatestruct_date, '\\d{{4}}')
                        = CAST(YEAR(CURRENT_DATE) - 1 AS VARCHAR)
                        THEN 1 END)                                                             AS new_last_year
                FROM base b
                JOIN filtered_trials ft
                  ON b.protocolsection_identificationmodule_nctid = ft.nctid
            """).fetchone()
        except Exception as e:
            print(f"Overview KPI error: {e}")
            kpi_row = None

        if kpi_row is None:
            kpi_row = (0, 0, 0, 0, "", 0)

        total        = kpi_row[0] or 0
        enroll       = kpi_row[1] or 0
        results      = kpi_row[2] or 0
        done         = kpi_row[3] or 0
        raw_date     = kpi_row[4] or ""
        new_last_year = kpi_row[5] or 0

        pct_results  = round(results / total * 100, 1) if total else 0
        pct_complete = round(done    / total * 100, 1) if total else 0

        # Format last update
        try:
            dt = datetime.strptime(raw_date[:10], "%Y-%m-%d")
            last_update_str = dt.strftime("%b %d, %Y")
        except Exception:
            last_update_str = raw_date or "N/A"

        # Compact enrollment label (123.42M / 4.5K / 999)
        def _fmt_enrollment(n):
            if n >= 1_000_000:
                return f"{n / 1_000_000:.2f}M"
            if n >= 1_000:
                return f"{n / 1_000:.1f}K"
            return f"{n:,.0f}"

        # ── Delay Status donut ────────────────────────────────────────
        df_delay = self.con.execute(f"""
            {base_cte}
            SELECT
                CASE WHEN b.protocolsection_statusmodule_overallstatus IN ({delayed_sql})
                     THEN 'Delayed' ELSE 'On Track' END AS status_group,
                COUNT(*) AS count
            FROM base b
            JOIN filtered_trials ft
              ON b.protocolsection_identificationmodule_nctid = ft.nctid
            GROUP BY 1
        """).df()

        # ── Sex Distribution donut ────────────────────────────────────
        df_sex = self.con.execute(f"""
            {base_cte}
            SELECT
                UPPER(b.protocolsection_eligibilitymodule_sex) AS sex,
                COUNT(*) AS count
            FROM base b
            JOIN filtered_trials ft
              ON b.protocolsection_identificationmodule_nctid = ft.nctid
            WHERE b.protocolsection_eligibilitymodule_sex IS NOT NULL
            GROUP BY 1
            ORDER BY 2 DESC
        """).df()

        # ── Status Distribution bar ───────────────────────────────────
        df_status = self.con.execute(f"""
            {base_cte}
            SELECT
                b.protocolsection_statusmodule_overallstatus AS status,
                COUNT(*) AS count
            FROM base b
            JOIN filtered_trials ft
              ON b.protocolsection_identificationmodule_nctid = ft.nctid
            GROUP BY 1
            ORDER BY 2 DESC
        """).df()

        # ── GeoMap ───────────────────────────────────────────────────
        # When countries filter is active, restrict geo to only those countries
        # (otherwise geo would show ALL locations of Kazakhstan-filtered trials)
        if countries:
            geo_country_sql = ", ".join(f"'{c}'" for c in countries)
            geo_country_filter = f"AND l.{COUNTRY_COL} IN ({geo_country_sql})"
        else:
            geo_country_filter = ""

        try:
            df_geo = self.con.execute(f"""
                {base_cte}
                SELECT
                    l.{COUNTRY_COL} AS country,
                    COUNT(DISTINCT l.protocolsection_identificationmodule_nctid) AS count
                FROM location l
                JOIN filtered_trials ft
                  ON l.protocolsection_identificationmodule_nctid = ft.nctid
                WHERE l.{COUNTRY_COL} IS NOT NULL
                  {geo_country_filter}
                GROUP BY 1
                ORDER BY 2 DESC
            """).df()
        except Exception as e:
            print(f"Geo query error: {e}")
            df_geo = None

        # ── Top 25 Sponsors ───────────────────────────────────────────
        try:
            df_sponsors = self.con.execute(f"""
                {base_cte}
                SELECT
                    b.{SPONSOR_COL} AS sponsor,
                    COUNT(*) AS count
                FROM base b
                JOIN filtered_trials ft
                  ON b.protocolsection_identificationmodule_nctid = ft.nctid
                WHERE b.{SPONSOR_COL} IS NOT NULL
                GROUP BY 1
                ORDER BY 2 DESC
                LIMIT 25
            """).df()
        except Exception as e:
            print(f"Sponsor query error: {e}")
            df_sponsors = None

        # ── Table (first 500 rows) ────────────────────────────────────
        # When country filter is active, restrict agg_loc to selected countries
        # so the Country column in the table shows the filtered country, not an
        # unrelated one from the same multi-country trial.
        if countries:
            loc_country_sql = ", ".join(f"'{c}'" for c in countries)
            loc_where = f"WHERE {COUNTRY_COL} IN ({loc_country_sql})"
        else:
            loc_where = ""

        try:
            df_table = self.con.execute(f"""
                {base_cte},
                agg_phases AS (
                    SELECT
                        protocolsection_identificationmodule_nctid AS nctid,
                        STRING_AGG(DISTINCT protocolsection_designmodule_phases, ', ') AS phase
                    FROM phases
                    GROUP BY 1
                ),
                agg_loc AS (
                    SELECT
                        protocolsection_identificationmodule_nctid AS nctid,
                        MIN({COUNTRY_COL}) AS country
                    FROM location
                    {loc_where}
                    GROUP BY 1
                )
                SELECT
                    b.protocolsection_identificationmodule_nctid                      AS nctid,
                    regexp_extract(b.protocolsection_statusmodule_startdatestruct_date,
                                   '\\d{{4}}')                                         AS year,
                    b.protocolsection_statusmodule_completiondatestruct_date           AS completion,
                    b.protocolsection_identificationmodule_brieftitle                  AS title,
                    b.protocolsection_statusmodule_overallstatus                       AS status,
                    ap.phase,
                    b.protocolsection_designmodule_studytype                           AS study_type,
                    b.{SPONSOR_COL}                                                    AS sponsor,
                    al.country,
                    CAST(b.protocolsection_designmodule_enrollmentinfo_count AS BIGINT) AS enrollment
                FROM base b
                JOIN filtered_trials ft
                  ON b.protocolsection_identificationmodule_nctid = ft.nctid
                LEFT JOIN agg_phases ap
                  ON b.protocolsection_identificationmodule_nctid = ap.nctid
                LEFT JOIN agg_loc al
                  ON b.protocolsection_identificationmodule_nctid = al.nctid
                ORDER BY b.protocolsection_identificationmodule_nctid
                LIMIT 500
            """).df()
            # Make NCT ID a clickable markdown link
            df_table["nctid"] = df_table["nctid"].apply(
                lambda x: f"[{x}](https://clinicaltrials.gov/study/{x})"
            )
        except Exception as e:
            print(f"Table query error: {e}")
            df_table = None

        # ── Trial Duration by Phase ───────────────────────────────────
        try:
            df_duration = self.con.execute(f"""
                {base_cte},
                agg_ph_dur AS (
                    SELECT protocolsection_identificationmodule_nctid AS nctid,
                           MIN(protocolsection_designmodule_phases) AS phase
                    FROM phases GROUP BY 1
                ),
                dur AS (
                    SELECT
                        COALESCE(ap.phase, 'N/A') AS phase,
                        DATEDIFF('day',
                            TRY_CAST(b.protocolsection_statusmodule_startdatestruct_date AS DATE),
                            TRY_CAST(b.protocolsection_statusmodule_completiondatestruct_date AS DATE)
                        ) / 30.44 AS duration_months
                    FROM base b
                    JOIN filtered_trials ft
                      ON b.protocolsection_identificationmodule_nctid = ft.nctid
                    LEFT JOIN agg_ph_dur ap
                      ON b.protocolsection_identificationmodule_nctid = ap.nctid
                    WHERE DATEDIFF('day',
                        TRY_CAST(b.protocolsection_statusmodule_startdatestruct_date AS DATE),
                        TRY_CAST(b.protocolsection_statusmodule_completiondatestruct_date AS DATE)
                    ) BETWEEN 1 AND 18250
                )
                SELECT
                    phase,
                    ROUND(MEDIAN(duration_months), 1) AS median_months,
                    ROUND(AVG(duration_months), 1)    AS avg_months,
                    COUNT(*)                           AS trial_count
                FROM dur
                GROUP BY 1
                ORDER BY median_months DESC
            """).df()
        except Exception as e:
            print(f"Duration query error: {e}")
            df_duration = None

        prev_year = datetime.now().year - 1
        new_label = f"+ {new_last_year:,} new in {prev_year}"

        return {
            "kpi_trials":      f"{total:,}",
            "kpi_trials_new":  new_label,
            "kpi_enrollment":  _fmt_enrollment(enroll),
            "kpi_results":     f"{pct_results}%",
            "kpi_results_sub": f"{int(results):,} Records",
            "kpi_completion":  f"{pct_complete}%",
            "last_update":     last_update_str,
            "delay_dist":      df_delay,
            "sex_dist":        df_sex,
            "status_dist":     df_status,
            "geo_dist":        df_geo,
            "sponsor_dist":    df_sponsors,
            "table_data":      df_table,
            "duration_dist":   df_duration,
        }


    def get_interventions_data(self, phases=None, statuses=None, countries=None,
                               study_types=None, sponsor=None,
                               sem_level_1=None, sem_level_2=None, sem_level_3=None,
                               int_name=None, int_type_filter=None):
        with self._lock:
            return self._get_interventions_data_impl(
                phases, statuses, countries, study_types, sponsor,
                sem_level_1, sem_level_2, sem_level_3, int_name, int_type_filter
            )

    def _get_interventions_data_impl(self, phases=None, statuses=None, countries=None,
                                     study_types=None, sponsor=None,
                                     sem_level_1=None, sem_level_2=None, sem_level_3=None,
                                     int_name=None, int_type_filter=None):
        base_cte = self._build_filter_cte(phases, statuses, countries, study_types, sponsor)

        # sem_level + name conditions (no type filter — kept separate for treemap)
        int_conditions = ["1=1"]
        if sem_level_1:
            v_sql = ", ".join(f"'{v}'" for v in sem_level_1)
            int_conditions.append(f"i.sem_level_1 IN ({v_sql})")
        if sem_level_2:
            v_sql = ", ".join(f"'{v}'" for v in sem_level_2)
            int_conditions.append(f"i.sem_level_2 IN ({v_sql})")
        if sem_level_3:
            v_sql = ", ".join(f"'{v}'" for v in sem_level_3)
            int_conditions.append(f"i.sem_level_3 IN ({v_sql})")
        if int_name:
            safe = int_name.replace("'", "''")
            int_conditions.append(f"i.{INTERVENTION_NAME_COL} ILIKE '%{safe}%'")
        int_where_base = " AND ".join(int_conditions)

        # Treemap cross-filter applied only to non-treemap charts
        if int_type_filter:
            safe_type = int_type_filter.replace("'", "''")
            int_where_typed = int_where_base + f" AND i.{INTERVENTION_TYPE_COL} = '{safe_type}'"
        else:
            int_where_typed = int_where_base

        def _make_full_cte(int_where):
            return base_cte.rstrip() + f""",
        filtered_interventions AS (
            SELECT
                i.protocolsection_identificationmodule_nctid AS nctid,
                i.{INTERVENTION_TYPE_COL}                    AS int_type,
                i.{INTERVENTION_NAME_COL}                    AS int_name,
                i.entity_canonical_name,
                i.armgrouplabel
            FROM interventions i
            JOIN filtered_trials ft
              ON i.protocolsection_identificationmodule_nctid = ft.nctid
            WHERE {int_where}
        ),
        int_trials AS (
            SELECT DISTINCT nctid FROM filtered_interventions
        )
        """

        # treemap uses base (all types visible); everything else uses typed CTE
        full_cte_base  = _make_full_cte(int_where_base)
        full_cte_typed = _make_full_cte(int_where_typed)

        # ── KPIs ──────────────────────────────────────────────────────
        # Total Trials = all globally-filtered trials (same denominator as Overview)
        kpi_row = self.con.execute(f"""
            {base_cte}
            SELECT COUNT(*) FROM filtered_trials
        """).fetchone()
        total = (kpi_row[0] or 0) if kpi_row else 0

        try:
            uniq_row = self.con.execute(f"""
                {full_cte_typed}
                SELECT
                    COUNT(DISTINCT LOWER(TRIM(int_name)))     AS unique_interventions,
                    COUNT(DISTINCT entity_canonical_name)      AS unique_conditions
                FROM filtered_interventions
            """).fetchone()
            unique_int  = (uniq_row[0] or 0) if uniq_row else 0
            unique_cond = (uniq_row[1] or 0) if uniq_row else 0
        except Exception as e:
            print(f"Int uniq error: {e}"); unique_int = unique_cond = 0

        try:
            enroll_row = self.con.execute(f"""
                {base_cte}
                SELECT SUM(b.protocolsection_designmodule_enrollmentinfo_count)
                FROM base b
                JOIN filtered_trials ft ON b.protocolsection_identificationmodule_nctid = ft.nctid
            """).fetchone()
            enroll = (enroll_row[0] or 0) if enroll_row else 0
        except Exception as e:
            print(f"Int enrollment error: {e}"); enroll = 0

        def _fmt_n(n):
            if n >= 1_000_000: return f"{n / 1_000_000:.2f}M"
            if n >= 1_000:     return f"{n / 1_000:.1f}K"
            return f"{n:,.0f}"

        # ── Intervention Types treemap — always all types (no cross-filter) ──
        try:
            df_types = self.con.execute(f"""
                {full_cte_base}
                SELECT int_type, COUNT(DISTINCT nctid) AS count
                FROM filtered_interventions
                WHERE int_type IS NOT NULL
                GROUP BY 1
                ORDER BY 2 DESC
            """).df()
        except Exception as e:
            print(f"Int types error: {e}"); df_types = None

        # ── Dynamics stacked bar (capped at current year) ──────────────
        try:
            df_dynamics = self.con.execute(f"""
                {full_cte_typed}
                SELECT
                    regexp_extract(
                        b.protocolsection_statusmodule_startdatestruct_date,
                        '\\d{{4}}'
                    )                        AS year,
                    fi.int_type,
                    COUNT(DISTINCT fi.nctid) AS count
                FROM filtered_interventions fi
                JOIN base b
                  ON fi.nctid = b.protocolsection_identificationmodule_nctid
                WHERE fi.int_type IS NOT NULL
                  AND regexp_extract(
                        b.protocolsection_statusmodule_startdatestruct_date, '\\d{{4}}'
                      ) >= '2000'
                  AND regexp_extract(
                        b.protocolsection_statusmodule_startdatestruct_date, '\\d{{4}}'
                      ) <= CAST(YEAR(CURRENT_DATE) AS VARCHAR)
                GROUP BY 1, 2
                ORDER BY 1
            """).df()
        except Exception as e:
            print(f"Dynamics error: {e}"); df_dynamics = None

        # ── Top 25 Interventions (case-normalised dedup) ───────────────
        try:
            df_top_int = self.con.execute(f"""
                {full_cte_typed}
                SELECT ANY_VALUE(int_name) AS int_name,
                       COUNT(DISTINCT nctid) AS count
                FROM filtered_interventions
                WHERE int_name IS NOT NULL
                GROUP BY LOWER(TRIM(int_name))
                ORDER BY 2 DESC
                LIMIT 25
            """).df()
        except Exception as e:
            print(f"Top interventions error: {e}"); df_top_int = None

        # ── Top 25 Conditions (from conditions table) ──────────────────
        try:
            df_top_cond = self.con.execute(f"""
                {full_cte_typed}
                SELECT c.{CONDITIONS_NAME_COL} AS condition,
                       COUNT(DISTINCT c.protocolsection_identificationmodule_nctid) AS count
                FROM conditions c
                JOIN int_trials it
                  ON c.protocolsection_identificationmodule_nctid = it.nctid
                WHERE c.{CONDITIONS_NAME_COL} IS NOT NULL
                GROUP BY 1
                ORDER BY 2 DESC
                LIMIT 25
            """).df()
        except Exception as e:
            print(f"Top conditions error: {e}"); df_top_cond = None

        # ── Word Cloud top 50 (case-normalised) ───────────────────────
        try:
            df_wordcloud = self.con.execute(f"""
                {full_cte_typed}
                SELECT ANY_VALUE(int_name) AS int_name, COUNT(*) AS count
                FROM filtered_interventions
                WHERE int_name IS NOT NULL
                GROUP BY LOWER(TRIM(int_name))
                ORDER BY 2 DESC
                LIMIT 50
            """).df()
        except Exception as e:
            print(f"Word cloud error: {e}"); df_wordcloud = None

        # ── GeoMap ────────────────────────────────────────────────────
        if countries:
            geo_filter = ("AND l." + COUNTRY_COL + " IN ("
                          + ", ".join(f"'{c}'" for c in countries) + ")")
        else:
            geo_filter = ""
        try:
            df_geo = self.con.execute(f"""
                {full_cte_typed}
                SELECT l.{COUNTRY_COL} AS country,
                       COUNT(DISTINCT l.protocolsection_identificationmodule_nctid) AS count
                FROM location l
                JOIN int_trials it ON l.protocolsection_identificationmodule_nctid = it.nctid
                WHERE l.{COUNTRY_COL} IS NOT NULL {geo_filter}
                GROUP BY 1
                ORDER BY 2 DESC
            """).df()
        except Exception as e:
            print(f"Int geo error: {e}"); df_geo = None

        # ── Data Table ────────────────────────────────────────────────
        try:
            df_table = self.con.execute(f"""
                {full_cte_typed},
                agg_phases AS (
                    SELECT protocolsection_identificationmodule_nctid AS nctid,
                           STRING_AGG(DISTINCT protocolsection_designmodule_phases, ', ') AS phase
                    FROM phases GROUP BY 1
                )
                SELECT
                    fi.nctid,
                    regexp_extract(
                        b.protocolsection_statusmodule_startdatestruct_date, '\\d{{4}}'
                    )                                                              AS year,
                    b.protocolsection_identificationmodule_brieftitle              AS title,
                    b.protocolsection_statusmodule_overallstatus                   AS status,
                    ap.phase,
                    b.protocolsection_designmodule_studytype                       AS study_type,
                    fi.int_type,
                    fi.armgrouplabel                                                AS arm_label,
                    fi.int_name,
                    CAST(b.protocolsection_designmodule_enrollmentinfo_count AS BIGINT) AS enrollment
                FROM filtered_interventions fi
                JOIN base b ON fi.nctid = b.protocolsection_identificationmodule_nctid
                LEFT JOIN agg_phases ap ON fi.nctid = ap.nctid
                ORDER BY fi.nctid
                LIMIT 500
            """).df()
            df_table["nctid"] = df_table["nctid"].apply(
                lambda x: f"[{x}](https://clinicaltrials.gov/study/{x})"
            )
        except Exception as e:
            print(f"Int table error: {e}"); df_table = None

        return {
            "kpi_trials":        f"{total:,}",
            "kpi_enrollment":    _fmt_n(enroll),
            "kpi_unique_int":    f"{unique_int:,}",
            "kpi_unique_cond":   f"{unique_cond:,}",
            "int_types":         df_types,
            "int_dynamics":      df_dynamics,
            "top_interventions": df_top_int,
            "top_conditions":    df_top_cond,
            "wordcloud":         df_wordcloud,
            "geo_dist":          df_geo,
            "table_data":        df_table,
        }


    def get_conditions_data(self, phases=None, statuses=None, countries=None,
                            study_types=None, sponsor=None,
                            int_type=None, cond_name=None,
                            level1_filter=None):
        with self._lock:
            return self._get_conditions_data_impl(
                phases, statuses, countries, study_types, sponsor,
                int_type, cond_name, level1_filter,
            )

    def _get_conditions_data_impl(self, phases=None, statuses=None, countries=None,
                                   study_types=None, sponsor=None,
                                   int_type=None, cond_name=None,
                                   level1_filter=None):
        base_cte = self._build_filter_cte(phases, statuses, countries, study_types, sponsor)

        # Optional: restrict filtered_trials to those with a specific intervention type
        if int_type:
            safe_type = int_type.replace("'", "''")
            int_cte_sql = f""",
        int_type_trials AS (
            SELECT DISTINCT ft.nctid
            FROM filtered_trials ft
            JOIN interventions i
              ON ft.nctid = i.protocolsection_identificationmodule_nctid
            WHERE i.{INTERVENTION_TYPE_COL} = '{safe_type}'
        )"""
            join_src = "int_type_trials"
        else:
            int_cte_sql = ""
            join_src = "filtered_trials"

        # Base conditions WHERE (no level_1 filter — used for treemap)
        cond_parts = ["1=1"]
        if cond_name:
            safe = cond_name.replace("'", "''")
            cond_parts.append(f"c.condition_name ILIKE '%{safe}%'")
        cond_where_base = " AND ".join(cond_parts)

        # Typed WHERE adds level_1 cross-filter for non-treemap charts
        if level1_filter:
            safe = level1_filter.replace("'", "''")
            cond_where_typed = cond_where_base + f" AND c.level_1 = '{safe}'"
        else:
            cond_where_typed = cond_where_base

        def _make_full_cte(cond_where):
            return base_cte.rstrip() + int_cte_sql + f""",
        filtered_conditions AS (
            SELECT
                c.protocolsection_identificationmodule_nctid AS nctid,
                c.condition_id,
                c.condition_name,
                COALESCE(c.level_1, 'Unclassified') AS level_1,
                c.level_2
            FROM conditions c
            JOIN {join_src} ft
              ON c.protocolsection_identificationmodule_nctid = ft.nctid
            WHERE {cond_where}
        ),
        cond_trials AS (
            SELECT DISTINCT nctid FROM filtered_conditions
        )
        """

        full_cte_base  = _make_full_cte(cond_where_base)
        full_cte_typed = _make_full_cte(cond_where_typed)

        # ── KPIs ──────────────────────────────────────────────────────────
        kpi_row = self.con.execute(f"""
            {base_cte}
            SELECT COUNT(*) FROM filtered_trials
        """).fetchone()
        total = (kpi_row[0] or 0) if kpi_row else 0

        try:
            enroll_row = self.con.execute(f"""
                {base_cte}
                SELECT SUM(b.protocolsection_designmodule_enrollmentinfo_count)
                FROM base b
                JOIN filtered_trials ft
                  ON b.protocolsection_identificationmodule_nctid = ft.nctid
            """).fetchone()
            enroll = (enroll_row[0] or 0) if enroll_row else 0
        except Exception as e:
            print(f"Cond enrollment error: {e}"); enroll = 0

        try:
            uniq_row = self.con.execute(f"""
                {full_cte_typed}
                SELECT COUNT(DISTINCT LOWER(TRIM(condition_name))),
                       COUNT(DISTINCT level_1)
                FROM filtered_conditions
            """).fetchone()
            unique_cond = (uniq_row[0] or 0) if uniq_row else 0
            unique_cat  = (uniq_row[1] or 0) if uniq_row else 0
        except Exception as e:
            print(f"Cond uniq error: {e}"); unique_cond = unique_cat = 0

        def _fmt_n(n):
            if n >= 1_000_000: return f"{n / 1_000_000:.2f}M"
            if n >= 1_000:     return f"{n / 1_000:.1f}K"
            return f"{n:,.0f}"

        # ── Conditions treemap (all categories, no level_1 cross-filter) ──
        try:
            df_tree = self.con.execute(f"""
                {full_cte_base}
                SELECT level_1, COUNT(DISTINCT nctid) AS count
                FROM filtered_conditions
                WHERE level_1 IS NOT NULL AND level_1 != 'Unclassified'
                GROUP BY 1
                ORDER BY 2 DESC
            """).df()
        except Exception as e:
            print(f"Cond tree error: {e}"); df_tree = None

        # ── Phase distribution grouped bar ────────────────────────────────
        try:
            df_phase = self.con.execute(f"""
                {full_cte_typed}
                SELECT
                    p.protocolsection_designmodule_phases AS phase,
                    fc.level_1,
                    COUNT(DISTINCT fc.nctid) AS count
                FROM filtered_conditions fc
                JOIN phases p
                  ON fc.nctid = p.protocolsection_identificationmodule_nctid
                WHERE fc.level_1 IS NOT NULL
                  AND p.protocolsection_designmodule_phases IS NOT NULL
                GROUP BY 1, 2
                ORDER BY 1, 3 DESC
            """).df()
        except Exception as e:
            print(f"Cond phase error: {e}"); df_phase = None

        # ── Heatmap: level_1 × intervention type ──────────────────────────
        try:
            df_heatmap = self.con.execute(f"""
                {full_cte_typed}
                SELECT
                    fc.level_1,
                    COALESCE(i.{INTERVENTION_TYPE_COL}, 'No Intervention') AS int_type,
                    COUNT(DISTINCT fc.nctid) AS count
                FROM filtered_conditions fc
                LEFT JOIN interventions i
                  ON fc.nctid = i.protocolsection_identificationmodule_nctid
                WHERE fc.level_1 IS NOT NULL
                GROUP BY 1, 2
            """).df()
        except Exception as e:
            print(f"Cond heatmap error: {e}"); df_heatmap = None

        # ── Top 25 conditions (deduped) ───────────────────────────────────
        try:
            df_top_cond = self.con.execute(f"""
                {full_cte_typed}
                SELECT ANY_VALUE(condition_name) AS condition_name,
                       COUNT(DISTINCT nctid) AS count
                FROM filtered_conditions
                WHERE condition_name IS NOT NULL
                GROUP BY LOWER(TRIM(condition_name))
                ORDER BY 2 DESC
                LIMIT 25
            """).df()
        except Exception as e:
            print(f"Cond top25 error: {e}"); df_top_cond = None

        # ── Trend lines (top 8 categories by year) ────────────────────────
        try:
            df_trend = self.con.execute(f"""
                {full_cte_typed}
                SELECT
                    regexp_extract(
                        b.protocolsection_statusmodule_startdatestruct_date, '\\d{{4}}'
                    ) AS year,
                    fc.level_1,
                    COUNT(DISTINCT fc.nctid) AS count
                FROM filtered_conditions fc
                JOIN base b
                  ON fc.nctid = b.protocolsection_identificationmodule_nctid
                WHERE fc.level_1 IN (
                    SELECT level_1 FROM filtered_conditions
                    WHERE level_1 IS NOT NULL
                    GROUP BY 1 ORDER BY COUNT(DISTINCT nctid) DESC LIMIT 8
                )
                  AND regexp_extract(
                        b.protocolsection_statusmodule_startdatestruct_date, '\\d{{4}}'
                      ) >= '2000'
                  AND regexp_extract(
                        b.protocolsection_statusmodule_startdatestruct_date, '\\d{{4}}'
                      ) <= CAST(YEAR(CURRENT_DATE) AS VARCHAR)
                GROUP BY 1, 2
                ORDER BY 1
            """).df()
        except Exception as e:
            print(f"Cond trend error: {e}"); df_trend = None

        # ── Geo ───────────────────────────────────────────────────────────
        if countries:
            geo_filter = ("AND l." + COUNTRY_COL + " IN ("
                          + ", ".join(f"'{c}'" for c in countries) + ")")
        else:
            geo_filter = ""
        try:
            df_geo = self.con.execute(f"""
                {full_cte_typed}
                SELECT l.{COUNTRY_COL} AS country,
                       COUNT(DISTINCT l.protocolsection_identificationmodule_nctid) AS count
                FROM location l
                JOIN cond_trials ct
                  ON l.protocolsection_identificationmodule_nctid = ct.nctid
                WHERE l.{COUNTRY_COL} IS NOT NULL {geo_filter}
                GROUP BY 1
                ORDER BY 2 DESC
            """).df()
        except Exception as e:
            print(f"Cond geo error: {e}"); df_geo = None

        # ── Table ─────────────────────────────────────────────────────────
        try:
            df_table = self.con.execute(f"""
                {full_cte_typed},
                agg_phases AS (
                    SELECT protocolsection_identificationmodule_nctid AS nctid,
                           STRING_AGG(DISTINCT protocolsection_designmodule_phases, ', ') AS phase
                    FROM phases GROUP BY 1
                ),
                agg_int AS (
                    SELECT protocolsection_identificationmodule_nctid AS nctid,
                           MIN({INTERVENTION_NAME_COL}) AS int_name,
                           MIN(armgrouplabel)            AS int_description
                    FROM interventions GROUP BY 1
                )
                SELECT
                    fc.nctid,
                    regexp_extract(
                        b.protocolsection_statusmodule_startdatestruct_date, '\\d{{4}}'
                    )                                                        AS year,
                    b.protocolsection_statusmodule_overallstatus             AS status,
                    ap.phase,
                    fc.condition_name,
                    fc.condition_id,
                    ai.int_name,
                    ai.int_description
                FROM filtered_conditions fc
                JOIN base b ON fc.nctid = b.protocolsection_identificationmodule_nctid
                LEFT JOIN agg_phases ap ON fc.nctid = ap.nctid
                LEFT JOIN agg_int    ai ON fc.nctid = ai.nctid
                ORDER BY fc.nctid
                LIMIT 500
            """).df()
            df_table["nctid"] = df_table["nctid"].apply(
                lambda x: f"[{x}](https://clinicaltrials.gov/study/{x})"
            )
        except Exception as e:
            print(f"Cond table error: {e}"); df_table = None

        return {
            "kpi_trials":      f"{total:,}",
            "kpi_enrollment":  _fmt_n(enroll),
            "kpi_unique_cond": f"{unique_cond:,}",
            "kpi_unique_cat":  f"{unique_cat:,}",
            "cond_tree":       df_tree,
            "phase_dist":      df_phase,
            "heatmap":         df_heatmap,
            "top_conditions":  df_top_cond,
            "trend_lines":     df_trend,
            "geo_dist":        df_geo,
            "table_data":      df_table,
        }


    def get_outcomes_data(self, phases=None, statuses=None, countries=None,
                          study_types=None, sponsor=None,
                          outcome_type=None, sponsor_class=None,
                          primary_purpose=None, reporting_status=None):
        with self._lock:
            return self._get_outcomes_data_impl(
                phases, statuses, countries, study_types, sponsor,
                outcome_type, sponsor_class, primary_purpose, reporting_status,
            )

    def _build_outcomes_where(self, phases=None, statuses=None, countries=None,
                               study_types=None, sponsor=None,
                               outcome_type=None, sponsor_class=None,
                               primary_purpose=None, reporting_status=None):
        """WHERE clause for the outcomes table (pre-joined, no CTEs needed)."""
        c = ["1=1"]
        if phases:
            c.append(f"{PHASE_COL} IN ({', '.join(repr(p) for p in phases)})")
        if statuses:
            c.append(f"{OVERALL_STATUS_COL} IN ({', '.join(repr(s) for s in statuses)})")
        if countries:
            c.append(f"main_country IN ({', '.join(repr(x) for x in countries)})")
        if study_types:
            c.append(f"protocolsection_designmodule_studytype IN ({', '.join(repr(t) for t in study_types)})")
        if sponsor:
            c.append(f"{SPONSOR_COL} ILIKE '%{sponsor.replace(chr(39), chr(39)*2)}%'")
        if outcome_type:
            c.append(f"{OUTCOME_TYPE_COL} = '{outcome_type.replace(chr(39), chr(39)*2)}'")
        if sponsor_class:
            c.append(f"{SPONSOR_CLASS_COL} = '{sponsor_class.replace(chr(39), chr(39)*2)}'")
        if primary_purpose:
            c.append(f"{PRIMARY_PURPOSE_COL} = '{primary_purpose.replace(chr(39), chr(39)*2)}'")
        if reporting_status:
            c.append(f"{OUTCOME_STATUS_COL} = '{reporting_status.replace(chr(39), chr(39)*2)}'")
        return " AND ".join(c)

    def _get_outcomes_data_impl(self, phases=None, statuses=None, countries=None,
                                 study_types=None, sponsor=None,
                                 outcome_type=None, sponsor_class=None,
                                 primary_purpose=None, reporting_status=None):
        where = self._build_outcomes_where(
            phases, statuses, countries, study_types, sponsor,
            outcome_type, sponsor_class, primary_purpose, reporting_status,
        )

        def _fmt_n(n):
            if n >= 1_000_000: return f"{n / 1_000_000:.2f}M"
            if n >= 1_000:     return f"{n / 1_000:.1f}K"
            return f"{n:,.0f}"

        # ── KPIs ──────────────────────────────────────────────────────────
        try:
            k = self.con.execute(f"""
                SELECT
                    COUNT(DISTINCT protocolsection_identificationmodule_nctid) AS trials,
                    COUNT(*)                                                    AS total_outcomes,
                    SUM(CASE WHEN pvalue_mean < 0.05 THEN 1 ELSE 0 END)        AS significant,
                    COUNT(CASE WHEN pvalue_mean IS NOT NULL THEN 1 END)         AS with_pvalue,
                    MEDIAN(CASE WHEN pvalue_mean > 0 AND pvalue_mean <= 1
                                THEN pvalue_mean END)                           AS median_pval
                FROM outcomes
                WHERE {where}
            """).fetchone()
            kpi_trials   = (k[0] or 0) if k else 0
            kpi_total    = (k[1] or 0) if k else 0
            kpi_sig      = (k[2] or 0) if k else 0
            kpi_wpval    = (k[3] or 0) if k else 0
            kpi_med_pval = round(k[4], 4) if k and k[4] is not None else None
            pct_sig      = round(kpi_sig / kpi_wpval * 100, 1) if kpi_wpval else 0
        except Exception as e:
            print(f"Outcomes KPI error: {e}")
            kpi_trials = kpi_total = kpi_sig = kpi_wpval = 0
            kpi_med_pval = None; pct_sig = 0

        # ── P-value histogram (20 bins) ────────────────────────────────────
        try:
            df_pval = self.con.execute(f"""
                SELECT
                    ROUND(FLOOR(pvalue_mean * 20) / 20.0, 2) AS bin,
                    COUNT(*) AS count
                FROM outcomes
                WHERE {where}
                  AND pvalue_mean IS NOT NULL
                  AND pvalue_mean BETWEEN 0 AND 1
                GROUP BY 1
                ORDER BY 1
            """).df()
        except Exception as e:
            print(f"Outcomes pval hist error: {e}"); df_pval = None

        # ── Volcano plot: effect × p-value (up to 3000 pts) ───────────────
        try:
            df_volcano = self.con.execute(f"""
                SELECT
                    effect_mean,
                    pvalue_mean,
                    {OUTCOME_TYPE_COL} AS outcome_type,
                    {OUTCOME_TITLE_COL} AS title
                FROM outcomes
                WHERE {where}
                  AND effect_mean IS NOT NULL
                  AND pvalue_mean  IS NOT NULL
                  AND pvalue_mean  >  0
                  AND ABS(effect_mean) < 20
                ORDER BY RANDOM()
                LIMIT 3000
            """).df()
        except Exception as e:
            print(f"Outcomes volcano error: {e}"); df_volcano = None

        # ── Reporting status by sponsor class ─────────────────────────────
        try:
            df_report = self.con.execute(f"""
                SELECT
                    COALESCE({SPONSOR_CLASS_COL}, 'UNKNOWN') AS sponsor_class,
                    COALESCE({OUTCOME_STATUS_COL}, 'UNKNOWN') AS reporting_status,
                    COUNT(*) AS count
                FROM outcomes
                WHERE {where}
                GROUP BY 1, 2
                ORDER BY 1, 3 DESC
            """).df()
        except Exception as e:
            print(f"Outcomes reporting error: {e}"); df_report = None

        # ── Phase × Significance ──────────────────────────────────────────
        try:
            df_phase_sig = self.con.execute(f"""
                SELECT
                    COALESCE({PHASE_COL}, 'N/A') AS phase,
                    CASE WHEN pvalue_mean IS NULL  THEN 'UNKNOWN'
                         WHEN pvalue_mean < 0.05   THEN 'SIGNIFICANT'
                         ELSE 'NOT_SIGNIFICANT' END AS significance,
                    COUNT(DISTINCT protocolsection_identificationmodule_nctid) AS count
                FROM outcomes
                WHERE {where} AND {PHASE_COL} IS NOT NULL
                GROUP BY 1, 2
                ORDER BY 1
            """).df()
        except Exception as e:
            print(f"Outcomes phase×sig error: {e}"); df_phase_sig = None

        # ── Outcome type donut ────────────────────────────────────────────
        try:
            df_otype = self.con.execute(f"""
                SELECT
                    COALESCE({OUTCOME_TYPE_COL}, 'UNKNOWN') AS outcome_type,
                    COUNT(*) AS count
                FROM outcomes
                WHERE {where}
                GROUP BY 1
                ORDER BY 2 DESC
            """).df()
        except Exception as e:
            print(f"Outcomes type error: {e}"); df_otype = None

        # ── Param type bar ────────────────────────────────────────────────
        try:
            df_param = self.con.execute(f"""
                SELECT
                    COALESCE({OUTCOME_PARAM_COL}, 'UNKNOWN') AS param_type,
                    COUNT(*) AS count
                FROM outcomes
                WHERE {where} AND {OUTCOME_PARAM_COL} IS NOT NULL
                GROUP BY 1
                ORDER BY 2 DESC
                LIMIT 15
            """).df()
        except Exception as e:
            print(f"Outcomes param error: {e}"); df_param = None

        # ── Geo ───────────────────────────────────────────────────────────
        try:
            df_geo = self.con.execute(f"""
                SELECT main_country AS country,
                       COUNT(DISTINCT protocolsection_identificationmodule_nctid) AS count
                FROM outcomes
                WHERE {where} AND main_country IS NOT NULL
                GROUP BY 1
                ORDER BY 2 DESC
            """).df()
        except Exception as e:
            print(f"Outcomes geo error: {e}"); df_geo = None

        # ── Table ─────────────────────────────────────────────────────────
        try:
            df_table = self.con.execute(f"""
                SELECT
                    protocolsection_identificationmodule_nctid        AS nctid,
                    regexp_extract(
                        protocolsection_statusmodule_startdatestruct_date, '\\d{{4}}'
                    )                                                  AS year,
                    {OUTCOME_TYPE_COL}                                 AS outcome_type,
                    {OUTCOME_TITLE_COL}                                AS title,
                    {OUTCOME_PARAM_COL}                                AS param_type,
                    {OUTCOME_STATUS_COL}                               AS reporting_status,
                    {PHASE_COL}                                        AS phase,
                    ROUND(pvalue_mean, 4)                              AS pvalue,
                    ROUND(effect_mean, 4)                              AS effect_size,
                    main_country                                       AS country,
                    {SPONSOR_COL}                                      AS sponsor,
                    {SPONSOR_CLASS_COL}                                AS sponsor_class
                FROM outcomes
                WHERE {where}
                ORDER BY nctid
                LIMIT 500
            """).df()
            df_table["nctid"] = df_table["nctid"].apply(
                lambda x: f"[{x}](https://clinicaltrials.gov/study/{x})"
            )
        except Exception as e:
            print(f"Outcomes table error: {e}"); df_table = None

        return {
            "kpi_trials":     _fmt_n(kpi_trials),
            "kpi_total":      _fmt_n(kpi_total),
            "kpi_sig":        f"{pct_sig}%",
            "kpi_sig_sub":    f"{_fmt_n(kpi_sig)} of {_fmt_n(kpi_wpval)} with p-value",
            "kpi_med_pval":   f"{kpi_med_pval}" if kpi_med_pval is not None else "N/A",
            "pval_hist":      df_pval,
            "volcano":        df_volcano,
            "reporting":      df_report,
            "phase_sig":      df_phase_sig,
            "outcome_types":  df_otype,
            "param_types":    df_param,
            "geo_dist":       df_geo,
            "table_data":     df_table,
        }


engine = DataEngine()
