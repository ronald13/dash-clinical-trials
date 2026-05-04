from dash import dcc, html, callback, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from data_engine import engine


# ── Helpers ───────────────────────────────────────────────────────────────────

def _empty_fig(msg="No data"):
    fig = go.Figure()
    fig.add_annotation(text=msg, showarrow=False, font={"size": 14, "color": "#aaa"})
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis={"visible": False}, yaxis={"visible": False},
        margin=dict(t=10, b=10, l=10, r=10),
    )
    return fig


def _card(header, graph_id, height=300):
    return dbc.Card([
        dbc.CardHeader(header, className="bg-white fw-bold border-0 pt-3 pb-0",
                       style={"fontSize": "1rem"}),
        dbc.CardBody(dcc.Loading(dcc.Graph(id=graph_id, style={"height": f"{height}px"},
                                           config={"displayModeBar": False}))),
    ], className="shadow-sm border-0 h-100", style={"borderRadius": "12px"})


def _kpi_card(title, value_id, icon_cls, gradient, subtitle_id=None):
    icon = html.Div(
        html.I(className=f"bi {icon_cls}", style={"fontSize": "1.5rem", "color": "white"}),
        style={
            "width": "52px", "height": "52px", "borderRadius": "14px",
            "background": gradient,
            "display": "flex", "alignItems": "center", "justifyContent": "center",
            "flexShrink": "0",
        },
    )
    return dbc.Card([
        dbc.CardBody(
            html.Div([
                html.Div([
                    html.P(title, className="text-muted fw-bold mb-1",
                           style={"fontSize": "0.78rem", "textTransform": "uppercase",
                                  "letterSpacing": "0.6px"}),
                    html.H3(id=value_id, className="mb-0 fw-bold", style={"fontSize": "1.9rem"}),
                    html.Small(id=subtitle_id, className="text-muted mt-1 d-block")
                    if subtitle_id else html.Div(),
                ], style={"flex": "1"}),
                icon,
            ], style={"display": "flex", "alignItems": "flex-start",
                      "justifyContent": "space-between", "gap": "12px"})
        )
    ], className="shadow-sm border-0 h-100", style={"borderRadius": "12px"})


# ── Layout ────────────────────────────────────────────────────────────────────

def render_layout():
    return html.Div([

        # Header banner
        dbc.Card([
            dbc.CardBody([
                html.Div([
                    html.H4("Clinical Trials Insights",
                            className="mb-0 fw-bold d-inline me-2"),
                    html.Span("|", className="text-muted me-2"),
                    html.Span("Last update: ", className="text-muted me-1",
                              style={"fontSize": "0.9rem"}),
                    html.Span(id="last-update-date", className="fw-bold fst-italic",
                              style={"color": "#2c6fad"}),
                ], className="d-flex align-items-center"),
                html.Small("Overview", className="text-muted"),
            ])
        ], className="shadow-sm border-0 mb-4", style={"borderRadius": "12px"}),

        # KPI row
        dbc.Row([
            dbc.Col(_kpi_card(
                "Total Trials", "kpi-trials", "bi-activity",
                "linear-gradient(135deg,#667eea,#764ba2)"), width=3),
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
        ], className="mb-4 g-3"),

        # Charts row
        dbc.Row([
            dbc.Col(_card("Delay Status",       "chart-delay-donut",  280), width=4),
            dbc.Col(_card("Sex Distribution",   "chart-sex-donut",    280), width=4),
            dbc.Col(_card("Status Distribution","chart-status-bar",   280), width=4),
        ], className="mb-4 g-3"),

        # Table
        dbc.Card([
            dbc.CardHeader("Table View", className="bg-white fw-bold border-0 pt-3 pb-0",
                           style={"fontSize": "1rem"}),
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
                        {"name": "Sponsor",          "id": "sponsor"},
                        {"name": "Country",          "id": "country"},
                    ],
                    page_size=10,
                    page_action="native",
                    sort_action="native",
                    filter_action="native",
                    markdown_options={"html": False},
                    style_table={"overflowX": "auto"},
                    style_cell={
                        "fontFamily": "inherit",
                        "fontSize": "13px",
                        "padding": "8px 12px",
                        "overflow": "hidden",
                        "textOverflow": "ellipsis",
                        "maxWidth": "220px",
                        "whiteSpace": "nowrap",
                    },
                    style_header={
                        "backgroundColor": "#f8f9fa",
                        "fontWeight": "700",
                        "border": "1px solid #dee2e6",
                        "fontSize": "12px",
                        "textTransform": "uppercase",
                        "letterSpacing": "0.4px",
                    },
                    style_data={"border": "1px solid #f0f0f0"},
                    style_data_conditional=[
                        {"if": {"filter_query": '{status} = "COMPLETED"',  "column_id": "status"},
                         "color": "#28a745", "fontWeight": "600"},
                        {"if": {"filter_query": '{status} = "RECRUITING"', "column_id": "status"},
                         "color": "#007bff", "fontWeight": "600"},
                        {"if": {"filter_query": '{status} = "TERMINATED"', "column_id": "status"},
                         "color": "#dc3545", "fontWeight": "600"},
                        {"if": {"filter_query": '{status} = "WITHDRAWN"',  "column_id": "status"},
                         "color": "#fd7e14", "fontWeight": "600"},
                        {"if": {"row_index": "odd"},
                         "backgroundColor": "#fafafa"},
                    ],
                )
            )),
        ], className="shadow-sm border-0 mb-4", style={"borderRadius": "12px"}),

        # GeoMap + Sponsors row
        dbc.Row([
            dbc.Col(_card("GeoMap",         "chart-geomap",   380), width=6),
            dbc.Col(_card("Top 25 Sponsors","chart-sponsors",  380), width=6),
        ], className="mb-4 g-3"),

    ], style={"padding": "8px"})


