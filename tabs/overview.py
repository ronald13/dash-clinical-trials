from dash import dcc, html, callback, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from data_engine import engine


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_label(v):
    """Smart number label: avoids '0.00K' for small values."""
    if v is None:
        return ""
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v / 1_000:.1f}K"
    return str(int(v))


def _empty_fig(msg="No data"):
    fig = go.Figure()
    fig.add_annotation(text=msg, showarrow=False, font={"size": 14, "color": "#bbb"})
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis={"visible": False}, yaxis={"visible": False},
        margin=dict(t=10, b=10, l=10, r=10),
    )
    return fig


def _chart_card(header, graph_id, height=300):
    return dbc.Card([
        dbc.CardHeader(header, className="bg-white fw-semibold border-0 pt-3 pb-0",
                       style={"fontSize": "0.95rem", "color": "#333"}),
        dbc.CardBody(dcc.Loading(
            dcc.Graph(id=graph_id, style={"height": f"{height}px"},
                      config={"displayModeBar": False}),
            color="#9b9be4",
        )),
    ], className="shadow-sm border-0 h-100",
       style={"borderRadius": "12px", "border": "none",
              "boxShadow": "0 2px 10px rgba(0,0,0,0.07)"})


def _kpi_card(title, value_id, icon_cls, gradient,
              subtitle_id=None, subtitle_cls="text-muted small"):
    icon = html.Div(
        html.I(className=f"bi {icon_cls}",
               style={"fontSize": "1.4rem", "color": "white"}),
        style={
            "width": "50px", "height": "50px", "borderRadius": "12px",
            "background": gradient, "flexShrink": "0",
            "display": "flex", "alignItems": "center", "justifyContent": "center",
        },
    )
    return dbc.Card([
        dbc.CardBody(
            html.Div([
                html.Div([
                    html.P(title, className="text-muted fw-semibold mb-1",
                           style={"fontSize": "0.75rem", "textTransform": "uppercase",
                                  "letterSpacing": "0.7px"}),
                    html.H3(id=value_id, className="mb-0 fw-bold",
                            style={"fontSize": "1.85rem", "lineHeight": "1.1"}),
                    html.Small(id=subtitle_id,
                               className=f"{subtitle_cls} mt-1 d-block")
                    if subtitle_id else html.Div(),
                ], style={"flex": "1", "minWidth": "0"}),
                icon,
            ], style={"display": "flex", "alignItems": "flex-start",
                      "justifyContent": "space-between", "gap": "10px"})
        )
    ], className="border-0 h-100",
       style={"borderRadius": "12px", "border": "none",
              "boxShadow": "0 2px 10px rgba(0,0,0,0.07)"})


# ── Layout ────────────────────────────────────────────────────────────────────

# Phase display order for duration chart
_PHASE_ORDER = ["PHASE1", "PHASE2", "PHASE3", "PHASE4", "NA", "N/A"]
_PHASE_COLORS = {
    "PHASE1": "#4e79a7", "PHASE2": "#f28e2b",
    "PHASE3": "#e15759", "PHASE4": "#76b7b2",
    "NA": "#bab0ac",     "N/A":  "#bab0ac",
}


