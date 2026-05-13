import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import dash
from dash import dcc, html, Input, Output, dash_table
import warnings
warnings.filterwarnings('ignore')

# ── Data ──────────────────────────────────────────────────────────────────────
df  = pd.read_csv('data/online_retail_clean.csv', parse_dates=['invoicedate'])
rfm = pd.read_csv('data/rfm_segments.csv')

df['year_month'] = df['invoicedate'].dt.to_period('M').astype(str)
df['day_of_week'] = df['invoicedate'].dt.day_name()
df['hour']        = df['invoicedate'].dt.hour

# KPIs
total_revenue    = df['revenue'].sum()
total_customers  = df['customer_id'].nunique()
total_orders     = df['invoice'].nunique()
avg_order_value  = total_revenue / total_orders
champion_revenue = rfm[rfm['segment'] == 'Champions']['monetary'].sum()
champion_pct     = champion_revenue / rfm['monetary'].sum() * 100

# Segment colors
SEGMENT_COLORS = {
    'Champions'          : '#0C447C',
    'Loyal Customers'    : '#378ADD',
    'New Customers'      : '#1D9E75',
    'Potential Loyalists': '#5DCAA5',
    'Need Attention'     : '#EF9F27',
    'At Risk'            : '#D85A30',
    'Cannot Lose Them'   : '#993C1D',
    'Lost'               : '#888780',
    'Hibernating'        : '#B4B2A9',
}

# ── App ───────────────────────────────────────────────────────────────────────
app = dash.Dash(__name__, title='E-Commerce Sales Dashboard')

# ── Helper components ─────────────────────────────────────────────────────────
def kpi_card(title, value, color):
    return html.Div([
        html.P(title, style={'margin': '0 0 4px', 'fontSize': '11px',
                             'color': '#888780', 'textTransform': 'uppercase',
                             'letterSpacing': '0.06em'}),
        html.H2(value, style={'margin': 0, 'fontSize': '22px',
                              'color': color, 'fontWeight': '600'})
    ], style={
        'background': 'white',
        'borderRadius': '10px',
        'padding': '16px 20px',
        'boxShadow': '0 1px 3px rgba(0,0,0,0.07)',
        'borderTop': f'3px solid {color}'
    })

def card_style():
    return {
        'background': 'white',
        'borderRadius': '10px',
        'padding': '20px',
        'boxShadow': '0 1px 3px rgba(0,0,0,0.07)'
    }

def chart_title_style():
    return {'margin': '0 0 12px', 'fontSize': '15px',
            'color': '#2C2C2A', 'fontWeight': '500'}


# ── Layout ────────────────────────────────────────────────────────────────────
app.layout = html.Div(style={
    'fontFamily': 'Segoe UI, Arial, sans-serif',
    'backgroundColor': '#f8f9fa',
    'minHeight': '100vh',
    'padding': '24px'
}, children=[

    # Header
    html.Div([
        html.H1('E-Commerce Sales Analysis',
                style={'margin': 0, 'color': '#0C447C', 'fontSize': '26px'}),
        html.P('UCI Online Retail II · 2009–2011 · 500k+ transactions',
               style={'margin': '4px 0 0', 'color': '#888780', 'fontSize': '13px'})
    ], style={'marginBottom': '24px'}),

    # KPI Cards
    html.Div([
        kpi_card('Total Revenue',    f'£{total_revenue:,.0f}',    '#0C447C'),
        kpi_card('Total Customers',  f'{total_customers:,}',      '#1D9E75'),
        kpi_card('Total Orders',     f'{total_orders:,}',         '#378ADD'),
        kpi_card('Avg Order Value',  f'£{avg_order_value:,.2f}',  '#EF9F27'),
        kpi_card('Champion Revenue', f'£{champion_revenue:,.0f} ({champion_pct:.1f}%)', '#993C1D'),
    ], style={
        'display': 'grid',
        'gridTemplateColumns': 'repeat(5, 1fr)',
        'gap': '16px',
        'marginBottom': '24px'
    }),

    # Row 1 — Monthly revenue + segment treemap
    html.Div([
        html.Div([
            html.H3('Monthly Revenue Trend', style=chart_title_style()),
            dcc.Graph(id='monthly-revenue', config={'displayModeBar': False})
        ], style=card_style()),

        html.Div([
            html.H3('Customer Segments', style=chart_title_style()),
            dcc.Graph(id='segment-treemap', config={'displayModeBar': False})
        ], style=card_style()),
    ], style={'display': 'grid', 'gridTemplateColumns': '1.6fr 1fr',
              'gap': '16px', 'marginBottom': '16px'}),

    # Row 2 — Pareto curve + RFM heatmap
    html.Div([
        html.Div([
            html.H3('80/20 Pareto Curve', style=chart_title_style()),
            dcc.Graph(id='pareto-curve', config={'displayModeBar': False})
        ], style=card_style()),

        html.Div([
            html.H3('Revenue Heatmap — Day × Hour', style=chart_title_style()),
            dcc.Graph(id='dow-heatmap', config={'displayModeBar': False})
        ], style=card_style()),
    ], style={'display': 'grid', 'gridTemplateColumns': '1fr 1fr',
              'gap': '16px', 'marginBottom': '16px'}),

    # Row 3 — Segment deep-dive (interactive)
    html.Div([
        html.H3('Segment Deep-Dive', style=chart_title_style()),
        html.P('Select a segment to see its customers',
               style={'color': '#888780', 'fontSize': '12px', 'margin': '0 0 12px'}),
        dcc.Dropdown(
            id='segment-dropdown',
            options=[{'label': s, 'value': s}
                     for s in sorted(rfm['segment'].unique())],
            value='Champions',
            clearable=False,
            style={'width': '280px', 'marginBottom': '16px'}
        ),
        html.Div(id='segment-stats',
                 style={'display': 'grid',
                        'gridTemplateColumns': 'repeat(6, 1fr)',
                        'gap': '12px',
                        'marginBottom': '16px'}),
        dcc.Graph(id='segment-scatter', config={'displayModeBar': False})
    ], style={**card_style(), 'marginBottom': '16px'}),

    # Row 4 — Top products table
    html.Div([
        html.H3('Top 20 Products by Revenue', style=chart_title_style()),
        html.Div(id='products-table')
    ], style=card_style()),

    # Footer
    html.P('Built by Nelson Benítez · Data: UCI Online Retail II · Tools: Python, Pandas, Plotly Dash',
           style={'textAlign': 'center', 'color': '#B4B2A9',
                  'fontSize': '12px', 'marginTop': '24px'})
])