# ── Callback ──────────────────────────────────────────────────────────────────

@callback(
    Output("kpi-trials",        "children"),
    Output("kpi-enrollment",    "children"),
    Output("kpi-results",       "children"),
    Output("kpi-results-sub",   "children"),
    Output("kpi-completion",    "children"),
    Output("last-update-date",  "children"),
    Output("chart-delay-donut", "figure"),
    Output("chart-sex-donut",   "figure"),
    Output("chart-status-bar",  "figure"),
    Output("trials-table",      "data"),
    Output("chart-geomap",      "figure"),
    Output("chart-sponsors",    "figure"),
    Input("apply-filters-btn",  "n_clicks"),
    State("phase-dropdown",     "value"),
    State("status-dropdown",    "value"),
    State("country-dropdown",   "value"),
    State("study-type-dropdown","value"),
    State("sponsor-input",      "value"),
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
        DELAY_COLORS = {"On Track": "#5bc0de", "Delayed": "#1f4e79"}
        total_k = f"{df_delay['count'].sum() / 1000:.2f}K"
        fig_delay = px.pie(df_delay, names="status_group", values="count", hole=0.65,
                           color="status_group", color_discrete_map=DELAY_COLORS)
        fig_delay.update_traces(textinfo="none")
        fig_delay.add_annotation(text=total_k, x=0.5, y=0.5,
                                  font=dict(size=18, color="#333"), showarrow=False)
        fig_delay.update_layout(
            margin=dict(t=10, b=30, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", y=-0.05, x=0.5, xanchor="center",
                        font=dict(size=11)),
        )
    else:
        fig_delay = _empty_fig()

    # ── Sex Distribution donut ────────────────────────────────────────
    df_sex = data["sex_dist"]
    if df_sex is not None and not df_sex.empty:
        SEX_COLORS = {"ALL": "#5bc0de", "FEMALE": "#1f4e79", "MALE": "#f0a500"}
        total_k = f"{df_sex['count'].sum() / 1000:.1f}K"
        fig_sex = px.pie(df_sex, names="sex", values="count", hole=0.65,
                         color="sex", color_discrete_map=SEX_COLORS)
        fig_sex.update_traces(textinfo="none")
        fig_sex.add_annotation(text=total_k, x=0.5, y=0.5,
                                font=dict(size=18, color="#333"), showarrow=False)
        fig_sex.update_layout(
            margin=dict(t=10, b=30, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", y=-0.05, x=0.5, xanchor="center",
                        font=dict(size=11)),
        )
    else:
        fig_sex = _empty_fig()

    # ── Status Distribution bar ───────────────────────────────────────
    df_status = data["status_dist"]
    if df_status is not None and not df_status.empty:
        labels = [f"{v/1000:.2f}K" for v in df_status["count"]]
        fig_status = px.bar(df_status, x="count", y="status", orientation="h",
                            color_discrete_sequence=["#9b9be4"])
        fig_status.update_traces(text=labels, textposition="outside",
                                  cliponaxis=False)
        fig_status.update_layout(
            yaxis={"categoryorder": "total ascending", "title": "",
                   "tickfont": {"size": 11}},
            xaxis={"title": "", "showticklabels": False},
            margin=dict(t=10, b=10, l=10, r=70),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            bargap=0.3,
        )
    else:
        fig_status = _empty_fig()

    # ── Table ─────────────────────────────────────────────────────────
    df_table = data.get("table_data")
    table_records = df_table.to_dict("records") if df_table is not None and not df_table.empty else []

    # ── GeoMap ───────────────────────────────────────────────────────
    df_geo = data.get("geo_dist")
    if df_geo is not None and not df_geo.empty:
        fig_geo = px.choropleth(
            df_geo, locations="country", locationmode="country names",
            color="count", color_continuous_scale="Blues",
            labels={"count": "Trials"},
        )
        fig_geo.update_layout(
            margin=dict(t=0, b=0, l=0, r=0),
            paper_bgcolor="rgba(0,0,0,0)",
            geo=dict(bgcolor="rgba(0,0,0,0)", showframe=False,
                     showcoastlines=True, coastlinecolor="#ccc",
                     showland=True, landcolor="#f5f5f5",
                     showocean=True, oceancolor="#eaf3fb"),
            coloraxis_showscale=False,
        )
    else:
        fig_geo = _empty_fig("No geodata")

    # ── Top 25 Sponsors ───────────────────────────────────────────────
    df_sponsors = data.get("sponsor_dist")
    if df_sponsors is not None and not df_sponsors.empty:
        labels = [f"{v/1000:.2f}K" for v in df_sponsors["count"]]
        fig_sponsors = px.bar(df_sponsors, x="count", y="sponsor", orientation="h",
                              color_discrete_sequence=["#f0a500"])
        fig_sponsors.update_traces(text=labels, textposition="outside",
                                    cliponaxis=False)
        fig_sponsors.update_layout(
            yaxis={"categoryorder": "total ascending", "title": "",
                   "tickfont": {"size": 11}},
            xaxis={"title": "", "showticklabels": False},
            margin=dict(t=10, b=10, l=10, r=70),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            bargap=0.25,
        )
    else:
        fig_sponsors = _empty_fig("No sponsor data")

    return (
        data["kpi_trials"],
        data["kpi_enrollment"],
        data["kpi_results"],
        data["kpi_results_sub"],
        data["kpi_completion"],
        data["last_update"],
        fig_delay,
        fig_sex,
        fig_status,
        table_records,
        fig_geo,
        fig_sponsors,
    )
