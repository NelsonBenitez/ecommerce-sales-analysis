import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import dash
from dash import dcc, html, Input, Output, State, dash_table, no_update, ctx
import warnings
warnings.filterwarnings('ignore')

# --- Data Loading & Prep ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
df  = pd.read_csv(os.path.join(BASE_DIR, 'data', 'online_retail_clean.csv'), parse_dates=['invoicedate'])
rfm = pd.read_csv(os.path.join(BASE_DIR, 'data', 'rfm_segments.csv'))

df['year']        = df['invoicedate'].dt.year
df['year_month']  = df['invoicedate'].dt.to_period('M').astype(str)
df['month_label'] = df['invoicedate'].dt.strftime('%b %Y')
df['day_of_week'] = df['invoicedate'].dt.day_name()
df['hour']        = df['invoicedate'].dt.hour
df = df.merge(rfm[['customer_id', 'segment']], on='customer_id', how='left')

YEARS        = sorted(df['year'].unique().tolist())
YEAR_OPTIONS = [{'label': 'All Years', 'value': 'all'}] + [{'label': str(y), 'value': y} for y in YEARS]

SEGMENT_COLORS = {
    'Champions': '#0C447C', 'Loyal Customers': '#378ADD',
    'New Customers': '#1D9E75', 'Potential Loyalists': '#5DCAA5',
    'Need Attention': '#EF9F27', 'At Risk': '#D85A30',
    'Cannot Lose Them': '#993C1D', 'Lost': '#888780', 'Hibernating': '#B4B2A9',
}
DOW_ORDER = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
FONT      = 'Segoe UI, Arial, sans-serif'
BG        = '#f8f9fa'
SHADOW    = '0 1px 3px rgba(0,0,0,0.07)'

app    = dash.Dash(__name__, title='E-Commerce Sales Dashboard', suppress_callback_exceptions=True)
server = app.server

# --- Reusable Components ---
def kpi_card(title, value, color, subtitle=None):
    ch = [
        html.P(title, style={'margin':'0 0 4px','fontSize':'11px','color':'#888780',
                             'textTransform':'uppercase','letterSpacing':'0.06em','fontFamily':FONT}),
        html.H2(value, style={'margin':0,'fontSize':'22px','color':color,'fontWeight':'600','fontFamily':FONT})
    ]
    if subtitle:
        ch.append(html.P(subtitle, style={'margin':'4px 0 0','fontSize':'11px','color':'#888780','fontFamily':FONT}))
    return html.Div(ch, style={'background':'white','borderRadius':'10px','padding':'16px 20px',
                                'boxShadow':SHADOW,'borderTop':f'3px solid {color}'})

def card(children, extra=None):
    s = {'background':'white','borderRadius':'10px','padding':'20px','boxShadow':SHADOW}
    if extra: s.update(extra)
    return html.Div(children, style=s)

def stitle(text):
    return html.H3(text, style={'margin':'0 0 4px','fontSize':'18px','color':'#2C2C2A','fontWeight':'500','fontFamily':FONT})

def sub(text):
    return html.P(text, style={'color':'#888780','fontSize':'14px','margin':'0 0 10px','fontStyle':'italic','fontFamily':FONT})

# --- Filter Logic ---
def filter_df(d, year, seg):
    out = d.copy()
    if year != 'all': out = out[out['year'] == int(year)]
    if seg: out = out[out['segment'] == seg]
    return out

def filter_rfm(r, year, seg, d_full):
    out = r.copy()
    if year != 'all':
        active = d_full[d_full['year'] == int(year)]['customer_id'].unique()
        out = out[out['customer_id'].isin(active)]
    if seg: out = out[out['segment'] == seg]
    return out

def get_color(seg):
    return SEGMENT_COLORS.get(seg, '#378ADD') if seg else '#378ADD'

