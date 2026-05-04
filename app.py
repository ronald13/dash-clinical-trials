import dash
import dash_bootstrap_components as dbc

app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.FLATLY,
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css",
    ],
    suppress_callback_exceptions=True,
)
server = app.server
