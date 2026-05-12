import math
from dash import dcc, html, callback, Input, Output, State, dash_table
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


def _chart_card(header, graph_id, height=300, subtitle=None):
    header_content = html.Div([
        html.Span(header, className="fw-semibold",
                  style={"fontSize": "0.95rem", "color": "#333"}),
        *([] if subtitle is None else [
            html.Small(f"  {subtitle}", className="text-muted ms-2",
                       style={"fontSize": "0.75rem"})
        ]),
    ], className="d-flex align-items-center")
    return dbc.Card([
        dbc.CardHeader(header_content,
                       className="bg-white border-0 pt-3 pb-0"),
        dbc.CardBody(dcc.Loading(
            dcc.Graph(id=graph_id, style={"height": f"{height}px"},
                      config={"displayModeBar": False}),
            color="#9b9be4",
        )),
    ], className="shadow-sm border-0 h-100",
       style={"borderRadius": "12px", "border": "none",
              "boxShadow": "0 2px 10px rgba(0,0,0,0.07)"})


def _kpi_card(title, value_id, sub_id, icon_cls, gradient):
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
                    html.P(id=sub_id, className="text-muted mb-0 mt-1",
                           style={"fontSize": "0.72rem"}),
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


_SIG_COLORS = {
    "SIGNIFICANT":     "#27ae60",
    "NOT_SIGNIFICANT": "#95a5a6",
    "UNKNOWN":         "#bdc3c7",
}

_TYPE_COLORS = {
    "PRIMARY":   "#2c6fad",
    "SECONDARY": "#76b7b2",
    "OTHER":     "#bab0ac",
}

opts = engine.filter_options


# ── Caching ───────────────────────────────────────────────────────────────────

@cache.memoize(timeout=300)
def _fetch_outcomes(phases_t, statuses_t, countries_t, study_types_t, sponsor,
                    outcome_type_t, sponsor_class_t, primary_purpose_t, reporting_status_t):
    return engine.get_outcomes_data(
        phases=list(phases_t), statuses=list(statuses_t),
        countries=list(countries_t), study_types=list(study_types_t),
        sponsor=sponsor,
        outcome_type=list(outcome_type_t),
        sponsor_class=list(sponsor_class_t),
        primary_purpose=list(primary_purpose_t),
        reporting_status=list(reporting_status_t),
    )