# --- Figure Functions ---
def monthly_fig(fdf, seg=None):
    color   = get_color(seg)
    monthly = (fdf.groupby(['year_month','month_label'])['revenue']
                  .sum().reset_index().sort_values('year_month'))
    rolling = monthly['revenue'].rolling(3, min_periods=1).mean()
    tv = monthly['year_month'].tolist()[::2]
    tt = monthly.loc[monthly['year_month'].isin(tv),'month_label'].tolist()
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=monthly['year_month'], y=monthly['revenue'],
        marker_color=color, opacity=0.85, name='Revenue',
        customdata=monthly['month_label'],
        hovertemplate='<b>%{customdata}</b><br>Revenue: \u00a3%{y:,.0f}<extra></extra>'
    ))
    fig.add_trace(go.Scatter(
        x=monthly['year_month'], y=rolling, mode='lines',
        line=dict(color='#D85A30', width=2, dash='dash'), name='3-Month Rolling Avg',
        customdata=monthly['month_label'],
        hovertemplate='<b>%{customdata}</b><br>3-Month Avg: \u00a3%{y:,.0f}<extra></extra>'
    ))
    fig.update_layout(
        margin=dict(t=10,b=50,l=40,r=10), height=300,
        plot_bgcolor='white', paper_bgcolor='white',
        yaxis=dict(tickprefix='\u00a3', gridcolor='#f0f0f0', tickformat=',.0f'),
        xaxis=dict(tickmode='array', tickvals=tv, ticktext=tt, tickangle=-45, gridcolor='#f0f0f0'),
        legend=dict(orientation='h', y=1.12, x=0), hovermode='x unified'
    )
    return fig

def dow_fig(fdf, seg=None):
    color = get_color(seg)
    dow = (fdf.groupby('day_of_week')['invoice'].nunique()
              .reset_index().rename(columns={'invoice':'orders'}))
    dow['day_of_week'] = pd.Categorical(dow['day_of_week'], categories=DOW_ORDER, ordered=True)
    dow = dow.sort_values('day_of_week')
    fig = go.Figure(go.Bar(
        x=dow['day_of_week'], y=dow['orders'],
        marker_color=color, opacity=0.85,
        hovertemplate='<b>%{x}</b><br>Orders: %{y:,}<extra></extra>'
    ))
    fig.update_layout(
        margin=dict(t=10,b=40,l=40,r=10), height=280,
        plot_bgcolor='white', paper_bgcolor='white',
        xaxis=dict(gridcolor='#f0f0f0'),
        yaxis=dict(gridcolor='#f0f0f0', title='Orders'),
        showlegend=False
    )
    return fig

def freq_dist(fdf, seg=None):
    color = SEGMENT_COLORS.get(seg, '#EF9F27') if seg else '#EF9F27'
    freq  = (fdf.groupby('customer_id')['invoice'].nunique()
                .reset_index().rename(columns={'invoice':'num_orders'}))
    if len(freq) == 0:
        return go.Figure()
    labels = ['1','2','3','4','5','6-10','11-20','21-50','51+']
    upper  = max(int(freq['num_orders'].max()) + 1, 52)
    bins   = [0, 1, 2, 3, 4, 5, 10, 20, 50, upper]
    freq['bucket'] = pd.cut(freq['num_orders'], bins=bins, labels=labels, right=True)
    counts = freq['bucket'].value_counts().reindex(labels).fillna(0)
    fig = go.Figure(go.Bar(
        x=labels, y=counts.values, marker_color=color, opacity=0.85,
        hovertemplate='<b>%{x} orders</b><br>Customers: %{y:,}<extra></extra>'
    ))
    fig.update_layout(
        margin=dict(t=10,b=40,l=40,r=10), height=280,
        plot_bgcolor='white', paper_bgcolor='white',
        xaxis=dict(title='Orders per customer', gridcolor='#f0f0f0'),
        yaxis=dict(title='Customers', gridcolor='#f0f0f0'),
        showlegend=False
    )
    return fig

