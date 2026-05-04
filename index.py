from dash import dcc, html, Input, Output
import dash_bootstrap_components as dbc
from app import app
from tabs import overview

# Shared Sidebar Filters
sidebar = dbc.Col([
    html.H4("Medical Filters"),
    html.Hr(),
    html.P("Select Trial Phases:"),
    dcc.Dropdown(
        id='phase-dropdown',
        options=['Phase 1', 'Phase 2', 'Phase 3', 'Phase 4'],
        value=['Phase 3'],
        multi=True
    ),
    html.Br(),
    dbc.Button("Apply Filters", id="apply-filters-btn", color="primary", class_name="w-100"),
], width=2, style={"background-color": "#f8f9fa", "padding": "2rem"})

# Content area
content = dbc.Col([
    dcc.Tabs(id='main-tabs', value='tab-overview', children=[
        dcc.Tab(label='Overview', value='tab-overview'),
        dcc.Tab(label='Conditions', value='tab-conditions'),
    ]),
    html.Div(id='tab-display', style={"padding": "2rem"})
], width=10)

app.layout = dbc.Container([
    dbc.Row([sidebar, content])
], fluid=True)

@app.callback(Output('tab-display', 'children'), Input('main-tabs', 'value'))
def display_tab(tab_name):
    if tab_name == 'tab-overview':
        return overview.render_layout()
    return html.Div("Tab content coming soon...")

if __name__ == '__main__':
    app.run(debug=True, port=8050)