def _cache_key(phases, statuses, countries, study_types, sponsor,
               outcome_type, sponsor_class, primary_purpose, reporting_status):
    return (
        tuple(sorted(phases or [])),
        tuple(sorted(statuses or [])),
        tuple(sorted(countries or [])),
        tuple(sorted(study_types or [])),
        sponsor or "",
        tuple(sorted(outcome_type or [])),
        tuple(sorted(sponsor_class or [])),
        tuple(sorted(primary_purpose or [])),
        tuple(sorted(reporting_status or [])),
    )


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
                html.Span("Outcomes", className="fw-bold fst-italic",
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
                        _label("Outcome Type"),
                        dcc.Dropdown(
                            id="out-type-dropdown",
                            options=[{"label": v, "value": v}
                                     for v in opts.get("outcome_types", [])],
                            value=None, multi=False, placeholder="All",
                            style={"fontSize": "13px"},
                        ),
                    ], width=3),
                    dbc.Col([
                        _label("Sponsor Class"),
                        dcc.Dropdown(
                            id="out-sponsor-class-dropdown",
                            options=[{"label": v, "value": v}
                                     for v in opts.get("sponsor_classes", [])],
                            value=None, multi=False, placeholder="All",
                            style={"fontSize": "13px"},
                        ),
                    ], width=3),
                    dbc.Col([
                        _label("Primary Purpose"),
                        dcc.Dropdown(
                            id="out-purpose-dropdown",
                            options=[{"label": v, "value": v}
                                     for v in opts.get("primary_purposes", [])],
                            value=None, multi=False, placeholder="All",
                            style={"fontSize": "13px"},
                        ),
                    ], width=3),
                    dbc.Col([
                        _label("Reporting Status"),
                        dcc.Dropdown(
                            id="out-report-status-dropdown",
                            options=[{"label": v, "value": v}
                                     for v in opts.get("reporting_statuses", [])],
                            value=None, multi=False, placeholder="All",
                            style={"fontSize": "13px"},
                        ),
                    ], width=2),
                    dbc.Col([
                        html.Div(style={"height": "21px"}),
                        dbc.Button("Apply", id="out-apply-btn",
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
            dbc.Col(_kpi_card("Trials with Results", "out-kpi-trials",   "out-kpi-trials-sub",
                              "bi-clipboard2-pulse-fill",
                              "linear-gradient(135deg,#667eea,#764ba2)"), width=3),
            dbc.Col(_kpi_card("Total Outcomes",       "out-kpi-total",    "out-kpi-total-sub",
                              "bi-list-check",
                              "linear-gradient(135deg,#11998e,#38ef7d)"), width=3),
            dbc.Col(_kpi_card("Significant Outcomes", "out-kpi-sig",      "out-kpi-sig-sub",
                              "bi-graph-up-arrow",
                              "linear-gradient(135deg,#f093fb,#f5576c)"), width=3),
            dbc.Col(_kpi_card("Median P-value",       "out-kpi-med-pval", "out-kpi-med-pval-sub",
                              "bi-calculator-fill",
                              "linear-gradient(135deg,#f6d365,#fda085)"), width=3),
        ], className="mb-4 g-3", style={"paddingTop": "4px"}),

        # P-value histogram + Volcano plot
        dbc.Row([
            dbc.Col(_chart_card(
                "P-value Distribution",
                "out-chart-pval-hist", 340,
                subtitle="red line = 0.05 threshold",
            ), width=6),
            dbc.Col(_chart_card(
                "Volcano Plot — Effect Size vs. Significance",
                "out-chart-volcano", 340,
                subtitle="effect_mean × −log₁₀(p-value)",
            ), width=6),
        ], className="mb-4 g-3"),

        # Reporting status by sponsor + Outcome type donut
        dbc.Row([
            dbc.Col(_chart_card(
                "Reporting Status by Sponsor Class",
                "out-chart-reporting", 320,
            ), width=7),
            dbc.Col(_chart_card(
                "Outcome Type Split",
                "out-chart-otype", 320,
            ), width=5),
        ], className="mb-4 g-3"),

        # Phase × Significance + Param type
        dbc.Row([
            dbc.Col(_chart_card(
                "Study Distribution by Phase and Significance",
                "out-chart-phase-sig", 340,
            ), width=7),
            dbc.Col(_chart_card(
                "Measurement Parameter Types",
                "out-chart-param", 340,
            ), width=5),
        ], className="mb-4 g-3"),

        # Geo full width
        dbc.Row([
            dbc.Col(_chart_card("Geographic Distribution",
                            "out-chart-geo", 300,
                            subtitle="color = % significant outcomes (p < 0.05)"), width=12),
        ], className="mb-4 g-3"),

        # Data Table
        dcc.Store(id="out-table-store"),
        dbc.Card([
            dbc.CardHeader(
                html.Div([
                    html.Span("Outcome Details", className="fw-semibold",
                              style={"fontSize": "0.95rem", "color": "#333"}),
                    dbc.Button(
                        [html.I(className="bi bi-download me-1"), "CSV"],
                        id="out-export-btn", size="sm",
                        color="outline-secondary", className="ms-auto",
                        style={"fontSize": "0.75rem", "padding": "2px 10px"},
                    ),
                    dcc.Download(id="out-download"),
                ], className="d-flex align-items-center"),
                className="bg-white border-0 pt-3 pb-0",
            ),
            dbc.CardBody(dcc.Loading(
                dash_table.DataTable(
                    id="out-table",
                    columns=[
                        {"name": "ID",               "id": "nctid",            "presentation": "markdown"},
                        {"name": "Year",             "id": "year"},
                        {"name": "Outcome Type",     "id": "outcome_type"},
                        {"name": "Title",            "id": "title"},
                        {"name": "Param Type",       "id": "param_type"},
                        {"name": "Reporting Status", "id": "reporting_status"},
                        {"name": "Phase",            "id": "phase"},
                        {"name": "P-value",          "id": "pvalue"},
                        {"name": "Effect Size",      "id": "effect_size"},
                        {"name": "Country",          "id": "country"},
                        {"name": "Sponsor",          "id": "sponsor"},
                        {"name": "Sponsor Class",    "id": "sponsor_class"},
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
                        {"if": {"column_id": "title"},   "maxWidth": "280px"},
                        {"if": {"column_id": "sponsor"}, "maxWidth": "180px"},
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
                        {"if": {"filter_query": '{outcome_type} = "PRIMARY"',
                                "column_id": "outcome_type"},
                         "color": "#2c6fad", "fontWeight": "600"},
                        {"if": {"filter_query": '{reporting_status} = "POSTED"',
                                "column_id": "reporting_status"},
                         "color": "#27ae60", "fontWeight": "600"},
                        {"if": {"row_index": "odd"}, "backgroundColor": "#fafafa"},
                    ],
                ),
                color="#9b9be4",
            )),
        ], className="border-0 mb-4",
           style={"borderRadius": "12px", "border": "none",
                  "boxShadow": "0 2px 10px rgba(0,0,0,0.07)"}),

    ], style={"padding": "6px 8px"})