# --- Layout Elements ---
def navbar(active):
    pages = [('/', 'Executive Overview'), ('/rfm', 'RFM Segmentation'), ('/behavior', 'Customer Behavior')]
    links = []
    for href, label in pages:
        act = href == active
        links.append(html.A(label, href=href, style={
            'padding':'18px 65px', # Increased padding
            'fontFamily':FONT,
            'color':'white' if act else 'rgba(255,255,255,0.5)', # Muted color for inactive
            'fontWeight':'800' if act else '500', # Thicker weight for active
            'fontSize':'22px' if act else '16px', # SIGNIFICANTLY bigger active font
            'textDecoration':'none',
            'borderBottom':'5px solid white' if act else '5px solid transparent', # Thick bottom highlight
            'display':'inline-block',
            'transition': 'all 0.3s ease-in-out'
        }))
    return html.Div([
        html.Div([
            html.Span('📦 E-Commerce Sales Analytics', style={
                'color':'white','fontWeight':'900','fontSize':'26px', # Increased logo font
                'marginRight':'45px','fontFamily':FONT
            }),
            html.Div(links, style={'display':'flex','gap':'8px'})
        ], style={'display':'flex','alignItems':'center', 'padding':'0 24px', 'maxWidth':'1400px', 'margin':'0'})
    ], style={
        'backgroundColor':'#0C447C',
        'marginBottom':'30px', 
        'boxShadow':'0 4px 12px rgba(0,0,0,0.2)', 
        'padding': '0 10px'
    })

def filter_bar(page_id, show_seg=True):
    ch = [
        html.Div([
            html.Label('Filter by Year', style={
                'fontSize':'11px','color':'#888780','textTransform':'uppercase',
                'letterSpacing':'0.06em','marginBottom':'4px','display':'block','fontFamily':FONT
            }),
            dcc.Dropdown(id=f'year-{page_id}', options=YEAR_OPTIONS, value='all',
                         clearable=False, style={'width':'160px','fontSize':'13px'})
        ])
    ]
    if show_seg:
        ch.append(html.Div([
            html.Label('Filter by Segment', style={
                'fontSize':'11px','color':'#888780','textTransform':'uppercase',
                'letterSpacing':'0.06em','marginBottom':'4px','display':'block','fontFamily':FONT
            }),
            dcc.Dropdown(id=f'seg-{page_id}',
                         options=[{'label':s,'value':s} for s in sorted(rfm['segment'].unique())],
                         value=None, placeholder='All Segments', clearable=True,
                         style={'width':'220px','fontSize':'13px'})
        ]))
    ch.append(html.Div(
        html.Span(id=f'badge-{page_id}', children='Showing: All Data', style={
            'backgroundColor':'#E6F1FB','color':'#185FA5',
            'padding':'5px 12px','borderRadius':'20px',
            'fontSize':'18px','fontWeight':'500','fontFamily':FONT
        }),
        style={'alignSelf':'flex-end','paddingBottom':'2px'}
    ))
    return html.Div(ch, style={
        'display':'flex','gap':'16px','alignItems':'flex-end',
        'background':'white','borderRadius':'10px','padding':'16px 20px',
        'boxShadow':SHADOW,'marginBottom':'16px'
    })

def page_header(title, subtitle_text):
    return html.Div([
        html.H2(title, style={'margin':'0 0 4px','color':'#0C447C','fontSize':'34px','fontWeight':'800','fontFamily':FONT}),
        html.P(subtitle_text, style={'margin':'0 0 16px','color':'#888780','fontSize':'18px','fontFamily':FONT})
    ])

FOOTER = html.P('Built by Nelson Benitez · UCI Online Retail II · Plotly Dash',
                style={'textAlign':'center','color':'#B4B2A9','fontSize':'18px',
                       'padding':'12px','fontFamily':FONT})

