from dash import dcc, html, callback, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from data_engine import engine


# --- Вспомогательные функции для чистоты кода ---

def make_kpi_card(title, id_value, trend_text=None, trend_color="success"):
    """
    Создает стандартизированную карточку KPI с закруглениями и тенями.
    Использование классов Bootstrap для легкой стилизации без CSS-костылей.
    """
    return dbc.Card([
        dbc.CardBody([
            html.P(title, className="text-muted text-uppercase fw-bold mb-1", style={"fontSize": "0.85rem"}),
            html.H3(id=id_value, className="mb-2 fw-bold text-dark"),
            html.Small(trend_text, className=f"text-{trend_color} fw-semibold") if trend_text else html.Div()
        ])
    ], className="shadow-sm border-0 h-100", style={"borderRadius": "16px"})


# --- Основной Layout ---

def render_layout():
    return html.Div([
        # 1. Верхний ряд: Карточки KPI
        dbc.Row([
            dbc.Col(make_kpi_card("Total Trials", "kpi-trials", "▲ 6.1% vs last year"), width=3),
            dbc.Col(make_kpi_card("Total Enrollment", "kpi-enrollment", "Across 142 Countries", "muted"), width=3),
            dbc.Col(make_kpi_card("Has Results (%)", "kpi-results", "76,725 Records", "muted"), width=3),
            dbc.Col(make_kpi_card("Completion Rate", "kpi-completion", "▲ On Schedule", "success"), width=3),
        ], className="mb-4"),

        # 2. Средний ряд: Графики (Donut Chart и Horizontal Bar)
        dbc.Row([
            # Левая колонка для распределения (например, по Фазам или Статусам)
            dbc.Col(dbc.Card([
                dbc.CardHeader("Distribution by Phase", className="bg-white fw-bold border-0 pt-4 pb-0",
                               style={"fontSize": "1.1rem"}),
                dbc.CardBody(dcc.Loading(dcc.Graph(id='chart-donut-phase', style={"height": "320px"})))
            ], className="shadow-sm border-0 mb-4", style={"borderRadius": "16px"}), width=4),

            # Правая колонка для Географии (Топ стран)
            dbc.Col(dbc.Card([
                dbc.CardHeader("Top Recruiting Countries", className="bg-white fw-bold border-0 pt-4 pb-0",
                               style={"fontSize": "1.1rem"}),
                dbc.CardBody(dcc.Loading(dcc.Graph(id='chart-geo-bar', style={"height": "320px"})))
            ], className="shadow-sm border-0 mb-4", style={"borderRadius": "16px"}), width=8),
        ]),
    ], style={"padding": "10px"})


# --- Логика (Callbacks) ---

@callback(
    Output('kpi-trials', 'children'),
    Output('kpi-enrollment', 'children'),
    Output('kpi-results', 'children'),
    Output('kpi-completion', 'children'),
    Output('chart-donut-phase', 'figure'),
    Output('chart-geo-bar', 'figure'),
    Input('apply-filters-btn', 'n_clicks'),
    State('phase-dropdown', 'value')
)
def update_overview(n_clicks, selected_phases):
    if not selected_phases:
        selected_phases = []

        # 1 запрос к базе, возвращающий всю страницу
    data = engine.get_overview_data(selected_phases)

    print(data)

    # График статусов (Donut)
    df_status = data.get("status_dist")
    if df_status is not None and not df_status.empty:
        fig_donut = px.pie(df_status, names='status', values='count', hole=0.65,
                           color_discrete_sequence=px.colors.qualitative.Prism)
        fig_donut.update_traces(textinfo='percent', textposition='inside', showlegend=False)
        fig_donut.update_layout(margin=dict(t=20, b=20, l=20, r=20), paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0)')
    else:
        fig_donut = go.Figure().add_annotation(text="No data", showarrow=False, font={"size": 20})

    # График стран (Bar)
    df_geo = data.get("geo_dist")
    if df_geo is not None and not df_geo.empty:
        fig_geo = px.bar(df_geo.head(10), x='count', y='country', orientation='h',
                         color_discrete_sequence=['#3b82f6'])
        fig_geo.update_layout(
            yaxis={'categoryorder': 'total ascending', 'title': ''},
            xaxis={'title': 'Number of Trials'},
            margin=dict(t=20, b=20, l=20, r=20),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
    else:
        fig_geo = go.Figure().add_annotation(text="No data", showarrow=False, font={"size": 20})

    return (
        data["kpi_trials"],
        data["kpi_enrollment"],
        data["kpi_results"],
        data["kpi_completion"],
        fig_donut,
        fig_geo
    )