# ── Main data callback ─────────────────────────────────────────────────────────

@callback(
    Output("out-kpi-trials",          "children"),
    Output("out-kpi-trials-sub",      "children"),
    Output("out-kpi-total",           "children"),
    Output("out-kpi-total-sub",       "children"),
    Output("out-kpi-sig",             "children"),
    Output("out-kpi-sig-sub",         "children"),
    Output("out-kpi-med-pval",        "children"),
    Output("out-kpi-med-pval-sub",    "children"),
    Output("out-chart-pval-hist",     "figure"),
    Output("out-chart-volcano",       "figure"),
    Output("out-chart-reporting",     "figure"),
    Output("out-chart-otype",         "figure"),
    Output("out-chart-phase-sig",     "figure"),
    Output("out-chart-param",         "figure"),
    Output("out-chart-geo",           "figure"),
    Output("out-table",               "data"),
    Output("out-table-store",         "data"),
    Input("apply-filters-btn",             "n_clicks"),
    Input("out-apply-btn",                 "n_clicks"),
    State("phase-dropdown",                "value"),
    State("status-dropdown",               "value"),
    State("country-dropdown",              "value"),
    State("study-type-dropdown",           "value"),
    State("sponsor-input",                 "value"),
    State("out-type-dropdown",             "value"),
    State("out-sponsor-class-dropdown",    "value"),
    State("out-purpose-dropdown",          "value"),
    State("out-report-status-dropdown",    "value"),
)
def update_outcomes(_, __,
                    phases, statuses, countries, study_types, sponsor,
                    outcome_type, sponsor_class, primary_purpose, reporting_status):
    data = _fetch_outcomes(*_cache_key(
        phases, statuses, countries, study_types, sponsor,
        outcome_type, sponsor_class, primary_purpose, reporting_status,
    ))

    # ── KPI values ────────────────────────────────────────────────────────
    kpi_trials_sub  = "unique trials"
    kpi_total_sub   = "outcome records"
    kpi_sig_sub     = data["kpi_sig_sub"]
    kpi_pval_sub    = "median across reported outcomes"

    # ── P-value histogram ─────────────────────────────────────────────────
    df_pval = data.get("pval_hist")
    if df_pval is not None and not df_pval.empty:
        fig_pval = go.Figure()
        fig_pval.add_trace(go.Bar(
            x=df_pval["bin"], y=df_pval["count"],
            marker_color=[
                "#e74c3c" if b < 0.05 else "#aec6e8"
                for b in df_pval["bin"]
            ],
            hovertemplate="p-value bin: %{x:.2f}–%{x:.2f}<br>Count: %{y:,}<extra></extra>",
            width=0.045,
        ))
        fig_pval.add_vline(x=0.05, line_dash="dash", line_color="#e74c3c",
                           annotation_text="p=0.05", annotation_position="top right",
                           annotation_font_size=11)
        fig_pval.update_layout(
            xaxis={"title": "P-value", "tickfont": {"size": 11},
                   "range": [-0.02, 1.02]},
            yaxis={"title": "Count", "tickfont": {"size": 11}},
            margin=dict(t=20, b=10, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            bargap=0.05,
        )
    else:
        fig_pval = _empty_fig("No p-value data available")

    # ── Volcano plot ──────────────────────────────────────────────────────
    df_vol = data.get("volcano")
    if df_vol is not None and not df_vol.empty:
        df_vol = df_vol.copy()
        df_vol["neg_log_p"] = df_vol["pvalue_mean"].apply(
            lambda p: -math.log10(p) if p and p > 0 else None
        )
        df_vol = df_vol.dropna(subset=["neg_log_p"])
        df_vol["significance"] = df_vol["pvalue_mean"].apply(
            lambda p: "SIGNIFICANT" if p < 0.05 else "NOT_SIGNIFICANT"
        )
        color_map = {"SIGNIFICANT": "#e74c3c", "NOT_SIGNIFICANT": "#aec6e8"}
        fig_vol = px.scatter(
            df_vol, x="effect_mean", y="neg_log_p",
            color="significance",
            color_discrete_map=color_map,
            hover_data={"title": True, "pvalue_mean": ":.4f",
                        "effect_mean": ":.3f", "significance": False},
            opacity=0.55,
        )
        fig_vol.add_hline(y=-math.log10(0.05), line_dash="dash", line_color="#e74c3c",
                          annotation_text="p=0.05", annotation_font_size=10)
        fig_vol.add_vline(x=0, line_color="#ccc", line_width=1)
        fig_vol.update_traces(marker_size=5)
        fig_vol.update_layout(
            xaxis={"title": "Effect Size (effect_mean)", "tickfont": {"size": 11}},
            yaxis={"title": "−log₁₀(p-value)", "tickfont": {"size": 11}},
            legend=dict(title="", orientation="h", y=-0.18, x=0.5, xanchor="center",
                        font=dict(size=10)),
            margin=dict(t=10, b=10, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        )
    else:
        fig_vol = _empty_fig("Insufficient effect size / p-value data")

    # ── Reporting status by sponsor class ─────────────────────────────────
    df_rep = data.get("reporting")
    if df_rep is not None and not df_rep.empty:
        fig_rep = px.bar(
            df_rep, x="count", y="sponsor_class", color="reporting_status",
            orientation="h", barmode="stack",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_rep.update_layout(
            xaxis={"title": "", "tickfont": {"size": 11}},
            yaxis={"title": "", "tickfont": {"size": 11}, "ticklabelstandoff": 8},
            legend=dict(title="", orientation="h", y=-0.2, x=0.5, xanchor="center",
                        font=dict(size=10)),
            margin=dict(t=10, b=10, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        )
    else:
        fig_rep = _empty_fig()

    # ── Outcome type donut ────────────────────────────────────────────────
    df_otype = data.get("outcome_types")
    if df_otype is not None and not df_otype.empty:
        color_map = {t: _TYPE_COLORS.get(t, "#bab0ac") for t in df_otype["outcome_type"]}
        fig_otype = go.Figure(go.Pie(
            labels=df_otype["outcome_type"],
            values=df_otype["count"],
            hole=0.55,
            marker_colors=[color_map[t] for t in df_otype["outcome_type"]],
            hovertemplate="<b>%{label}</b><br>Count: %{value:,}<br>Share: %{percent}<extra></extra>",
            textfont_size=12,
        ))
        fig_otype.update_layout(
            margin=dict(t=10, b=10, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center",
                        font=dict(size=11)),
            showlegend=True,
        )
    else:
        fig_otype = _empty_fig()

    # ── Phase × Significance horizontal stacked bar ───────────────────────
    df_ps = data.get("phase_sig")
    if df_ps is not None and not df_ps.empty:
        fig_ps = px.bar(
            df_ps, y="phase", x="count", color="significance",
            orientation="h", barmode="stack",
            color_discrete_map=_SIG_COLORS,
        )
        fig_ps.update_layout(
            xaxis={"title": "", "tickfont": {"size": 11}},
            yaxis={"title": "", "tickfont": {"size": 11},
                   "categoryorder": "total ascending", "ticklabelstandoff": 8},
            legend=dict(title="", orientation="h", y=-0.18, x=0.5, xanchor="center",
                        font=dict(size=10)),
            margin=dict(t=10, b=10, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        )
    else:
        fig_ps = _empty_fig()

    # ── Param type bar ────────────────────────────────────────────────────
    df_param = data.get("param_types")
    if df_param is not None and not df_param.empty:
        fig_param = px.bar(
            df_param, x="count", y="param_type", orientation="h",
            color_discrete_sequence=["#76b7b2"],
        )
        fig_param.update_traces(
            hovertemplate="<b>%{y}</b><br>Count: %{x:,}<extra></extra>",
        )
        fig_param.update_layout(
            yaxis={"categoryorder": "total ascending", "title": "",
                   "tickfont": {"size": 10}, "ticklabelstandoff": 8},
            xaxis={"title": "", "showticklabels": False},
            margin=dict(t=10, b=10, l=10, r=40),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            bargap=0.25,
        )
    else:
        fig_param = _empty_fig()

    # ── Geo: color = % significant outcomes per country ───────────────────
    df_geo = data.get("geo_dist")
    if df_geo is not None and not df_geo.empty:
        df_geo = df_geo.copy()
        # Only color countries that have actual p-value data
        df_color = df_geo[df_geo["with_pval"] > 0].copy()
        if not df_color.empty:
            fig_geo = px.choropleth(
                df_color,
                locations="country", locationmode="country names",
                color="pct_significant",
                color_continuous_scale=[[0, "#fef9c3"], [0.5, "#f59e0b"], [1, "#b91c1c"]],
                range_color=[0, 100],
                custom_data=["country", "trials", "significant", "with_pval", "pct_significant"],
            )
            fig_geo.update_traces(
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Trials: %{customdata[1]}<br>"
                    "Significant outcomes: %{customdata[2]} / %{customdata[3]}<br>"
                    "% significant: %{customdata[4]:.1f}%"
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
                coloraxis_colorbar=dict(
                    title="% Significant",
                    ticksuffix="%",
                    thickness=12,
                    len=0.6,
                ),
            )
        else:
            fig_geo = _empty_fig("No p-value data for geographic breakdown")
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
        data["kpi_trials"],     kpi_trials_sub,
        data["kpi_total"],      kpi_total_sub,
        data["kpi_sig"],        kpi_sig_sub,
        data["kpi_med_pval"],   kpi_pval_sub,
        fig_pval,
        fig_vol,
        fig_rep,
        fig_otype,
        fig_ps,
        fig_param,
        fig_geo,
        table_records,
        store_data,
    )


@callback(
    Output("out-download", "data"),
    Input("out-export-btn", "n_clicks"),
    State("out-table-store", "data"),
    prevent_initial_call=True,
)
def download_out_csv(n_clicks, store_data):
    if not store_data:
        return None
    df = pd.DataFrame(store_data)
    if "nctid" in df.columns:
        df["nctid"] = df["nctid"].str.extract(r'\[([^\]]+)\]').fillna(df["nctid"])
    return dcc.send_data_frame(df.to_csv, "outcomes_trials.csv", index=False)