# --- Page Builders ---
def make_ov():
    return html.Div([
        navbar('/'),
        html.Div([
            page_header('Executive Overview', 'High-level revenue, orders and product performance'),
            filter_bar('ov', show_seg=False),
            html.Div(id='ov-kpis', style={'display':'grid','gridTemplateColumns':'repeat(5,1fr)','gap':'16px','marginBottom':'16px'}),
            html.Div([
                card([stitle('Monthly Revenue Trend'),
                      sub('Bars = monthly total  ·  Dashed = 3-month rolling average (smooths spikes to show underlying trend)'),
                      dcc.Graph(id='ov-monthly', config={'displayModeBar':False})]),
                card([stitle('Orders by Day of Week'),
                      sub('Unique orders placed on each day of the week'),
                      dcc.Graph(id='ov-dow', config={'displayModeBar':False})]),
            ], style={'display':'grid','gridTemplateColumns':'1.8fr 1fr','gap':'16px','marginBottom':'16px'}),
            html.Div([
                card([stitle('Revenue by Country — Top 10'),
                      sub('Countries with more than 50 orders'),
                      dcc.Graph(id='ov-country', config={'displayModeBar':False})]),
                card([stitle('Top 20 Products by Revenue'), html.Div(id='ov-products')]),
            ], style={'display':'grid','gridTemplateColumns':'1fr 1.4fr','gap':'16px'}),
        ], style={'padding':'0 24px 24px'}),
        FOOTER
    ], style={'fontFamily':FONT,'backgroundColor':BG,'minHeight':'100vh'})

def make_rfm():
    return html.Div([
        navbar('/rfm'),
        html.Div([
            page_header('RFM Segmentation', 'Customer segmentation by Recency, Frequency and Monetary value'),
            filter_bar('rfm', show_seg=True),
            html.Div(id='rfm-kpis', style={'display':'grid','gridTemplateColumns':'repeat(7,1fr)','gap':'16px','marginBottom':'16px'}),
            html.Div([
                card([stitle('Monthly Revenue by Segment'),
                      sub('Bar color reflects selected segment  ·  Use filters above to compare'),
                      dcc.Graph(id='rfm-monthly', config={'displayModeBar':False})]),
                card([stitle('Customer Segments — Size & Revenue Share'),
                      sub('Click a segment to filter all charts  ·  Size = customers  ·  Color = % of revenue'),
                      dcc.Graph(id='rfm-treemap', config={'displayModeBar':False}, style={'cursor':'pointer'})]),
            ], style={'display':'grid','gridTemplateColumns':'1.6fr 1fr','gap':'16px','marginBottom':'16px'}),
            html.Div([
                card([stitle('80/20 Pareto Curve'),
                      sub('What % of revenue comes from the top X% of customers'),
                      dcc.Graph(id='rfm-pareto', config={'displayModeBar':False})]),
                card([stitle('Frequency vs Total Spend'),
                      sub('Each dot = one customer  ·  X = orders  ·  Y = total £ spent  ·  Color = recency (darker = more recent)'),
                      dcc.Graph(id='rfm-scatter', config={'displayModeBar':False})]),
            ], style={'display':'grid','gridTemplateColumns':'1fr 1fr','gap':'16px'}),
        ], style={'padding':'0 24px 24px'}),
        FOOTER
    ], style={'fontFamily':FONT,'backgroundColor':BG,'minHeight':'100vh'})

