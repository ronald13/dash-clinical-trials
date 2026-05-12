from dash import dcc, html, callback, Input, Output, State, dash_table, ctx
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from data_engine import engine
from cache import cache


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


# Stable color map for MeSH level-1 disease categories
_COND_COLORS = {
    "Neoplasms":                                                         "#e15759",
    "Nervous System Diseases":                                           "#4e79a7",
    "Infections":                                                        "#f28e2b",
    "Cardiovascular Diseases":                                           "#76b7b2",
    "Mental Disorders":                                                  "#59a14f",
    "Musculoskeletal Diseases":                                          "#edc948",
    "Nutritional and Metabolic Diseases":                                "#b07aa1",
    "Respiratory Tract Diseases":                                        "#ff9da7",
    "Eye Diseases":                                                      "#9c755f",
    "Digestive System Diseases":                                         "#bab0ac",
    "Urogenital Diseases":                                               "#499894",
    "Skin and Connective Tissue Diseases":                               "#f1ce63",
    "Hemic and Lymphatic Diseases":                                      "#d37295",
    "Pathological Conditions, Signs and Symptoms":                       "#a0cbe8",
    "Congenital, Hereditary, and Neonatal Diseases and Abnormalities":   "#86bcb6",
    "Chemically-Induced Disorders":                                      "#8cd17d",
    "Stomatognathic Diseases":                                           "#b6992d",
    "Endocrine System Diseases":                                         "#f89a89",
    "Immune System Diseases":                                            "#79706e",
    "Unclassified":                                                      "#d3d3d3",
}
_COND_FALLBACK = ["#6ca6cd", "#ffd700", "#90ee90", "#dda0dd", "#87ceeb", "#f4a460"]


def _cond_color(cat):
    return _COND_COLORS.get(cat, _COND_FALLBACK[hash(cat) % len(_COND_FALLBACK)])


opts = engine.filter_options


# ── Caching ───────────────────────────────────────────────────────────────────

@cache.memoize(timeout=300)
def _fetch_conditions(phases_t, statuses_t, countries_t, study_types_t, sponsor,
                      int_type_t, cond_name, level1_filter):
    return engine.get_conditions_data(
        phases=list(phases_t), statuses=list(statuses_t),
        countries=list(countries_t), study_types=list(study_types_t),
        sponsor=sponsor,
        int_type=list(int_type_t),
        cond_name=cond_name, level1_filter=level1_filter,
    )


def _cache_key(phases, statuses, countries, study_types, sponsor,
               int_type, cond_name, level1_filter):
    return (
        tuple(sorted(phases or [])),
        tuple(sorted(statuses or [])),
        tuple(sorted(countries or [])),
        tuple(sorted(study_types or [])),
        sponsor or "",
        tuple(sorted(int_type or [])),
        cond_name or "",
        level1_filter or "",
    )


# ── Layout ────────────────────────────────────────────────────────────────────

