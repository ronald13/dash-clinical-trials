from dash import dcc, html, Input, Output
import dash_bootstrap_components as dbc
from app import app
from tabs import overview
from data_engine import engine

# Reusable label helper
def _label(text):
    return html.P(text, className="mb-1 fw-semibold",
                  style={"fontSize": "0.78rem", "textTransform": "uppercase",
                         "letterSpacing": "0.5px", "color": "#555"})


opts = engine.filter_options  # populated at startup from S3

sidebar = dbc.Col([
    html.H5("Controls", className="fw-bold mb-3", style={"fontSize": "1rem"}),
    html.Hr(className="mt-0 mb-3"),

    _label("Phase"),
    dcc.Dropdown(id="phase-dropdown",
                 options=opts.get("phases", []),
                 value=None, multi=True, placeholder="All phases",
                 className="mb-3"),

    _label("Status"),
    dcc.Dropdown(id="status-dropdown",
                 options=opts.get("statuses", []),
                 value=None, multi=True, placeholder="All statuses",
                 className="mb-3"),

    _label("Country"),
    dcc.Dropdown(id="country-dropdown",
                 options=opts.get("countries", []),
                 value=None, multi=True, placeholder="All countries",
                 className="mb-3"),

    _label("Study Type"),
    dcc.Dropdown(id="study-type-dropdown",
                 options=opts.get("study_types", []),
                 value=None, multi=True, placeholder="All types",
                 className="mb-3"),

    _label("Sponsor"),
    dbc.Input(id="sponsor-input", type="text",
              placeholder="Search sponsor…", size="sm",
              className="mb-3"),

    dbc.Button("Apply Filters", id="apply-filters-btn",
               color="primary", className="w-100 mt-1"),

], width=2, style={
    "backgroundColor": "#f8f9fa",
    "padding": "1.5rem 1rem",
    "minHeight": "100vh",
    "overflowY": "auto",
    "borderRight": "1px solid #e9ecef",
})

content = dbc.Col([
    dcc.Tabs(id="main-tabs", value="tab-overview", children=[
        dcc.Tab(label="Overview",      value="tab-overview"),
        dcc.Tab(label="Conditions",    value="tab-conditions"),
        dcc.Tab(label="Interventions", value="tab-interventions"),
        dcc.Tab(label="Outcomes",      value="tab-outcomes"),
    ], className="mb-3"),
    html.Div(id="tab-display", style={"padding": "0.5rem 1rem"}),
], width=10)

app.layout = dbc.Container([
    dbc.Row([sidebar, content])
], fluid=True)


@app.callback(Output("tab-display", "children"), Input("main-tabs", "value"))
def display_tab(tab_name):
    if tab_name == "tab-overview":
        return overview.render_layout()
    return html.Div("Tab content coming soon…",
                    className="text-muted p-4 text-center")


if __name__ == "__main__":
    app.run(debug=True, port=8050)