def make_beh():
    return html.Div([
        navbar('/behavior'),
        html.Div([
            page_header('Customer Behavior', 'When customers shop, how often and purchasing patterns'),
            filter_bar('beh', show_seg=True),
            html.Div([
                card([stitle('Orders by Day of Week'), sub('Which days generate the most order volume'),
                      dcc.Graph(id='beh-dow', config={'displayModeBar':False})]),
                card([stitle('Orders by Hour of Day'), sub('Peak shopping hours across all days'),
                      dcc.Graph(id='beh-hour', config={'displayModeBar':False})]),
            ], style={'display':'grid','gridTemplateColumns':'1fr 1fr','gap':'16px','marginBottom':'16px'}),
            card([stitle('Revenue Heatmap — Day × Hour'),
                  sub('Darker = higher revenue  ·  Best time windows for promotions and email campaigns'),
                  dcc.Graph(id='beh-heatmap', config={'displayModeBar':False})], {'marginBottom':'16px'}),
            html.Div([
                card([stitle('New vs Returning Customers per Month'),
                      sub('New = first purchase that month  ·  Returning = had purchased before'),
                      dcc.Graph(id='beh-new-ret', config={'displayModeBar':False})]),
                card([stitle('Purchase Frequency Distribution'),
                      sub('How many orders each customer placed — shows one-time vs loyal buyers'),
                      dcc.Graph(id='beh-freq', config={'displayModeBar':False})]),
            ], style={'display':'grid','gridTemplateColumns':'1fr 1fr','gap':'16px'}),
        ], style={'padding':'0 24px 24px'}),
        FOOTER
    ], style={'fontFamily':FONT,'backgroundColor':BG,'minHeight':'100vh'})

# --- Main App Layout ---
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content')
], style={'fontFamily':FONT,'backgroundColor':BG})

@app.callback(Output('page-content','children'), Input('url','pathname'))
def route(path):
    if path == '/rfm': return make_rfm()
    if path == '/behavior': return make_beh()
    return make_ov()

# --- OV Callbacks ---
@app.callback(Output('badge-ov','children'), Input('year-ov','value'))
def badge_ov(y): return f'Showing: {"All Years" if y=="all" else y}'

@app.callback(Output('ov-kpis','children'), Input('year-ov','value'))
def ov_kpis(y):
    fdf = filter_df(df, y, None)
    rev=fdf['revenue'].sum(); c=fdf['customer_id'].nunique()
    o=fdf['invoice'].nunique(); aov=rev/o if o>0 else 0; u=fdf['quantity'].sum()
    return [kpi_card('Total Revenue',f'\u00a3{rev:,.0f}','#0C447C'),
            kpi_card('Total Customers',f'{c:,}','#1D9E75'),
            kpi_card('Total Orders',f'{o:,}','#378ADD'),
            kpi_card('Avg Order Value',f'\u00a3{aov:,.2f}','#EF9F27'),
            kpi_card('Units Sold',f'{u:,}','#993C1D')]

@app.callback(Output('ov-monthly','figure'), Input('year-ov','value'))
def ov_monthly(y): return monthly_fig(filter_df(df,y,None))

@app.callback(Output('ov-dow','figure'), Input('year-ov','value'))
def ov_dow(y): return dow_fig(filter_df(df,y,None))

@app.callback(Output('ov-country','figure'), Input('year-ov','value'))
def ov_country(y):
    fdf = filter_df(df,y,None)
    c = fdf.groupby('country')['revenue'].sum().reset_index().sort_values('revenue',ascending=False).head(10)
    fig = go.Figure(go.Bar(x=c['revenue'],y=c['country'],orientation='h',
                           marker_color='#378ADD',opacity=0.85,
                           hovertemplate='<b>%{y}</b><br>Revenue: \u00a3%{x:,.0f}<extra></extra>'))
    fig.update_layout(margin=dict(t=10,b=40,l=120,r=10),height=300,
                      plot_bgcolor='white',paper_bgcolor='white',
                      xaxis=dict(tickprefix='\u00a3',gridcolor='#f0f0f0',tickformat=',.0f'),
                      yaxis=dict(autorange='reversed',gridcolor='#f0f0f0'),showlegend=False)
    return fig

@app.callback(Output('ov-products','children'), Input('year-ov','value'))
def ov_products(y):
    fdf = filter_df(df,y,None)
    top = (fdf.groupby('description').agg(revenue=('revenue','sum'),
           orders=('invoice','nunique'),units=('quantity','sum'))
           .sort_values('revenue',ascending=False).head(20).reset_index())
    top['revenue'] = top['revenue'].apply(lambda x: f'\u00a3{x:,.0f}')
    return dash_table.DataTable(data=top.to_dict('records'),
        columns=[{'name':c.title(),'id':c} for c in top.columns],
        style_header={'backgroundColor':'#0C447C','color':'white','fontWeight':'500','fontSize':'12px'},
        style_cell={'fontSize':'12px','padding':'6px 10px','textAlign':'left',
                    'border':'1px solid #f0f0f0','fontFamily':FONT},
        style_data_conditional=[{'if':{'row_index':'odd'},'backgroundColor':'#f8f9fa'}],
        page_size=8)

