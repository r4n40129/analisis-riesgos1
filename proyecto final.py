import dash
from dash import dcc, html, Input, Output, State
import pandas as pd
import plotly.express as px
import base64
import io

app = dash.Dash(__name__)

# Layout del Dashboard
app.layout = html.Div([
    html.H1("Dashboard de Análisis de Riesgos", style={'textAlign': 'center'}),
    dcc.Upload(
        id='upload-data',
        children=html.Button('Subir Archivo CSV o Excel'),
        multiple=False
    ),
    dcc.Store(id='data-store', data=None),
    html.Div(id='output-data-upload', style={'marginTop': '10px'}),
    dcc.RangeSlider(id='year-slider', step=1, marks={}, tooltip={"placement": "bottom"}),
    dcc.Dropdown(id='name-dropdown', clearable=True, placeholder="Selecciona un nombre"),
    dcc.Dropdown(id='risk-dropdown', clearable=True, placeholder="Selecciona un riesgo"),
    dcc.Graph(id='grafico-riesgos'),
    dcc.Graph(id='grafico-variaciones'),
    html.Div(id='tabla-resumen', style={'marginTop': '20px'})
])

# Función para procesar archivos
def parse_contents(contents, filename):
    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        ext = filename.split('.')[-1].lower()
        
        if ext == 'csv':
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        elif ext in ['xls', 'xlsx']:
            df = pd.read_excel(io.BytesIO(decoded))
        else:
            return None
        
        required_cols = {'AÑO', 'RIESGOS', 'NOMBRE'}
        if not required_cols.issubset(set(df.columns)):
            return None
        
        df = df.dropna(subset=['AÑO', 'RIESGOS', 'NOMBRE'])
        df['AÑO'] = pd.to_numeric(df['AÑO'], errors='coerce').astype('Int64')
        return df.dropna()
    except Exception as e:
        print(f"Error al leer el archivo: {e}")
        return None

# Callback para cargar datos
@app.callback(
    [Output('year-slider', 'min'), Output('year-slider', 'max'), Output('year-slider', 'value'),
     Output('year-slider', 'marks'), Output('risk-dropdown', 'options'), Output('name-dropdown', 'options'),
     Output('output-data-upload', 'children'), Output('data-store', 'data')],
    [Input('upload-data', 'contents')],
    [State('upload-data', 'filename')]
)
def cargar_datos(contents, filename):
    if contents is None:
        return None, None, None, {}, [], [], "Sube un archivo para comenzar.", None
    
    df = parse_contents(contents, filename)
    if df is None:
        return None, None, None, {}, [], [], "Error en el archivo. Asegúrate de que tiene las columnas 'AÑO', 'RIESGOS' y 'NOMBRE'.", None
    
    min_year, max_year = df['AÑO'].min(), df['AÑO'].max()
    marks = {year: str(year) for year in range(min_year, max_year + 1)}
    risks = [{'label': r, 'value': r} for r in sorted(df['RIESGOS'].dropna().unique())]
    risks.insert(0, {'label': "Todos", 'value': "Todos"})
    names = [{'label': n, 'value': n} for n in sorted(df['NOMBRE'].dropna().unique())]
    names.insert(0, {'label': "Todos", 'value': "Todos"})
    
    return min_year, max_year, [min_year, max_year], marks, risks, names, f"Archivo {filename} cargado correctamente.", df.to_dict()

# Callback para actualizar gráficos y tabla
@app.callback(
    [Output('grafico-riesgos', 'figure'), Output('tabla-resumen', 'children')],
    [Input('year-slider', 'value'), Input('risk-dropdown', 'value'), Input('name-dropdown', 'value')],
    [State('data-store', 'data')]
)
def actualizar_dashboard(year_range, risk_selected, name_selected, data):
    if data is None or year_range is None:
        return px.bar(title="Sube un archivo para visualizar datos"), ""
    
    df = pd.DataFrame(data)
    df_filtrado = df[(df['AÑO'] >= year_range[0]) & (df['AÑO'] <= year_range[1])]
    
    if risk_selected and risk_selected != "Todos":
        df_filtrado = df_filtrado[df_filtrado['RIESGOS'] == risk_selected]
    
    if name_selected and name_selected != "Todos":
        df_filtrado = df_filtrado[df_filtrado['NOMBRE'] == name_selected]
    
    if df_filtrado.empty:
        return px.bar(title="No hay datos para mostrar"), html.Div("No hay datos disponibles para los filtros seleccionados")
    
    df_riesgos = df_filtrado.groupby(['AÑO', 'RIESGOS']).size().reset_index(name='Total de Pacientes')
    fig = px.bar(df_riesgos, x='AÑO', y='Total de Pacientes', color='RIESGOS', title="Distribución de Pacientes por Año y Riesgo")
    
    tabla = html.Table([
        html.Tr([html.Th("Año"), html.Th("Riesgo"), html.Th("Total de Pacientes")])
    ] + [
        html.Tr([html.Td(a), html.Td(r), html.Td(c)]) for a, r, c in zip(df_riesgos['AÑO'], df_riesgos['RIESGOS'], df_riesgos['Total de Pacientes'])
    ])
    
    return fig, tabla

# Callback para analizar variaciones en el tiempo según el riesgo seleccionado
@app.callback(
    Output('grafico-variaciones', 'figure'),
    [Input('year-slider', 'value'), Input('risk-dropdown', 'value')],
    [State('data-store', 'data')]
)
def analizar_variaciones(year_range, risk_selected, data):
    if data is None or year_range is None:
        return px.line(title="Sube un archivo para visualizar variaciones")
    
    df = pd.DataFrame(data)
    df_filtrado = df[(df['AÑO'] >= year_range[0]) & (df['AÑO'] <= year_range[1])]
    
    if risk_selected and risk_selected != "Todos":
        df_filtrado = df_filtrado[df_filtrado['RIESGOS'] == risk_selected]
    
    if df_filtrado.empty:
        return px.line(title="No hay datos disponibles para los filtros seleccionados")
    
    df_variacion = df_filtrado.groupby('AÑO').size().reset_index(name='Total')
    df_variacion['Variación (%)'] = df_variacion['Total'].pct_change() * 100
    
    fig = px.line(df_variacion, x='AÑO', y='Total', title="Variación de Pacientes por Año", markers=True)
    fig.add_scatter(x=df_variacion['AÑO'], y=df_variacion['Variación (%)'], mode='lines+markers', name="Variación (%)")
    
    return fig

if __name__ == '__main__':
    app.run_server(debug=True) 
