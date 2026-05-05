from dash import dcc, html, callback, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from data_engine import engine


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_label(v):
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


def _kpi_card(title, value_id, icon_cls, gradient):
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
                ], style={"flex": "1", "minWidth": "0"}),
                icon,
            ], style={"display": "flex", "alignItems": "flex-start",
                      "justifyContent": "space-between", "gap": "10px"})
        )
    ], className="border-0 h-100",
       style={"borderRadius": "12px", "border": "none",
              "boxShadow": "0 2px 10px rgba(0,0,0,0.07)"})


def _label(text):
    return html.P(text, className="mb-1 fw-semibold",
                  style={"fontSize": "0.75rem", "textTransform": "uppercase",
                         "letterSpacing": "0.5px", "color": "#888"})


# Intervention type color palette (consistent across treemap/stacked bar)
_INT_PALETTE = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
    "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac", "#499894",
]

opts = engine.filter_options


# ── Layout ────────────────────────────────────────────────────────────────────

def render_layout():
    return html.Div([

        # Header
        dbc.Card([
            dbc.CardBody(html.Div([
                html.H4("Clinical Trials Insights",
                        className="mb-0 fw-bold d-inline me-2",
                        style={"fontSize": "1.3rem"}),
                html.Span("|", className="text-muted me-2"),
                html.Span("Interventions", className="fw-bold fst-italic",
                          style={"color": "#2c6fad", "fontSize": "0.9rem"}),
            ], className="d-flex align-items-center"), className="py-3")
        ], className="border-0 mb-3",
           style={"borderRadius": "12px", "border": "none",
                  "boxShadow": "0 2px 10px rgba(0,0,0,0.07)"}),

        # Internal filters
        dbc.Card([
            dbc.CardBody(
                dbc.Row([
                    dbc.Col([
                        _label("System"),
                        dcc.Dropdown(
                            id="int-sem1-dropdown",
                            options=[{"label": v, "value": v}
                                     for v in opts.get("int_sem_level_1", [])],
                            value=None, multi=True, placeholder="All",
                            style={"fontSize": "13px"},
                        ),
                    ], width=3),
                    dbc.Col([
                        _label("Category"),
                        dcc.Dropdown(
                            id="int-sem2-dropdown",
                            options=[{"label": v, "value": v}
                                     for v in opts.get("int_sem_level_2", [])],
                            value=None, multi=True, placeholder="All",
                            style={"fontSize": "13px"},
                        ),
                    ], width=3),
                    dbc.Col([
                        _label("Subcategory"),
                        dcc.Dropdown(
                            id="int-sem3-dropdown",
                            options=[{"label": v, "value": v}
                                     for v in opts.get("int_sem_level_3", [])],
                            value=None, multi=True, placeholder="All",
                            style={"fontSize": "13px"},
                        ),
                    ], width=3),
                    dbc.Col([
                        _label("Intervention Name"),
                        dbc.Input(
                            id="int-name-input",
                            type="text", placeholder="Search…", size="sm",
                            style={"fontSize": "13px", "borderColor": "#ddd"},
                        ),
                    ], width=2),
                    dbc.Col([
                        html.Div(style={"height": "21px"}),
                        dbc.Button("Apply", id="int-apply-btn",
                                   color="primary", size="sm", className="w-100",
                                   style={"borderRadius": "8px", "fontWeight": "600",
                                          "letterSpacing": "0.3px"}),
                    ], width=1),
                ], className="g-3 align-items-end"),
                className="py-2 px-3",
            ),
        ], className="border-0 mb-3",
           style={"borderRadius": "12px", "border": "none",
                  "boxShadow": "0 2px 10px rgba(0,0,0,0.07)"}),

        # KPI row
        dbc.Row([
            dbc.Col(_kpi_card("Total Trials",         "int-kpi-trials",
                              "bi-activity",         "linear-gradient(135deg,#667eea,#764ba2)"), width=3),
            dbc.Col(_kpi_card("Total Enrollment",     "int-kpi-enrollment",
                              "bi-person-fill",      "linear-gradient(135deg,#11998e,#38ef7d)"), width=3),
            dbc.Col(_kpi_card("Unique Interventions", "int-kpi-unique-int",
                              "bi-capsule",          "linear-gradient(135deg,#f093fb,#f5576c)"), width=3),
            dbc.Col(_kpi_card("Unique Conditions",    "int-kpi-unique-cond",
                              "bi-heart-pulse-fill", "linear-gradient(135deg,#f6d365,#fda085)"), width=3),
        ], className="mb-4 g-3", style={"paddingTop": "4px"}),

        # Treemap + Dynamics
        dbc.Row([
            dbc.Col(_chart_card("Intervention Types",
                                "int-chart-treemap", 350), width=5),
            dbc.Col(_chart_card("Dynamics of Trials by Intervention Type",
                                "int-chart-dynamics", 350), width=7),
        ], className="mb-4 g-3"),

        # Top 25 Interventions + Top 25 Conditions
        dbc.Row([
            dbc.Col(_chart_card("Top 25 Interventions",
                                "int-chart-top-interventions", 480), width=6),
            dbc.Col(_chart_card("Top 25 Conditions",
                                "int-chart-top-conditions",    480), width=6),
        ], className="mb-4 g-3"),

        # Word Cloud + GeoMap
        dbc.Row([
            dbc.Col(_chart_card("Intervention Name — Word Cloud",
                                "int-chart-wordcloud", 380), width=5),
            dbc.Col(_chart_card("Geographic Distribution",
                                "int-chart-geomap",    380), width=7),
        ], className="mb-4 g-3"),

        # Data Table
        dbc.Card([
            dbc.CardHeader("Full Data Table",
                           className="bg-white fw-semibold border-0 pt-3 pb-0",
                           style={"fontSize": "0.95rem", "color": "#333"}),
            dbc.CardBody(dcc.Loading(
                dash_table.DataTable(
                    id="int-table",
                    columns=[
                        {"name": "ID",                "id": "nctid",     "presentation": "markdown"},
                        {"name": "Year",              "id": "year"},
                        {"name": "Title",             "id": "title"},
                        {"name": "Status",            "id": "status"},
                        {"name": "Phase",             "id": "phase"},
                        {"name": "Study Type",        "id": "study_type"},
                        {"name": "Int. Type",         "id": "int_type"},
                        {"name": "Group Label",       "id": "arm_label"},
                        {"name": "Intervention Name", "id": "int_name"},
                        {"name": "Enrollment",        "id": "enrollment"},
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
                        {"if": {"column_id": "title"},    "maxWidth": "260px"},
                        {"if": {"column_id": "int_name"}, "maxWidth": "220px"},
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
                        {"if": {"filter_query": '{status} = "COMPLETED"',
                                "column_id": "status"},
                         "color": "#27ae60", "fontWeight": "600"},
                        {"if": {"filter_query": '{status} = "RECRUITING"',
                                "column_id": "status"},
                         "color": "#2980b9", "fontWeight": "600"},
                        {"if": {"filter_query": '{status} = "TERMINATED"',
                                "column_id": "status"},
                         "color": "#c0392b", "fontWeight": "600"},
                        {"if": {"filter_query": '{status} = "WITHDRAWN"',
                                "column_id": "status"},
                         "color": "#e67e22", "fontWeight": "600"},
                        {"if": {"filter_query": '{status} = "NOT_YET_RECRUITING"',
                                "column_id": "status"},
                         "color": "#8e44ad", "fontWeight": "600"},
                        {"if": {"row_index": "odd"}, "backgroundColor": "#fafafa"},
                    ],
                ),
                color="#9b9be4",
            )),
        ], className="border-0 mb-4",
           style={"borderRadius": "12px", "border": "none",
                  "boxShadow": "0 2px 10px rgba(0,0,0,0.07)"}),

    ], style={"padding": "6px 8px"})