# --- RFM Callbacks ---

@app.callback(
    Output('seg-rfm', 'value'),
    Input('rfm-treemap', 'clickData'),
    State('seg-rfm', 'value')
)
def treemap_click(cd, cur):
    if cd is None:
        return cur
    clicked = cd['points'][0].get('label', None)
    if clicked == cur:
        return None
    return clicked

@app.callback(Output('badge-rfm','children'), Input('year-rfm','value'), Input('seg-rfm','value'))
def badge_rfm(y,s):
    p=[]; 
    if y!='all': p.append(str(y))
    if s: p.append(s)
    return f'Showing: {" · ".join(p) if p else "All Data"}'

@app.callback(Output('rfm-kpis','children'), Input('year-rfm','value'), Input('seg-rfm','value'))
def rfm_kpis(y,s):
    fdf=filter_df(df,y,s); frfm=filter_rfm(rfm,y,s,df)
    color=SEGMENT_COLORS.get(s,'#0C447C') if s else '#0C447C'
    rev=fdf['revenue'].sum(); c=fdf['customer_id'].nunique()
    o=fdf['invoice'].nunique(); aov=rev/o if o>0 else 0
    pr=frfm['monetary'].sum()/rfm['monetary'].sum()*100
    pc=len(frfm)/len(rfm)*100 if len(rfm)>0 else 0
    ar=frfm['recency'].mean() if len(frfm)>0 else 0
    af=frfm['frequency'].mean() if len(frfm)>0 else 0
    return [
        kpi_card('Segment', s or 'All Segments', color),
        kpi_card('Customers', f'{c:,}', color, subtitle=f'{pc:.1f}% of total'),
        kpi_card('Avg Recency', f'{ar:.0f} days', color, subtitle='Since last purchase'),
        kpi_card('Avg Frequency', f'{af:.1f} orders', color),
        kpi_card('Avg Order Value', f'\u00a3{aov:,.2f}', color),
        kpi_card('Segment Revenue', f'\u00a3{rev:,.0f}', color),
        kpi_card('% of Revenue', f'{pr:.1f}%', color),
    ]

@app.callback(Output('rfm-monthly','figure'), Input('year-rfm','value'), Input('seg-rfm','value'))
def rfm_monthly(y,s): return monthly_fig(filter_df(df,y,s), s)

@app.callback(Output('rfm-treemap','figure'), Input('year-rfm','value'))
def rfm_treemap(y):
    frfm=filter_rfm(rfm,y,None,df)
    ss=(frfm.groupby('segment').agg(customers=('customer_id','count'),
        revenue=('monetary','sum'),avg_monetary=('monetary','mean'),
        avg_frequency=('frequency','mean')).reset_index())
    ss['pct_revenue']  =(ss['revenue']/ss['revenue'].sum()*100).round(1)
    ss['pct_customers']=(ss['customers']/ss['customers'].sum()*100).round(1)
    
    fig=px.treemap(ss,path=['segment'],values='customers',color='pct_revenue',
                   color_continuous_scale='Blues',
                   custom_data=['pct_revenue','pct_customers','avg_monetary','avg_frequency'])
    
    fig.update_traces(
        level=0, 
        maxdepth=1,
        texttemplate='<b>%{label}</b><br>%{value} customers (%{customdata[1]:.1f}%)<br>%{customdata[0]:.1f}% of revenue',
        hovertemplate='<b>%{label}</b><br>Customers: %{value} (%{customdata[1]:.1f}% of total)<br>Revenue share: %{customdata[0]:.1f}%<br>Avg spend: \u00a3%{customdata[2]:,.0f}<br>Avg orders: %{customdata[3]:.1f}<extra></extra>',
        textfont_size=11)
    
    fig.update_layout(height=300,margin=dict(t=10,b=10,l=10,r=10),coloraxis_showscale=False)
    return fig