def render_layout():
    return html.Div([

        # Header
        dbc.Card([
            dbc.CardBody(html.Div([
                html.H4("Clinical Trials Insights",
                        className="mb-0 fw-bold d-inline me-2",
                        style={"fontSize": "1.3rem"}),
                html.Span("|", className="text-muted me-2"),
                html.Span("Last update: ", className="text-muted me-1",
                          style={"fontSize": "0.9rem"}),
                html.Span(id="last-update-date", className="fw-bold fst-italic",
                          style={"color": "#2c6fad", "fontSize": "0.9rem"}),
                html.Span("  ·  Overview", className="text-muted ms-2",
                          style={"fontSize": "0.85rem"}),
            ], className="d-flex align-items-center"), className="py-3")
        ], className="border-0 mb-4",
           style={"borderRadius": "12px", "border": "none",
                  "boxShadow": "0 2px 10px rgba(0,0,0,0.07)"}),

        # KPI row
        dbc.Row([
            dbc.Col(_kpi_card(
                "Total Trials", "kpi-trials", "bi-activity",
                "linear-gradient(135deg,#667eea,#764ba2)",
                subtitle_id="kpi-trials-new",
                subtitle_cls="text-success fw-semibold small"), width=3),
            dbc.Col(_kpi_card(
                "Total Enrollment", "kpi-enrollment", "bi-person-fill",
                "linear-gradient(135deg,#11998e,#38ef7d)"), width=3),
            dbc.Col(_kpi_card(
                "% Has Results", "kpi-results", "bi-info-circle-fill",
                "linear-gradient(135deg,#f093fb,#f5576c)",
                subtitle_id="kpi-results-sub"), width=3),
            dbc.Col(_kpi_card(
                "Completion Rate", "kpi-completion", "bi-check-circle-fill",
                "linear-gradient(135deg,#f6d365,#fda085)"), width=3),
        ], className="mb-4 g-3", style={"paddingTop": "4px"}),

        # Charts row
        dbc.Row([
            dbc.Col(_chart_card("Delay Status",        "chart-delay-donut", 290), width=4),
            dbc.Col(_chart_card("Sex Distribution",    "chart-sex-donut",   290), width=4),
            dbc.Col(_chart_card("Status Distribution", "chart-status-bar",  290), width=4),
        ], className="mb-4 g-3"),

        # Table
        dbc.Card([
            dbc.CardHeader("Table View",
                           className="bg-white fw-semibold border-0 pt-3 pb-0",
                           style={"fontSize": "0.95rem", "color": "#333"}),
            dbc.CardBody(dcc.Loading(
                dash_table.DataTable(
                    id="trials-table",
                    columns=[
                        {"name": "ID",               "id": "nctid",      "presentation": "markdown"},
                        {"name": "Year",             "id": "year"},
                        {"name": "Study Completion", "id": "completion"},
                        {"name": "Title",            "id": "title"},
                        {"name": "Status",           "id": "status"},
                        {"name": "Phase",            "id": "phase"},
                        {"name": "Study Type",       "id": "study_type"},
                        {"name": "Enrollment",       "id": "enrollment"},
                        {"name": "Sponsor",          "id": "sponsor"},
                        {"name": "Country",          "id": "country"},
                    ],
                    page_size=10,
                    page_action="native",
                    sort_action="native",
                    filter_action="native",
                    markdown_options={"html": False},
                    tooltip_delay=0,
                    tooltip_duration=4000,
                    style_table={"overflowX": "auto"},
                    style_cell={
                        "fontFamily": "inherit",
                        "fontSize": "13px",
                        "padding": "8px 12px",
                        "overflow": "hidden",
                        "textOverflow": "ellipsis",
                        "maxWidth": "200px",
                        "whiteSpace": "nowrap",
                    },
                    style_cell_conditional=[
                        {"if": {"column_id": "title"}, "maxWidth": "260px"},
                    ],
                    style_header={
                        "backgroundColor": "#f8f9fa",
                        "fontWeight": "700",
                        "border": "1px solid #eee",
                        "fontSize": "11px",
                        "textTransform": "uppercase",
                        "letterSpacing": "0.4px",
                        "color": "#555",
                    },
                    style_data={"border": "1px solid #f5f5f5"},
                    style_data_conditional=[
                        {"if": {"filter_query": '{status} = "COMPLETED"',          "column_id": "status"},
                         "color": "#27ae60", "fontWeight": "600"},
                        {"if": {"filter_query": '{status} = "RECRUITING"',         "column_id": "status"},
                         "color": "#2980b9", "fontWeight": "600"},
                        {"if": {"filter_query": '{status} = "TERMINATED"',         "column_id": "status"},
                         "color": "#c0392b", "fontWeight": "600"},
                        {"if": {"filter_query": '{status} = "WITHDRAWN"',          "column_id": "status"},
                         "color": "#e67e22", "fontWeight": "600"},
                        {"if": {"filter_query": '{status} = "NOT_YET_RECRUITING"', "column_id": "status"},
                         "color": "#8e44ad", "fontWeight": "600"},
                        {"if": {"row_index": "odd"}, "backgroundColor": "#fafafa"},
                    ],
                ),
                color="#9b9be4",
            )),
        ], className="border-0 mb-4",
           style={"borderRadius": "12px", "border": "none",
                  "boxShadow": "0 2px 10px rgba(0,0,0,0.07)"}),

        # GeoMap + Sponsors
        dbc.Row([
            dbc.Col(_chart_card("GeoMap",          "chart-geomap",   380), width=6),
            dbc.Col(_chart_card("Top 25 Sponsors", "chart-sponsors", 380), width=6),
        ], className="mb-4 g-3"),

        # Trial Duration Analysis
        dbc.Row([
            dbc.Col(_chart_card(
                "Trial Duration by Phase — median months from start to completion",
                "chart-duration-bar", 320), width=12),
        ], className="mb-4 g-3"),

    ], style={"padding": "6px 8px"})


# ── Callback ──────────────────────────────────────────────────────────────────