# ── Callback ──────────────────────────────────────────────────────────────────

@callback(
    Output("int-kpi-trials",              "children"),
    Output("int-kpi-enrollment",          "children"),
    Output("int-kpi-unique-int",          "children"),
    Output("int-kpi-unique-cond",         "children"),
    Output("int-chart-treemap",           "figure"),
    Output("int-chart-dynamics",          "figure"),
    Output("int-chart-top-interventions", "figure"),
    Output("int-chart-top-conditions",    "figure"),
    Output("int-chart-wordcloud",         "figure"),
    Output("int-chart-geomap",            "figure"),
    Output("int-table",                   "data"),
    Output("int-table",                   "tooltip_data"),
    Input("apply-filters-btn",            "n_clicks"),
    Input("int-apply-btn",                "n_clicks"),
    State("phase-dropdown",               "value"),
    State("status-dropdown",              "value"),
    State("country-dropdown",             "value"),
    State("study-type-dropdown",          "value"),
    State("sponsor-input",                "value"),
    State("int-sem1-dropdown",            "value"),
    State("int-sem2-dropdown",            "value"),
    State("int-sem3-dropdown",            "value"),
    State("int-name-input",               "value"),
)
def update_interventions(_, __, phases, statuses, countries, study_types, sponsor,
                         sem1, sem2, sem3, int_name):
    data = engine.get_interventions_data(
        phases=phases or [],
        statuses=statuses or [],
        countries=countries or [],
        study_types=study_types or [],
        sponsor=sponsor or "",
        sem_level_1=sem1 or [],
        sem_level_2=sem2 or [],
        sem_level_3=sem3 or [],
        int_name=int_name or "",
    )

    # ── Intervention Types treemap ────────────────────────────────────
    df_types = data.get("int_types")
    if df_types is not None and not df_types.empty:
        fig_treemap = px.treemap(
            df_types, path=["int_type"], values="count",
            color="count",
            color_continuous_scale=[[0, "#d6eaf8"], [1, "#1a5276"]],
        )
        fig_treemap.update_traces(
            hovertemplate="<b>%{label}</b><br>Trials: %{value:,}<extra></extra>",
            textfont_size=13,
        )
        fig_treemap.update_layout(
            margin=dict(t=10, b=10, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)",
            coloraxis_showscale=False,
        )
    else:
        fig_treemap = _empty_fig()

    # ── Dynamics stacked bar ──────────────────────────────────────────
    df_dyn = data.get("int_dynamics")
    if df_dyn is not None and not df_dyn.empty:
        fig_dyn = px.bar(
            df_dyn, x="year", y="count", color="int_type",
            barmode="stack",
            color_discrete_sequence=_INT_PALETTE,
        )
        fig_dyn.update_traces(
            hovertemplate="<b>%{x}</b> — %{fullData.name}<br>Trials: %{y:,}<extra></extra>",
        )
        fig_dyn.update_layout(
            xaxis={"title": "", "tickfont": {"size": 11}},
            yaxis={"title": "", "tickfont": {"size": 11}},
            legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center",
                        font=dict(size=10), title=""),
            margin=dict(t=10, b=10, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            bargap=0.15,
        )
    else:
        fig_dyn = _empty_fig()

    # ── Top 25 Interventions (mauve/pink) ─────────────────────────────
    df_top_int = data.get("top_interventions")
    if df_top_int is not None and not df_top_int.empty:
        df_top_int = df_top_int.copy()
        total = df_top_int["count"].sum()
        df_top_int["pct"] = (df_top_int["count"] / total * 100).round(1)
        fig_top_int = px.bar(df_top_int, x="count", y="int_name", orientation="h",
                             color_discrete_sequence=["#c17799"],
                             custom_data=["pct"])
        fig_top_int.update_traces(
            text=[_fmt_label(v) for v in df_top_int["count"]],
            textposition="outside", cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>Trials: %{x:,.0f}<br>% of total: %{customdata[0]:.1f}%<extra></extra>",
        )
        fig_top_int.update_layout(
            yaxis={"categoryorder": "total ascending", "title": "",
                   "tickfont": {"size": 10}, "ticklabelstandoff": 8},
            xaxis={"title": "", "showticklabels": False},
            margin=dict(t=10, b=10, l=10, r=55),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            bargap=0.25,
        )
    else:
        fig_top_int = _empty_fig()

    # ── Top 25 Conditions (teal) ──────────────────────────────────────
    df_top_cond = data.get("top_conditions")
    if df_top_cond is not None and not df_top_cond.empty:
        df_top_cond = df_top_cond.copy()
        total = df_top_cond["count"].sum()
        df_top_cond["pct"] = (df_top_cond["count"] / total * 100).round(1)
        fig_top_cond = px.bar(df_top_cond, x="count", y="condition", orientation="h",
                              color_discrete_sequence=["#2a9d8f"],
                              custom_data=["pct"])
        fig_top_cond.update_traces(
            text=[_fmt_label(v) for v in df_top_cond["count"]],
            textposition="outside", cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>Trials: %{x:,.0f}<br>% of total: %{customdata[0]:.1f}%<extra></extra>",
        )
        fig_top_cond.update_layout(
            yaxis={"categoryorder": "total ascending", "title": "",
                   "tickfont": {"size": 10}, "ticklabelstandoff": 8},
            xaxis={"title": "", "showticklabels": False},
            margin=dict(t=10, b=10, l=10, r=55),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            bargap=0.25,
        )
    else:
        fig_top_cond = _empty_fig()

    # ── Word Cloud (treemap of top 50 names, pink scale) ──────────────
    df_wc = data.get("wordcloud")
    if df_wc is not None and not df_wc.empty:
        fig_wc = px.treemap(
            df_wc, path=["int_name"], values="count",
            color="count",
            color_continuous_scale=[[0, "#fce4ec"], [1, "#ad1457"]],
        )
        fig_wc.update_traces(
            hovertemplate="<b>%{label}</b><br>Count: %{value:,}<extra></extra>",
            textfont_size=11,
        )
        fig_wc.update_layout(
            margin=dict(t=10, b=10, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)",
            coloraxis_showscale=False,
        )
    else:
        fig_wc = _empty_fig()

    # ── GeoMap ────────────────────────────────────────────────────────
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
                bgcolor="white", showframe=False, showcoastlines=False,
                showland=True, landcolor="#f0f0f0",
                showocean=True, oceancolor="white",
                showlakes=False,
                showcountries=True, countrycolor="#e0e0e0", countrywidth=0.3,
                projection_type="natural earth",
            ),
            coloraxis_showscale=False,
        )
    else:
        fig_geo = _empty_fig("No geodata")

    # ── Table ─────────────────────────────────────────────────────────
    df_table = data.get("table_data")
    if df_table is not None and not df_table.empty:
        table_records = df_table.to_dict("records")
        tooltip_data = [
            {"title": {"value": row.get("title") or "", "type": "text"}}
            for row in table_records
        ]
    else:
        table_records, tooltip_data = [], []

    return (
        data["kpi_trials"],
        data["kpi_enrollment"],
        data["kpi_unique_int"],
        data["kpi_unique_cond"],
        fig_treemap,
        fig_dyn,
        fig_top_int,
        fig_top_cond,
        fig_wc,
        fig_geo,
        table_records,
        tooltip_data,
    )