@app.callback(Output('rfm-pareto','figure'), Input('year-rfm','value'), Input('seg-rfm','value'))
def rfm_pareto(y,s):
    frfm=filter_rfm(rfm,y,s,df); color=get_color(s)
    if len(frfm)==0: return go.Figure()
    sr=frfm.sort_values('monetary',ascending=False).reset_index(drop=True)
    sr['cp']=(np.arange(1,len(sr)+1)/len(sr)*100)
    sr['cr']=(sr['monetary'].cumsum()/sr['monetary'].sum()*100)
    top20=sr[sr['cp']<=20]['monetary'].sum(); share=top20/sr['monetary'].sum()*100
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=sr['cp'],y=sr['cr'],mode='lines',
                             line=dict(color=color,width=2.5),fill='tozeroy',
                             fillcolor='rgba(55,138,221,0.1)',
                             hovertemplate='Top %{x:.1f}% \u2192 %{y:.1f}% of revenue<extra></extra>'))
    fig.add_vline(x=20,line_dash='dash',line_color='#D85A30',line_width=1.5)
    fig.add_hline(y=share,line_dash='dash',line_color='#1D9E75',line_width=1.5,
                  annotation_text=f'Top 20% \u2192 {share:.0f}% revenue',annotation_position='right')
    fig.update_layout(margin=dict(t=10,b=40,l=40,r=100),height=300,
                      plot_bgcolor='white',paper_bgcolor='white',
                      xaxis=dict(title='% of customers',gridcolor='#f0f0f0',range=[0,100]),
                      yaxis=dict(title='Cumulative % of revenue',gridcolor='#f0f0f0',range=[0,100]),
                      showlegend=False)
    return fig

@app.callback(Output('rfm-scatter','figure'), Input('year-rfm','value'), Input('seg-rfm','value'))
def rfm_scatter(y,s):
    frfm=filter_rfm(rfm,y,s,df)
    if len(frfm)==0: return go.Figure()
    fig=go.Figure(go.Scatter(x=frfm['frequency'],y=frfm['monetary'],mode='markers',
        marker=dict(size=7,color=frfm['recency'],colorscale='Blues_r',showscale=True,
                    colorbar=dict(title='Recency<br>(days)',thickness=12,len=0.8),
                    opacity=0.7,line=dict(width=0.5,color='white')),
        hovertemplate='Customer: %{text}<br>Orders: %{x}<br>Total spend: \u00a3%{y:,.0f}<extra></extra>',
        text=frfm['customer_id'].astype(str)))
    fig.update_layout(margin=dict(t=10,b=40,l=60,r=80),height=300,
                      plot_bgcolor='white',paper_bgcolor='white',
                      xaxis=dict(title='Number of orders',gridcolor='#f0f0f0'),
                      yaxis=dict(title='Total spend (\u00a3)',tickprefix='\u00a3',gridcolor='#f0f0f0'),
                      showlegend=False)
    return fig

# --- Behavior Callbacks ---
@app.callback(Output('badge-beh','children'), Input('year-beh','value'), Input('seg-beh','value'))
def badge_beh(y,s):
    p=[]
    if y!='all': p.append(str(y))
    if s: p.append(s)
    return f'Showing: {" · ".join(p) if p else "All Data"}'

@app.callback(Output('beh-dow','figure'), Input('year-beh','value'), Input('seg-beh','value'))
def beh_dow(y,s): return dow_fig(filter_df(df,y,s), s)

