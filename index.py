from dash import html
import dash_bootstrap_components as dbc
from app import app
from tabs import overview, interventions, conditions, outcomes
from data_engine import engine

from dash import dcc


def _label(text):
    return html.P(text, className="mb-1 fw-semibold",
                  style={"fontSize": "0.75rem", "textTransform": "uppercase",
                         "letterSpacing": "0.5px", "color": "#888"})


opts = engine.filter_options

_coming_soon = html.Div(
    [
        html.I(className="bi bi-tools me-2", style={"fontSize": "1.4rem", "color": "#ccc"}),
        html.Span("Tab content coming soon…", className="text-muted"),
    ],
    className="d-flex align-items-center justify-content-center p-5",
)

sidebar = dbc.Col([
    html.Div(
        html.Span("Controls", className="fw-bold",
                  style={"fontSize": "0.85rem", "textTransform": "uppercase",
                         "letterSpacing": "1px", "color": "#555"}),
        className="mb-3",
    ),
    html.Hr(className="mt-0 mb-3", style={"borderColor": "#e9ecef"}),

    _label("Phase"),
    dcc.Dropdown(id="phase-dropdown", options=opts.get("phases", []),
                 value=None, multi=True, placeholder="All",
                 className="mb-3", style={"fontSize": "13px"}),

    _label("Status"),
    dcc.Dropdown(id="status-dropdown", options=opts.get("statuses", []),
                 value=None, multi=True, placeholder="All",
                 className="mb-3", style={"fontSize": "13px"}),

    _label("Country"),
    dcc.Dropdown(id="country-dropdown", options=opts.get("countries", []),
                 value=None, multi=True, placeholder="All",
                 className="mb-3", style={"fontSize": "13px"}),

    _label("Study Type"),
    dcc.Dropdown(id="study-type-dropdown", options=opts.get("study_types", []),
                 value=None, multi=True, placeholder="All",
                 className="mb-3", style={"fontSize": "13px"}),

    _label("Sponsor"),
    dbc.Input(id="sponsor-input", type="text",
              placeholder="Search…", size="sm",
              className="mb-4",
              style={"fontSize": "13px", "borderColor": "#ddd"}),

    dbc.Button("Apply Filters", id="apply-filters-btn",
               color="primary", size="sm", className="w-100",
               style={"borderRadius": "8px", "fontWeight": "600",
                      "letterSpacing": "0.3px"}),

], width=2, style={
    "backgroundColor": "#f8f9fa",
    "padding": "1.4rem 1rem",
    "minHeight": "100vh",
    "overflowY": "auto",
    "borderRight": "1px solid #eee",
})

_tab_style        = {"fontSize": "0.88rem", "color": "#777",  "padding": "10px 18px"}
_tab_active_style = {"fontSize": "0.88rem", "color": "#2c6fad", "fontWeight": "600",
                     "padding": "10px 18px"}

# Tab contents are rendered ONCE at startup — switching tabs never re-fires callbacks.
content = dbc.Col([
    dbc.Tabs(
        id="main-tabs",
        active_tab="tab-overview",
        className="mb-0",
        style={"borderBottom": "1px solid #dee2e6"},
        children=[
            dbc.Tab(
                label="Overview", tab_id="tab-overview",
                label_style=_tab_style, active_label_style=_tab_active_style,
                children=[overview.render_layout()],
            ),
            dbc.Tab(
                label="Conditions", tab_id="tab-conditions",
                label_style=_tab_style, active_label_style=_tab_active_style,
                children=[conditions.render_layout()],
            ),
            dbc.Tab(
                label="Interventions", tab_id="tab-interventions",
                label_style=_tab_style, active_label_style=_tab_active_style,
                children=[interventions.render_layout()],
            ),
            dbc.Tab(
                label="Outcomes", tab_id="tab-outcomes",
                label_style=_tab_style, active_label_style=_tab_active_style,
                children=[outcomes.render_layout()],
            ),
        ],
    ),
], width=10)

app.layout = dbc.Container([
    dbc.Row([sidebar, content])
], fluid=True)

if __name__ == "__main__":
    app.run(debug=True, port=8050)