def render_layout():
    return html.Div([

        # Cross-filter state store
        dcc.Store(id="cond-level1-filter", data=None),

        # Header
        dbc.Card([
            dbc.CardBody(html.Div([
                html.H4("Clinical Trials Insights",
                        className="mb-0 fw-bold d-inline me-2",
                        style={"fontSize": "1.3rem"}),
                html.Span("|", className="text-muted me-2"),
                html.Span("Conditions", className="fw-bold fst-italic",
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
                        _label("Intervention Type"),
                        dcc.Dropdown(
                            id="cond-int-type-dropdown",
                            options=[{"label": v, "value": v}
                                     for v in opts.get("int_types", [])],
                            value=None, multi=False, placeholder="All",
                            style={"fontSize": "13px"},
                        ),
                    ], width=4),
                    dbc.Col([
                        _label("Condition Name"),
                        dbc.Input(
                            id="cond-name-input",
                            type="text", placeholder="Search…", size="sm",
                            style={"fontSize": "13px", "borderColor": "#ddd"},
                        ),
                    ], width=5),
                    dbc.Col([
                        html.Div(style={"height": "21px"}),
                        dbc.Button("Apply", id="cond-apply-btn",
                                   color="primary", size="sm", className="w-100",
                                   style={"borderRadius": "8px", "fontWeight": "600",
                                          "letterSpacing": "0.3px"}),
                    ], width=3),
                ], className="g-3 align-items-end"),
                className="py-2 px-3",
            ),
        ], className="border-0 mb-3",
           style={"borderRadius": "12px", "border": "none",
                  "boxShadow": "0 2px 10px rgba(0,0,0,0.07)"}),

        # KPI row
        dbc.Row([
            dbc.Col(_kpi_card("Total Trials",         "cond-kpi-trials",
                              "bi-activity",          "linear-gradient(135deg,#667eea,#764ba2)"), width=3),
            dbc.Col(_kpi_card("Total Enrollment",     "cond-kpi-enrollment",
                              "bi-person-fill",       "linear-gradient(135deg,#11998e,#38ef7d)"), width=3),
            dbc.Col(_kpi_card("Unique Conditions",    "cond-kpi-unique-cond",
                              "bi-heart-pulse-fill",  "linear-gradient(135deg,#f093fb,#f5576c)"), width=3),
            dbc.Col(_kpi_card("Disease Categories",   "cond-kpi-unique-cat",
                              "bi-diagram-3-fill",    "linear-gradient(135deg,#f6d365,#fda085)"), width=3),
        ], className="mb-4 g-3", style={"paddingTop": "4px"}),

        # Treemap (with cross-filter badge)
        dbc.Card([
            dbc.CardHeader(
                html.Div([
                    html.Span("Conditions Tree", className="fw-semibold",
                              style={"fontSize": "0.95rem", "color": "#333"}),
                    html.Span(
                        id="cond-level1-active-badge",
                        n_clicks=0,
                        className="badge ms-2",
                        style={"backgroundColor": "#e15759", "color": "white",
                               "fontSize": "0.75rem", "cursor": "pointer",
                               "display": "none"},
                    ),
                    html.Small(
                        "  Click a category to cross-filter all charts",
                        className="text-muted ms-3",
                        style={"fontSize": "0.75rem"},
                    ),
                ], className="d-flex align-items-center"),
                className="bg-white border-0 pt-3 pb-0",
            ),
            dbc.CardBody(dcc.Loading(
                dcc.Graph(id="cond-chart-tree", style={"height": "380px"},
                          config={"displayModeBar": False}),
                color="#9b9be4",
            )),
        ], className="border-0 mb-4",
           style={"borderRadius": "12px", "border": "none",
                  "boxShadow": "0 2px 10px rgba(0,0,0,0.07)"}),

        # Phase distribution (full width)
        dbc.Row([
            dbc.Col(_chart_card(
                "Annual Distribution of Clinical Trials by Phase",
                "cond-chart-phase", 360,
            ), width=12),
        ], className="mb-4 g-3"),

        # Heatmap + Top 25 conditions
        dbc.Row([
            dbc.Col(_chart_card("Trial Density Heatmap",
                                "cond-chart-heatmap",    400), width=6),
            dbc.Col(_chart_card("Top 25 Most Studied Conditions",
                                "cond-chart-top-cond",   400), width=6),
        ], className="mb-4 g-3"),

        # Trend lines + Geo
        dbc.Row([
            dbc.Col(_chart_card("Research Trends by Disease Category",
                                "cond-chart-trend",  380), width=7),
            dbc.Col(_chart_card("Geographic Distribution",
                                "cond-chart-geo",    380), width=5),
        ], className="mb-4 g-3"),

        # Data Table
        dcc.Store(id="cond-table-store"),
        dbc.Card([
            dbc.CardHeader(
                html.Div([
                    html.Span("Detailed Trial Records", className="fw-semibold",
                              style={"fontSize": "0.95rem", "color": "#333"}),
                    dbc.Button(
                        [html.I(className="bi bi-download me-1"), "CSV"],
                        id="cond-export-btn", size="sm",
                        color="outline-secondary", className="ms-auto",
                        style={"fontSize": "0.75rem", "padding": "2px 10px"},
                    ),
                    dcc.Download(id="cond-download"),
                ], className="d-flex align-items-center"),
                className="bg-white border-0 pt-3 pb-0",
            ),
            dbc.CardBody(dcc.Loading(
                dash_table.DataTable(
                    id="cond-table",
                    columns=[
                        {"name": "ID",                     "id": "nctid",           "presentation": "markdown"},
                        {"name": "Year",                   "id": "year"},
                        {"name": "Status",                 "id": "status"},
                        {"name": "Phase",                  "id": "phase"},
                        {"name": "Condition Name",         "id": "condition_name"},
                        {"name": "Condition ID",           "id": "condition_id"},
                        {"name": "Intervention Name",      "id": "int_name"},
                        {"name": "Intervention Description","id": "int_description"},
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
                    style_cell_conditional=[
                        {"if": {"column_id": "condition_name"}, "maxWidth": "260px"},
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
                        {"if": {"filter_query": '{status} = "COMPLETED"',  "column_id": "status"},
                         "color": "#27ae60", "fontWeight": "600"},
                        {"if": {"filter_query": '{status} = "RECRUITING"', "column_id": "status"},
                         "color": "#2980b9", "fontWeight": "600"},
                        {"if": {"filter_query": '{status} = "TERMINATED"', "column_id": "status"},
                         "color": "#c0392b", "fontWeight": "600"},
                        {"if": {"row_index": "odd"}, "backgroundColor": "#fafafa"},
                    ],
                ),
                color="#9b9be4",
            )),
        ], className="border-0 mb-4",
           style={"borderRadius": "12px", "border": "none",
                  "boxShadow": "0 2px 10px rgba(0,0,0,0.07)"}),

    ], style={"padding": "6px 8px"})