@app.callback(Output('beh-hour','figure'), Input('year-beh','value'), Input('seg-beh','value'))
def beh_hour(y,s):
    fdf=filter_df(df,y,s); color=get_color(s)
    h=(fdf.groupby('hour')['invoice'].nunique().reset_index().rename(columns={'invoice':'orders'}))
    fig=go.Figure(go.Bar(x=h['hour'],y=h['orders'],marker_color=color,opacity=0.85,
                         hovertemplate='<b>%{x}:00</b><br>Orders: %{y:,}<extra></extra>'))
    fig.update_layout(margin=dict(t=10,b=40,l=40,r=10),height=280,
                      plot_bgcolor='white',paper_bgcolor='white',
                      xaxis=dict(title='Hour of day',gridcolor='#f0f0f0',tickmode='linear',tick0=0,dtick=1),
                      yaxis=dict(gridcolor='#f0f0f0',title='Orders'),showlegend=False)
    return fig

@app.callback(Output('beh-heatmap','figure'), Input('year-beh','value'), Input('seg-beh','value'))
def beh_heatmap(y,s):
    fdf=filter_df(df,y,s)
    heat=(fdf.groupby(['day_of_week','hour'])['revenue'].sum().unstack(fill_value=0)
             .reindex([d for d in DOW_ORDER if d in fdf['day_of_week'].unique()]))
    fig=go.Figure(go.Heatmap(z=heat.values,x=heat.columns.astype(str),y=heat.index,
                              colorscale='Blues',
                              hovertemplate='%{y} %{x}:00<br>Revenue: \u00a3%{z:,.0f}<extra></extra>'))
    fig.update_layout(margin=dict(t=10,b=40,l=100,r=10),height=280,
                      plot_bgcolor='white',paper_bgcolor='white',
                      xaxis_title='Hour of day',yaxis_title='')
    return fig

@app.callback(Output('beh-new-ret','figure'), Input('year-beh','value'), Input('seg-beh','value'))
def beh_new_ret(y,s):
    fdf=filter_df(df,y,s)
    first=(fdf.groupby('customer_id')['year_month'].min().reset_index()
              .rename(columns={'year_month':'first_month'}))
    tagged=fdf.merge(first,on='customer_id')
    tagged['type']=np.where(tagged['year_month']==tagged['first_month'],'New','Returning')
    monthly=(tagged.groupby(['year_month','month_label','type'])['customer_id']
                   .nunique().unstack(fill_value=0).reset_index().sort_values('year_month'))
    tv=monthly['year_month'].tolist()[::2]
    tt=monthly.loc[monthly['year_month'].isin(tv),'month_label'].tolist()
    fig=go.Figure()
    if 'New' in monthly.columns:
        fig.add_trace(go.Bar(x=monthly['year_month'],y=monthly['New'],name='New',
                             marker_color='#1D9E75',opacity=0.85,customdata=monthly['month_label'],
                             hovertemplate='<b>%{customdata}</b><br>New: %{y:,}<extra></extra>'))
    if 'Returning' in monthly.columns:
        fig.add_trace(go.Bar(x=monthly['year_month'],y=monthly['Returning'],name='Returning',
                             marker_color='#378ADD',opacity=0.85,customdata=monthly['month_label'],
                             hovertemplate='<b>%{customdata}</b><br>Returning: %{y:,}<extra></extra>'))
    fig.update_layout(barmode='stack',margin=dict(t=10,b=50,l=40,r=10),height=280,
                      plot_bgcolor='white',paper_bgcolor='white',
                      xaxis=dict(tickmode='array',tickvals=tv,ticktext=tt,tickangle=-45,gridcolor='#f0f0f0'),
                      yaxis=dict(gridcolor='#f0f0f0',title='Customers'),
                      legend=dict(orientation='h',y=1.12,x=0),hovermode='x unified')
    return fig

@app.callback(Output('beh-freq','figure'), Input('year-beh','value'), Input('seg-beh','value'))
def beh_freq(y,s): return freq_dist(filter_df(df,y,s), s)

if __name__ == '__main__':
    app.run(debug=True)