@callback(
    Output("kpi-trials",         "children"),
    Output("kpi-trials-new",     "children"),
    Output("kpi-enrollment",     "children"),
    Output("kpi-results",        "children"),
    Output("kpi-results-sub",    "children"),
    Output("kpi-completion",     "children"),
    Output("last-update-date",   "children"),
    Output("chart-delay-donut",  "figure"),
    Output("chart-sex-donut",    "figure"),
    Output("chart-status-bar",   "figure"),
    Output("trials-table",       "data"),
    Output("trials-table",       "tooltip_data"),
    Output("chart-geomap",       "figure"),
    Output("chart-sponsors",     "figure"),
    Output("chart-duration-bar", "figure"),
    Input("apply-filters-btn",   "n_clicks"),
    State("phase-dropdown",      "value"),
    State("status-dropdown",     "value"),
    State("country-dropdown",    "value"),
    State("study-type-dropdown", "value"),
    State("sponsor-input",       "value"),
)
def update_overview(_, phases, statuses, countries, study_types, sponsor):
    data = engine.get_overview_data(
        phases=phases or [],
        statuses=statuses or [],
        countries=countries or [],
        study_types=study_types or [],
        sponsor=sponsor or "",
    )

    # ── Delay Status donut ────────────────────────────────────────────
    df_delay = data["delay_dist"]
    if df_delay is not None and not df_delay.empty:
        total_k = _fmt_label(df_delay["count"].sum())
        DELAY_COLORS = {"On Track": "#5bc0de", "Delayed": "#1a5276"}
        fig_delay = px.pie(df_delay, names="status_group", values="count", hole=0.65,
                           color="status_group", color_discrete_map=DELAY_COLORS)
        fig_delay.update_traces(
            textinfo="none",
            hovertemplate="<b>%{label}</b><br>Trials: %{value:,}<br>% of total: %{percent}<extra></extra>",
        )
        fig_delay.add_annotation(text=total_k, x=0.5, y=0.5,
                                  font=dict(size=18, color="#333"), showarrow=False)
        fig_delay.update_layout(
            margin=dict(t=10, b=30, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", y=-0.05, x=0.5, xanchor="center", font=dict(size=11)),
                    )
    else:
        fig_delay = _empty_fig()

    # ── Sex Distribution donut ────────────────────────────────────────
    df_sex = data["sex_dist"]
    if df_sex is not None and not df_sex.empty:
        total_k = _fmt_label(df_sex["count"].sum())
        SEX_COLORS = {"ALL": "#5bc0de", "FEMALE": "#1a5276", "MALE": "#f0a500"}
        fig_sex = px.pie(df_sex, names="sex", values="count", hole=0.65,
                         color="sex", color_discrete_map=SEX_COLORS)
        fig_sex.update_traces(
            textinfo="none",
            hovertemplate="<b>%{label}</b><br>Trials: %{value:,}<br>% of total: %{percent}<extra></extra>",
        )
        fig_sex.add_annotation(text=total_k, x=0.5, y=0.5,
                                font=dict(size=18, color="#333"), showarrow=False)
        fig_sex.update_layout(
            margin=dict(t=10, b=30, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", y=-0.05, x=0.5, xanchor="center", font=dict(size=11)),
                    )
    else:
        fig_sex = _empty_fig()

    # ── Status Distribution bar ───────────────────────────────────────
    df_status = data["status_dist"]
    if df_status is not None and not df_status.empty:
        df_status = df_status.copy()
        total_s = df_status["count"].sum()
        df_status["pct"] = (df_status["count"] / total_s * 100).round(1)
        fig_status = px.bar(df_status, x="count", y="status", orientation="h",
                            color_discrete_sequence=["#9b9be4"],
                            custom_data=["pct"])
        fig_status.update_traces(
            text=[_fmt_label(v) for v in df_status["count"]],
            textposition="outside", cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>Trials: %{x:,.0f}<br>% of total: %{customdata[0]:.1f}%<extra></extra>",
        )
        fig_status.update_layout(
            yaxis={"categoryorder": "total ascending", "title": "",
                   "tickfont": {"size": 11}, "ticklabelstandoff": 8},
            xaxis={"title": "", "showticklabels": False},
            margin=dict(t=10, b=10, l=10, r=55),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            bargap=0.3,
        )
    else:
        fig_status = _empty_fig()

    # ── Table + title tooltips ────────────────────────────────────────
    df_table = data.get("table_data")
    if df_table is not None and not df_table.empty:
        table_records = df_table.to_dict("records")
        tooltip_data = [
            {"title": {"value": row.get("title") or "", "type": "text"}}
            for row in table_records
        ]
    else:
        table_records, tooltip_data = [], []

    # ── GeoMap — minimalist ───────────────────────────────────────────
    df_geo = data.get("geo_dist")
    if df_geo is not None and not df_geo.empty:
        df_geo = df_geo.copy()
        df_geo["pct"] = (df_geo["count"] / df_geo["count"].sum() * 100).round(1)
        fig_geo = px.choropleth(
            df_geo,
            locations="country", locationmode="country names",
            color="count",
            color_continuous_scale=[[0, "#d6eaf8"], [1, "#1a5276"]],
            custom_data=["country", "count", "pct"],
        )
        fig_geo.update_traces(
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Trials: %{customdata[1]:,}<br>"
                "% of total: %{customdata[2]:.1f}%"
                "<extra></extra>"
            ),
            marker_line_color="white", marker_line_width=0.5,
        )
        fig_geo.update_layout(
            margin=dict(t=0, b=0, l=0, r=0),
            paper_bgcolor="white",
            geo=dict(
            bgcolor="white",
            showframe=False,
            showcoastlines=False,
            showland=True, landcolor="#f0f0f0",
            showocean=True, oceancolor="white",
            showlakes=False,
            showcountries=True,        # ← вместо showborders
            countrycolor="#e0e0e0",    # ← вместо bordercolor
            # borderwidth не нужен — толщина линий страновых границ не настраивается
            projection_type="natural earth",
        ),
            coloraxis_showscale=False,
                    )
    else:
        fig_geo = _empty_fig("No geodata")

    # ── Top 25 Sponsors ───────────────────────────────────────────────
    df_sponsors = data.get("sponsor_dist")
    if df_sponsors is not None and not df_sponsors.empty:
        df_sponsors = df_sponsors.copy()
        total_sp = df_sponsors["count"].sum()
        df_sponsors["pct"] = (df_sponsors["count"] / total_sp * 100).round(1)
        fig_sponsors = px.bar(df_sponsors, x="count", y="sponsor", orientation="h",
                              color_discrete_sequence=["#f0a500"],
                              custom_data=["pct"])
        fig_sponsors.update_traces(
            text=[_fmt_label(v) for v in df_sponsors["count"]],
            textposition="outside", cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>Trials: %{x:,.0f}<br>% of total: %{customdata[0]:.1f}%<extra></extra>",
        )
        fig_sponsors.update_layout(
            yaxis={"categoryorder": "total ascending", "title": "",
                   "tickfont": {"size": 11}, "ticklabelstandoff": 8},
            xaxis={"title": "", "showticklabels": False},
            margin=dict(t=10, b=10, l=10, r=55),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            bargap=0.25,
        )
    else:
        fig_sponsors = _empty_fig("No sponsor data")

    # ── Trial Duration by Phase ───────────────────────────────────────
    df_dur = data.get("duration_dist")
    if df_dur is not None and not df_dur.empty:
        df_dur = df_dur.copy()
        # Remove unknown/unspecified phases
        df_dur = df_dur[~df_dur["phase"].isin(["N/A", "NA"])]

    if df_dur is not None and not df_dur.empty:
        df_dur["_order"] = df_dur["phase"].apply(
            lambda p: _PHASE_ORDER.index(p) if p in _PHASE_ORDER else 99
        )
        df_dur = df_dur.sort_values("_order", ascending=False)

        fig_dur = px.bar(
            df_dur, x="median_months", y="phase", orientation="h",
            color="phase", color_discrete_map=_PHASE_COLORS,
            custom_data=["median_months", "avg_months", "trial_count"],
        )
        fig_dur.update_traces(
            text=[f"{v:.0f}" for v in df_dur["median_months"]],
            textposition="outside", cliponaxis=False,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Median: %{customdata[0]:.1f} months<br>"
                "Average: %{customdata[1]:.1f} months<br>"
                "Trials used: %{customdata[2]:,}"
                "<extra></extra>"
            ),
        )
        fig_dur.update_layout(
            yaxis={"title": "", "tickfont": {"size": 12}, "categoryorder": "array",
                   "categoryarray": list(reversed(df_dur["phase"].tolist()))},
            xaxis={"title": "Median duration (months)", "tickfont": {"size": 11}},
            margin=dict(t=10, b=30, l=10, r=65),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False, bargap=0.4,         )
    else:
        fig_dur = _empty_fig("No duration data (dates missing or not completed)")

    return (
        data["kpi_trials"],
        data["kpi_trials_new"],
        data["kpi_enrollment"],
        data["kpi_results"],
        data["kpi_results_sub"],
        data["kpi_completion"],
        data["last_update"],
        fig_delay,
        fig_sex,
        fig_status,
        table_records,
        tooltip_data,
        fig_geo,
        fig_sponsors,
        fig_dur,
    )
