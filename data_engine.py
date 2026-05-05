import duckdb
from datetime import datetime
from aws_client import setup_duckdb_s3
from constants import (TABLES, SPONSOR_COL, COUNTRY_COL, DELAYED_STATUSES,
                       INTERVENTION_TYPE_COL, INTERVENTION_NAME_COL)


class DataEngine:
    def __init__(self):
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
            self.con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{path}')")

    def _load_filter_options(self):
        """Load unique values for each filter dropdown once at startup."""
        def _fetch(sql):
            try:
                return [r[0] for r in self.con.execute(sql).fetchall()]
            except Exception as e:
                print(f"Filter options load error: {e}")
                return []

        return {
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
        }

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
        base_cte = self._build_filter_cte(phases, statuses, countries, study_types, sponsor)
        delayed_sql = ", ".join(f"'{s}'" for s in DELAYED_STATUSES)

        # ── KPIs ──────────────────────────────────────────────────────
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
                               int_name=None):
        base_cte = self._build_filter_cte(phases, statuses, countries, study_types, sponsor)

        # Interventions-specific WHERE conditions
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
        int_where = " AND ".join(int_conditions)

        full_cte = base_cte.rstrip() + f""",
        filtered_interventions AS (
            SELECT
                i.protocolsection_identificationmodule_nctid AS nctid,
                i.{INTERVENTION_TYPE_COL}                    AS int_type,
                i.{INTERVENTION_NAME_COL}                    AS int_name,
                i.entity_canonical_name,
                i.armgrouplabel,
                i.sem_level_1,
                i.sem_level_2,
                i.sem_level_3
            FROM interventions i
            JOIN filtered_trials ft
              ON i.protocolsection_identificationmodule_nctid = ft.nctid
            WHERE {int_where}
        ),
        int_trials AS (
            SELECT DISTINCT nctid FROM filtered_interventions
        )
        """

        # ── KPIs ──────────────────────────────────────────────────────
        kpi_row = self.con.execute(f"""
            {full_cte}
            SELECT
                COUNT(DISTINCT nctid)                AS total_trials,
                COUNT(DISTINCT int_name)             AS unique_interventions,
                COUNT(DISTINCT entity_canonical_name) AS unique_conditions
            FROM filtered_interventions
        """).fetchone()

        total       = kpi_row[0] or 0
        unique_int  = kpi_row[1] or 0
        unique_cond = kpi_row[2] or 0

        try:
            enroll_row = self.con.execute(f"""
                {full_cte}
                SELECT SUM(b.protocolsection_designmodule_enrollmentinfo_count)
                FROM base b
                JOIN int_trials it ON b.protocolsection_identificationmodule_nctid = it.nctid
            """).fetchone()
            enroll = (enroll_row[0] or 0) if enroll_row else 0
        except Exception as e:
            print(f"Int enrollment error: {e}")
            enroll = 0

        def _fmt_n(n):
            if n >= 1_000_000: return f"{n / 1_000_000:.2f}M"
            if n >= 1_000:     return f"{n / 1_000:.1f}K"
            return f"{n:,.0f}"

        # ── Intervention Types (treemap) ───────────────────────────────
        try:
            df_types = self.con.execute(f"""
                {full_cte}
                SELECT int_type, COUNT(DISTINCT nctid) AS count
                FROM filtered_interventions
                WHERE int_type IS NOT NULL
                GROUP BY 1
                ORDER BY 2 DESC
            """).df()
        except Exception as e:
            print(f"Int types error: {e}"); df_types = None

        # ── Dynamics stacked bar ───────────────────────────────────────
        try:
            df_dynamics = self.con.execute(f"""
                {full_cte}
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
                GROUP BY 1, 2
                ORDER BY 1
            """).df()
        except Exception as e:
            print(f"Dynamics error: {e}"); df_dynamics = None

        # ── Top 25 Interventions ───────────────────────────────────────
        try:
            df_top_int = self.con.execute(f"""
                {full_cte}
                SELECT int_name, COUNT(DISTINCT nctid) AS count
                FROM filtered_interventions
                WHERE int_name IS NOT NULL
                GROUP BY 1
                ORDER BY 2 DESC
                LIMIT 25
            """).df()
        except Exception as e:
            print(f"Top interventions error: {e}"); df_top_int = None

        # ── Top 25 Conditions ──────────────────────────────────────────
        try:
            df_top_cond = self.con.execute(f"""
                {full_cte}
                SELECT entity_canonical_name AS condition, COUNT(DISTINCT nctid) AS count
                FROM filtered_interventions
                WHERE entity_canonical_name IS NOT NULL
                GROUP BY 1
                ORDER BY 2 DESC
                LIMIT 25
            """).df()
        except Exception as e:
            print(f"Top conditions error: {e}"); df_top_cond = None

        # ── Word Cloud (top 50 by raw count for size weighting) ────────
        try:
            df_wordcloud = self.con.execute(f"""
                {full_cte}
                SELECT int_name, COUNT(*) AS count
                FROM filtered_interventions
                WHERE int_name IS NOT NULL
                GROUP BY 1
                ORDER BY 2 DESC
                LIMIT 50
            """).df()
        except Exception as e:
            print(f"Word cloud error: {e}"); df_wordcloud = None

        # ── GeoMap ────────────────────────────────────────────────────
        if countries:
            geo_filter = "AND l." + COUNTRY_COL + " IN (" + ", ".join(f"'{c}'" for c in countries) + ")"
        else:
            geo_filter = ""
        try:
            df_geo = self.con.execute(f"""
                {full_cte}
                SELECT
                    l.{COUNTRY_COL} AS country,
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
                {full_cte},
                agg_phases AS (
                    SELECT
                        protocolsection_identificationmodule_nctid AS nctid,
                        STRING_AGG(DISTINCT protocolsection_designmodule_phases, ', ') AS phase
                    FROM phases GROUP BY 1
                )
                SELECT
                    fi.nctid,
                    regexp_extract(
                        b.protocolsection_statusmodule_startdatestruct_date, '\\d{{4}}'
                    )                                                             AS year,
                    b.protocolsection_identificationmodule_brieftitle             AS title,
                    b.protocolsection_statusmodule_overallstatus                  AS status,
                    ap.phase,
                    b.protocolsection_designmodule_studytype                      AS study_type,
                    fi.int_type,
                    fi.armgrouplabel                                               AS arm_label,
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


engine = DataEngine()