# ── Cross-filter callbacks ─────────────────────────────────────────────────────

@callback(
    Output("cond-level1-filter", "data"),
    Input("cond-chart-tree",          "clickData"),
    Input("cond-level1-active-badge", "n_clicks"),
    State("cond-level1-filter",       "data"),
    prevent_initial_call=True,
)
def handle_level1_filter(click_data, _badge_clicks, current_filter):
    triggered = ctx.triggered_id
    if triggered == "cond-level1-active-badge":
        return None
    if click_data is None:
        return current_filter
    clicked = click_data["points"][0].get("label") or click_data["points"][0].get("id")
    return None if clicked == current_filter else clicked


@callback(
    Output("cond-level1-active-badge", "children"),
    Output("cond-level1-active-badge", "style"),
    Input("cond-level1-filter", "data"),
)
def update_level1_badge(level1_filter):
    base_style = {"backgroundColor": "#e15759", "color": "white",
                  "fontSize": "0.75rem", "cursor": "pointer"}
    if level1_filter:
        return f"✕ {level1_filter}", {**base_style, "display": "inline-block"}
    return "", {**base_style, "display": "none"}


# ── Main data callback ─────────────────────────────────────────────────────────

@callback(
    Output("cond-kpi-trials",       "children"),
    Output("cond-kpi-enrollment",   "children"),
    Output("cond-kpi-unique-cond",  "children"),
    Output("cond-kpi-unique-cat",   "children"),
    Output("cond-chart-tree",       "figure"),
    Output("cond-chart-phase",      "figure"),
    Output("cond-chart-heatmap",    "figure"),
    Output("cond-chart-top-cond",   "figure"),
    Output("cond-chart-trend",      "figure"),
    Output("cond-chart-geo",        "figure"),
    Output("cond-table",            "data"),
    Output("cond-table-store",      "data"),
    Input("apply-filters-btn",      "n_clicks"),
    Input("cond-apply-btn",         "n_clicks"),
    Input("cond-level1-filter",     "data"),
    State("phase-dropdown",         "value"),
    State("status-dropdown",        "value"),
    State("country-dropdown",       "value"),
    State("study-type-dropdown",    "value"),
    State("sponsor-input",          "value"),
    State("cond-int-type-dropdown", "value"),
    State("cond-name-input",        "value"),
)
def update_conditions(_, __, level1_filter,
                      phases, statuses, countries, study_types, sponsor,
                      int_type, cond_name):
    data = _fetch_conditions(*_cache_key(
        phases, statuses, countries, study_types, sponsor,
        int_type, cond_name, level1_filter,
    ))

    # ── Conditions treemap ────────────────────────────────────────────────
    df_tree = data.get("cond_tree")
    if df_tree is not None and not df_tree.empty:
        cats   = df_tree["level_1"].tolist()
        values = df_tree["count"].tolist()
        colors = [
            _cond_color(c) if (level1_filter is None or c == level1_filter) else "#e8e8e8"
            for c in cats
        ]
        fig_tree = go.Figure(go.Treemap(
            labels=cats,
            parents=[""] * len(cats),
            values=values,
            marker_colors=colors,
            hovertemplate="<b>%{label}</b><br>Trials: %{value:,}<extra></extra>",
            textfont_size=13,
        ))
        fig_tree.update_layout(
            margin=dict(t=10, b=10, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)",
        )
    else:
        fig_tree = _empty_fig()

    # ── Phase distribution grouped bar ───────────────────────────────────
    df_phase = data.get("phase_dist")
    if df_phase is not None and not df_phase.empty:
        color_map = {c: _cond_color(c) for c in df_phase["level_1"].unique()}
        fig_phase = px.bar(
            df_phase, x="phase", y="count", color="level_1",
            barmode="group",
            color_discrete_map=color_map,
        )
        fig_phase.update_traces(
            hovertemplate="<b>%{x}</b> — %{fullData.name}<br>Trials: %{y:,}<extra></extra>",
        )
        fig_phase.update_layout(
            xaxis={"title": "", "tickfont": {"size": 11}},
            yaxis={"title": "Total Trials", "tickfont": {"size": 11}},
            legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center",
                        font=dict(size=10), title=""),
            margin=dict(t=10, b=10, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            bargap=0.15,
        )
    else:
        fig_phase = _empty_fig()

    # ── Heatmap: condition category × intervention type ───────────────────
    df_hm = data.get("heatmap")
    if df_hm is not None and not df_hm.empty:
        pivot = df_hm.pivot_table(
            index="level_1", columns="int_type", values="count", fill_value=0
        )
        fig_hm = go.Figure(go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale=[[0, "#f0faf0"], [0.5, "#52c778"], [1, "#1a6b3a"]],
            hovertemplate="<b>%{y}</b><br>%{x}<br>Trials: %{z:,}<extra></extra>",
            showscale=False,
        ))
        fig_hm.update_layout(
            margin=dict(t=10, b=10, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis={"tickfont": {"size": 10}, "tickangle": -40},
            yaxis={"tickfont": {"size": 10}},
        )
    else:
        fig_hm = _empty_fig()

    # ── Top 25 conditions ─────────────────────────────────────────────────
    df_top = data.get("top_conditions")
    if df_top is not None and not df_top.empty:
        df_top = df_top.copy()
        total = df_top["count"].sum()
        df_top["pct"] = (df_top["count"] / total * 100).round(1)
        fig_top = px.bar(df_top, x="count", y="condition_name", orientation="h",
                         color_discrete_sequence=["#4e79a7"],
                         custom_data=["pct"])
        fig_top.update_traces(
            text=[_fmt_label(v) for v in df_top["count"]],
            textposition="outside", cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>Trials: %{x:,.0f}<br>Share: %{customdata[0]:.1f}%<extra></extra>",
        )
        fig_top.update_layout(
            yaxis={"categoryorder": "total ascending", "title": "",
                   "tickfont": {"size": 10}, "ticklabelstandoff": 8},
            xaxis={"title": "", "showticklabels": False},
            margin=dict(t=10, b=10, l=10, r=55),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            bargap=0.25,
        )
    else:
        fig_top = _empty_fig()

    # ── Trend lines ───────────────────────────────────────────────────────
    df_trend = data.get("trend_lines")
    if df_trend is not None and not df_trend.empty:
        color_map = {c: _cond_color(c) for c in df_trend["level_1"].unique()}
        fig_trend = px.line(
            df_trend, x="year", y="count", color="level_1",
            color_discrete_map=color_map,
            markers=False,
        )
        fig_trend.update_traces(line_width=2,
                                hovertemplate="<b>%{fullData.name}</b><br>%{x}: %{y:,}<extra></extra>")
        fig_trend.update_layout(
            xaxis={"title": "", "tickfont": {"size": 11}},
            yaxis={"title": "", "tickfont": {"size": 11}},
            legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center",
                        font=dict(size=10), title=""),
            margin=dict(t=10, b=10, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        )
    else:
        fig_trend = _empty_fig()

    # ── Geo ───────────────────────────────────────────────────────────────
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

    # ── Table ─────────────────────────────────────────────────────────────
    df_table = data.get("table_data")
    if df_table is not None and not df_table.empty:
        table_records = df_table.to_dict("records")
        store_data = table_records
    else:
        table_records, store_data = [], []

    return (
        data["kpi_trials"],
        data["kpi_enrollment"],
        data["kpi_unique_cond"],
        data["kpi_unique_cat"],
        fig_tree,
        fig_phase,
        fig_hm,
        fig_top,
        fig_trend,
        fig_geo,
        table_records,
        store_data,
    )


@callback(
    Output("cond-download", "data"),
    Input("cond-export-btn", "n_clicks"),
    State("cond-table-store", "data"),
    prevent_initial_call=True,
)
def download_cond_csv(n_clicks, store_data):
    if not store_data:
        return None
    df = pd.DataFrame(store_data)
    if "nctid" in df.columns:
        df["nctid"] = df["nctid"].str.extract(r'\[([^\]]+)\]').fillna(df["nctid"])
    return dcc.send_data_frame(df.to_csv, "conditions_trials.csv", index=False)