# ── Helper components ─────────────────────────────────────────────────────────
def kpi_card(title, value, color):
    return html.Div([
        html.P(title, style={'margin': '0 0 4px', 'fontSize': '11px',
                             'color': '#888780', 'textTransform': 'uppercase',
                             'letterSpacing': '0.06em'}),
        html.H2(value, style={'margin': 0, 'fontSize': '22px',
                              'color': color, 'fontWeight': '600'})
    ], style={
        'background': 'white',
        'borderRadius': '10px',
        'padding': '16px 20px',
        'boxShadow': '0 1px 3px rgba(0,0,0,0.07)',
        'borderTop': f'3px solid {color}'
    })

def card_style():
    return {
        'background': 'white',
        'borderRadius': '10px',
        'padding': '20px',
        'boxShadow': '0 1px 3px rgba(0,0,0,0.07)'
    }

def chart_title_style():
    return {'margin': '0 0 12px', 'fontSize': '15px',
            'color': '#2C2C2A', 'fontWeight': '500'}


# ── Callbacks ─────────────────────────────────────────────────────────────────

# Monthly revenue
@app.callback(Output('monthly-revenue', 'figure'), Input('segment-dropdown', 'value'))
def update_monthly(_):
    monthly = (df.groupby('year_month')['revenue']
                 .sum().reset_index().sort_values('year_month'))
    fig = go.Figure()
    fig.add_trace(go.Bar(x=monthly['year_month'], y=monthly['revenue'],
                         marker_color='#378ADD', opacity=0.85, name='Revenue'))
    fig.update_layout(
        margin=dict(t=10, b=40, l=40, r=10), height=280,
        plot_bgcolor='white', paper_bgcolor='white',
        yaxis=dict(tickprefix='£', gridcolor='#f0f0f0'),
        xaxis=dict(tickangle=-45, gridcolor='#f0f0f0'),
        showlegend=False
    )
    return fig

# Segment treemap
@app.callback(Output('segment-treemap', 'figure'), Input('segment-dropdown', 'value'))
def update_treemap(_):
    seg = (rfm.groupby('segment')
              .agg(customers=('customer_id','count'),
                   revenue=('monetary','sum'))
              .reset_index())
    fig = px.treemap(seg, path=['segment'], values='customers',
                     color='revenue',
                     color_continuous_scale='Blues',
                     hover_data=['revenue'])
    fig.update_traces(
        texttemplate='<b>%{label}</b><br>%{value} customers',
        textfont_size=11
    )
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10),
                      height=280, coloraxis_showscale=False)
    return fig

