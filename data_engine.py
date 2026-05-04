import duckdb
from aws_client import setup_duckdb_s3
from constants import TABLES


class DataEngine:
    def __init__(self):
        # Create an in-memory DuckDB connection
        self.con = duckdb.connect(database=':memory:')
        setup_duckdb_s3(self.con)
        self._initialize_views()

    def _initialize_views(self):
        """Create lazy views for S3 Parquet files. No data is downloaded yet."""
        for name, path in TABLES.items():
            self.con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{path}')")

    def get_overview_stats(self, phases):
        """
        Aggregates data across base, location, and phases.
        DuckDB pushes the 'WHERE' filter down to S3 to minimize data transfer.
        """
        # Handling SQL IN clause for 1 or more elements
        phase_filter = f"IN {tuple(phases)}" if len(phases) > 1 else f"= '{phases[0]}'"

        query = f"""
            SELECT 
                l.protocolsection_contactslocationsmodule_locations_country as country,
                COUNT(DISTINCT b.protocolsection_identificationmodule_nctid) as trial_count
            FROM base b
            JOIN phases p ON b.protocolsection_identificationmodule_nctid = p.protocolsection_identificationmodule_nctid
            JOIN locations l ON b.protocolsection_identificationmodule_nctid = l.protocolsection_identificationmodule_nctid
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT 15
        """


        return self.con.execute(query).df()

    def get_overview_data(self, phases):
        """
        Аналитика для Overview: защита от дублирования строк (Fan-out trap)
        за счет использования CTE (WITH filtered_trials).
        """
        # Формируем строку для IN (...): 'Phase 1', 'Phase 2'
        phases_sql = ", ".join([f"'{p}'" for p in phases])

        # 1. CTE: Находим уникальные NCT ID для выбранных фаз
        # Это мгновенно отсечет миллионы ненужных строк в S3
        base_cte = f"""
            WITH filtered_trials AS (
                SELECT DISTINCT protocolsection_identificationmodule_nctid AS nctid
                FROM phases
            )
        """

        # 2. Расчет KPI (Только таблица base + наш фильтр)
        kpi_query = f"""
            {base_cte}
            SELECT 
                COUNT(b.protocolsection_identificationmodule_nctid) as total_trials,
                SUM(b.protocolsection_designmodule_enrollmentinfo_count) as total_enrollment,
                SUM(b.hasresults) as trials_with_results,
                SUM(CASE WHEN b.protocolsection_statusmodule_overallstatus ILIKE '%COMPLETED%' THEN 1 ELSE 0 END) as completed_trials
            FROM base b
            JOIN filtered_trials ft ON b.protocolsection_identificationmodule_nctid = ft.nctid
        """
        kpis_raw = self.con.execute(kpi_query).fetchone()

        # Распаковываем и форматируем KPI (защита от None, если данных нет)
        total_trials = kpis_raw[0] if kpis_raw[0] else 0
        enrollment = kpis_raw[1] if kpis_raw[1] else 0
        has_results = kpis_raw[2] if kpis_raw[2] else 0
        completed = kpis_raw[3] if kpis_raw[3] else 0

        # Считаем проценты для UI
        pct_results = round((has_results / total_trials * 100), 1) if total_trials > 0 else 0
        pct_completed = round((completed / total_trials * 100), 1) if total_trials > 0 else 0

        # 3. Данные для Donut Chart (Распределение по статусам)
        status_query = f"""
            {base_cte}
            SELECT 
                b.protocolsection_statusmodule_overallstatus as status,
                COUNT(b.protocolsection_identificationmodule_nctid) as count
            FROM base b
            JOIN filtered_trials ft ON b.protocolsection_identificationmodule_nctid = ft.nctid
            GROUP BY 1
            ORDER BY 2 DESC
        """
        df_status = self.con.execute(status_query).df()

        # 4. Данные для Geo Bar Chart (Таблица location + наш фильтр)
        # ВНИМАНИЕ: Замени 'YOUR_COUNTRY_COLUMN' на реальное имя обрезанной колонки
        country_col = "protocolsection_contactslocationsmodule_locations_country"  # Предположительное имя

        geo_query = f"""
            {base_cte}
            SELECT 
                l.{country_col} AS country,
                COUNT(DISTINCT l.protocolsection_identificationmodule_nctid) as count
            FROM location l
            JOIN filtered_trials ft ON l.protocolsection_identificationmodule_nctid = ft.nctid
            WHERE l.{country_col} IS NOT NULL
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT 15
        """

        try:
            df_geo = self.con.execute(geo_query).df()
        except Exception as e:
            print(f"Ошибка чтения Location. Убедитесь, что колонка страны называется верно: {e}")
            df_geo = None

        # Отдаем готовый словарь в Dash
        return {
            "kpi_trials": f"{total_trials:,}",
            "kpi_enrollment": f"{enrollment:,.0f}",
            "kpi_results": f"{pct_results}%",
            "kpi_completion": f"{pct_completed}%",
            "status_dist": df_status,
            "geo_dist": df_geo
        }


# Singleton instance to be used across the app
engine = DataEngine()