# Pareto curve
@app.callback(Output('pareto-curve', 'figure'), Input('segment-dropdown', 'value'))
def update_pareto(_):
    rfm_sorted = rfm.sort_values('monetary', ascending=False).reset_index(drop=True)
    rfm_sorted['cum_pct_customers'] = (np.arange(1, len(rfm_sorted)+1)
                                        / len(rfm_sorted) * 100)
    rfm_sorted['cum_pct_revenue']   = (rfm_sorted['monetary'].cumsum()
                                        / rfm_sorted['monetary'].sum() * 100)

    top20_rev = rfm_sorted[rfm_sorted['cum_pct_customers'] <= 20]['monetary'].sum()
    rev_share = top20_rev / rfm_sorted['monetary'].sum() * 100

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=rfm_sorted['cum_pct_customers'],
        y=rfm_sorted['cum_pct_revenue'],
        mode='lines', line=dict(color='#378ADD', width=2.5),
        fill='tozeroy', fillcolor='rgba(55,138,221,0.1)'
    ))
    fig.add_vline(x=20, line_dash='dash', line_color='#D85A30', line_width=1.5)
    fig.add_hline(y=rev_share, line_dash='dash', line_color='#1D9E75', line_width=1.5,
                  annotation_text=f'Top 20% → {rev_share:.0f}% revenue',
                  annotation_position='right')
    fig.update_layout(
        margin=dict(t=10, b=40, l=40, r=80), height=280,
        plot_bgcolor='white', paper_bgcolor='white',
        xaxis=dict(title='% of customers', gridcolor='#f0f0f0'),
        yaxis=dict(title='Cumulative % revenue', gridcolor='#f0f0f0'),
        showlegend=False
    )
    return fig

# Day × Hour heatmap
@app.callback(Output('dow-heatmap', 'figure'), Input('segment-dropdown', 'value'))
def update_heatmap(_):
    dow_order = ['Monday','Tuesday','Wednesday','Thursday','Friday','Sunday']
    heat = (df.groupby(['day_of_week','hour'])['revenue']
              .sum().unstack(fill_value=0)
              .reindex([d for d in dow_order if d in df['day_of_week'].unique()]))
    fig = go.Figure(go.Heatmap(
        z=heat.values, x=heat.columns.astype(str),
        y=heat.index, colorscale='Blues',
        hovertemplate='%{y} %{x}:00 — £%{z:,.0f}<extra></extra>'
    ))
    fig.update_layout(
        margin=dict(t=10, b=40, l=80, r=10), height=280,
        plot_bgcolor='white', paper_bgcolor='white',
        xaxis_title='Hour of day', yaxis_title=''
    )
    return fig

# Segment deep-dive stats + scatter
@app.callback(
    Output('segment-stats', 'children'),
    Output('segment-scatter', 'figure'),
    Input('segment-dropdown', 'value')
)
def update_segment(segment):
    seg_df = rfm[rfm['segment'] == segment]
    color  = SEGMENT_COLORS.get(segment, '#378ADD')

    seg_total_revenue = seg_df['monetary'].sum()
    seg_pct_revenue   = seg_total_revenue / rfm['monetary'].sum() * 100

    stats = [
        kpi_card('Customers',       f"{len(seg_df):,} ({len(seg_df)/len(rfm)*100:.1f}%)", color),
        kpi_card('Avg Recency',     f"{seg_df['recency'].mean():.0f} days",               color),
        kpi_card('Avg Frequency',   f"{seg_df['frequency'].mean():.1f} orders",           color),
        kpi_card('Avg Spend',       f"£{seg_df['monetary'].mean():,.0f}",                 color),
        kpi_card('Segment Revenue', f"£{seg_total_revenue:,.0f}",                         color),
        kpi_card('% of Revenue',    f"{seg_pct_revenue:.1f}%",                            color),
]

    fig = px.scatter(seg_df, x='frequency', y='monetary',
                     size='recency', color_discrete_sequence=[color],
                     opacity=0.6, size_max=20,
                     labels={'frequency': 'Order frequency',
                              'monetary': 'Total spend (£)',
                              'recency': 'Days since last order'})
    fig.update_layout(
        margin=dict(t=10, b=40, l=60, r=10), height=320,
        plot_bgcolor='white', paper_bgcolor='white',
        yaxis=dict(tickprefix='£', gridcolor='#f0f0f0'),
        xaxis=dict(gridcolor='#f0f0f0')
    )
    return stats, fig

# Top products table
@app.callback(Output('products-table', 'children'), Input('segment-dropdown', 'value'))
def update_products(_):
    top = (df.groupby('description')
             .agg(revenue=('revenue','sum'),
                  orders=('invoice','nunique'),
                  units=('quantity','sum'))
             .sort_values('revenue', ascending=False)
             .head(20)
             .reset_index())
    top['revenue'] = top['revenue'].apply(lambda x: f'£{x:,.0f}')

    return dash_table.DataTable(
        data=top.to_dict('records'),
        columns=[{'name': c.title(), 'id': c} for c in top.columns],
        style_header={'backgroundColor': '#0C447C', 'color': 'white',
                      'fontWeight': '500', 'fontSize': '12px'},
        style_cell={'fontSize': '12px', 'padding': '8px 12px',
                    'textAlign': 'left', 'border': '1px solid #f0f0f0'},
        style_data_conditional=[
            {'if': {'row_index': 'odd'}, 'backgroundColor': '#f8f9fa'}
        ],
        page_size=10
    )


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True)