import dash
from dash import dcc, html, ctx
import dash_bootstrap_components as dbc
import dash_daq as daq
import plotly.graph_objects as go
import pandas as pd
import time
import logging
from dash.dependencies import Input, Output, State, ClientsideFunction


#            IMPORTACIÓN GESTOR TCP

try:
    from tcp_manager import get_sensor_buffer, send_tcp_command, set_target_ip, is_esp_connected, purge_buffer
    print("[SISTEMA] Conectado al Gestor TCP.")
except ImportError:
    print("[ERROR] No se encuentra tcp_manager.py. Usando modo simulado.")
    def get_sensor_buffer(): return [], (0,0,0,0,0)
    def send_tcp_command(msg): return False
    def set_target_ip(ip): pass
    def is_esp_connected(): return False
    def purge_buffer(): pass

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app

#               ESTILOS Y CONFIGURACIÓN

COLOR_BLUE = "#1B396A"
COLOR_RED = "#E31937"
COLOR_GREEN = "#28A745"
COLOR_GREEN_DARK = "#28A746DA"
COLOR_BG_LIGHT = "#f4f4f4"
COLOR_BG_LIGHT_DARK = "#e0e0e0"
COLOR_TEXT_DARK = "#333333"

sidebar_style = {'backgroundColor': COLOR_BLUE, 'color': 'white', 'minHeight': '100vh', 'padding': '20px', 'boxShadow': '4px 0 10px rgba(0,0,0,0.1)'}
content_style = {'backgroundColor': COLOR_BG_LIGHT, 'minHeight': '100vh', 'padding': '20px'}
card_style = {'backgroundColor': 'white', 'border': f'2px solid {COLOR_BLUE}', 'borderRadius': '10px', 'padding': '15px', 'marginBottom': '20px', 'boxShadow': '0 4px 6px rgba(0,0,0,0.05)'}
card_red_style = {**card_style, 'border': f'3px solid {COLOR_RED}'}
input_style = {'backgroundColor': 'white', 'color': COLOR_TEXT_DARK, 'borderColor': '#ccc', 'textAlign': 'center'}
sidebar_label = {'color': '#f8f9fa', 'fontWeight': '600', 'fontSize': '0.85rem', 'textTransform': 'uppercase', 'letterSpacing': '1px'}

def create_chart(x, y, title, xl, yl, color):
    fig = go.Figure()
    if x and len(x) > 0:
        fig.add_trace(go.Scattergl(
            x=x, y=y, mode='lines',
            line=dict(color=color, width=2)
        ))
    
    fig.update_layout(
        title=dict(text=title, font=dict(color=COLOR_BLUE, size=16, family="Arial"), x=0.5),
        template='plotly_white', paper_bgcolor='white', plot_bgcolor='white',
        margin=dict(l=50, r=20, t=50, b=50),
        xaxis=dict(title=xl, showgrid=True, gridcolor='#eee', zeroline=False),
        yaxis=dict(title=yl, showgrid=True, gridcolor='#eee', zeroline=False),
        font=dict(family="Arial, sans-serif", color=COLOR_TEXT_DARK),
        hovermode="x unified"
    )
    if not x: 
        fig.update_layout(xaxis=dict(range=[0, 10]), yaxis=dict(range=[0, 10]))
    return fig


#                           LAYOUT

app.layout = dbc.Container([
    dcc.Store(id='session-store', data={'running': False, 'start_time': None}),
    dcc.Store(id='main-store', data={'t': [], 'f': [], 'p': [], 'l': [], 'a': [], 'pwm': []}),
    dcc.Store(id='ip-store', storage_type='local'), 
    dcc.Interval(id='intervalo-lectura', interval=500, n_intervals=0),
    dcc.Download(id="download-excel"),

    dbc.Row([
        # --- SIDEBAR ---
        dbc.Col([
            html.Div(style=sidebar_style, children=[
                html.Div(className="d-flex align-items-center justify-content-between mb-4", children=[
                    html.Img(src="/assets/escudo_tecnm.png", style={'height': '60px', 'width': 'auto'}),
                    html.H3("McKibben", style={'fontWeight': 'bold', 'margin': '0', 'fontSize': '1.5rem', 'textAlign': 'center'}),
                    html.Img(src="/assets/escudo_tec.png", style={'height': '60px', 'width': 'auto'})
                ]),
                html.Hr(style={'borderColor': 'rgba(255,255,255,0.4)'}),

                # SECCIÓN IP
                html.Div(className="mb-3", children=[
                    html.Div(className="d-flex justify-content-between align-items-center mb-2", children=[
                        html.Label("CONEXIÓN ESP32", style=sidebar_label),
                        html.Div(id="ip-feedback-text", style={'fontSize': '0.75rem', 'color': '#00ffcc', 'fontWeight': 'bold'})
                    ]),
                    dbc.InputGroup([
                        dbc.Input(id="input-ip-address", placeholder="192.168.1.x", style=input_style),
                        dbc.Button("SET", id="btn-update-ip", color="danger", n_clicks=0, style={'fontWeight':'bold'}),
                    ], size="sm"),
                ]),

                # CONTROLES
                html.Div(className="mb-4", children=[
                    html.Label("ESTADO DEL SISTEMA", style=sidebar_label, className="mb-2 text-center w-100"),
                    html.Div(id="status-indicator", children="DESCONECTADO", 
                             style={'textAlign': 'center', 'color': 'white', 'marginBottom':'15px', 'fontWeight':'bold', 'fontSize':'0.9rem', 'backgroundColor': COLOR_RED, 'padding':'6px', 'borderRadius':'4px'}),
                    dbc.Row([
                        dbc.Col(dbc.Button("INICIAR", id="btn-start", color="light", className="w-100 mb-2 fw-bold", style={'color': COLOR_BLUE}, n_clicks=0, disabled=True), width=6),
                        dbc.Col(dbc.Button("BORRAR", id="btn-clear", color="danger", outline=True, className="w-100 mb-2 fw-bold", style={'backgroundColor': 'rgba(255,255,255,0.1)', 'color': 'white', 'borderColor':'white'}, n_clicks=0), width=6)
                    ]),
                    dbc.Button("RESET DE VALORES", id="btn-tare", color="light", className="w-100 mb-2 fw-bold", n_clicks=0, style={'color': COLOR_BLUE}),
                ]),
                html.Hr(style={'borderColor': 'rgba(255,255,255,0.2)'}),
                
                # TIPO PRUEBA Y MANUAL
                html.Label("TIPO DE PRUEBA", style=sidebar_label, className="mb-2"),
                dbc.ButtonGroup([
                    dbc.Button("Isométrica", id="btn-nav-iso", color="light", outline=False, className="w-50 fw-bold", style={'color': COLOR_BLUE}),
                    dbc.Button("Isotónica", id="btn-nav-isot", color="light", outline=True, className="w-50 fw-bold", style={'color': COLOR_BLUE}),
                ], className="w-100 mb-4"),

                html.Div([
                    html.Label("CONTROL MANUAL (PSI)", style=sidebar_label, className="text-center mb-2"),
                    html.Div(style={'display': 'flex', 'justifyContent': 'center', 'padding': '8px 0'}, children=[
                        daq.Knob(id='knob-presion', max=30, value=0.01, min=0, label="PSI", size=120, scale={'start': 0, 'interval': 5, 'labelInterval': 1}, textColor="white", color={"gradient":True, "ranges":{"green":[0,10],"yellow":[10,20],"red":[20,30]}})
                    ]),
                    html.Div([
                        dcc.Input(id='input-presion', type='number', min=0, max=30, value=0, step=0.1, style={**input_style, 'width': '80px', 'borderRadius':'5px', 'fontWeight':'bold'}),
                        dbc.Button("ENVIAR", id="btn-set-pressure", color="danger", size="sm", className="ms-2 fw-bold")
                    ], className="d-flex justify-content-center align-items-center mt-2 mb-2"),
                ], className="text-center mb-4"),

                # TELEMETRÍA
                html.Label("TELEMETRÍA", style=sidebar_label, className="mb-2 text-center"),
                dbc.Row([
                    dbc.Col(html.Div(style={'backgroundColor': 'white', 'padding': '8px', 'borderRadius': '6px'}, children=[html.Small("Long (cm)", className="text-muted", style={'fontSize':'0.7rem'}), html.H5(id="ind-len", children="0.0", style={'color': COLOR_BLUE, 'fontWeight':'bold', 'marginBottom':'0'})]), width=6),
                    dbc.Col(html.Div(style={'backgroundColor': 'white', 'padding': '8px', 'borderRadius': '6px'}, children=[html.Small("Pres (PSI)", className="text-muted", style={'fontSize':'0.7rem'}), html.H5(id="ind-pres", children="0.0", style={'color': COLOR_BLUE, 'fontWeight':'bold', 'marginBottom':'0'})]), width=6),
                    dbc.Col(html.Div(style={'backgroundColor': 'white', 'padding': '8px', 'borderRadius': '6px'}, children=[html.Small("Fuerza (N)", className="text-muted", style={'fontSize':'0.7rem'}), html.H5(id="ind-force", children="0.0", style={'color': COLOR_BLUE, 'fontWeight':'bold', 'marginBottom':'0'})]), width=6, className="mt-2"),
                    dbc.Col(html.Div(style={'backgroundColor': 'white', 'padding': '8px', 'borderRadius': '6px'}, children=[html.Small("Tiempo (s)", className="text-muted", style={'fontSize':'0.7rem'}), html.H5(id="ind-time", children="0.0", style={'color': COLOR_BLUE, 'fontWeight':'bold', 'marginBottom':'0'})]), width=6, className="mt-2"),
                    dbc.Col(html.Div(style={'backgroundColor': 'white', 'padding': '8px', 'borderRadius': '6px'}, children=[html.Small("Ángulo (°)", className="text-muted", style={'fontSize':'0.7rem'}), html.H5(id="ind-ang", children="0.0", style={'color': COLOR_BLUE, 'fontWeight':'bold', 'marginBottom':'0'})]), width=6, className="mt-2"),
                    dbc.Col(html.Div(style={'backgroundColor': 'white', 'padding': '8px', 'borderRadius': '6px'}, children=[html.Small("PWM (0-255)", className="text-muted", style={'fontSize':'0.7rem'}), html.H5(id="ind-pwm", children="0", style={'color': COLOR_BLUE, 'fontWeight':'bold', 'marginBottom':'0'})]), width=6, className="mt-2")
                ], className="g-2 text-center"),
                html.Br(),
                dbc.Button("Descargar Excel", id="btn-download", color="light", className="w-100 fw-bold", style={'color': COLOR_BLUE})
            ])
        ], width=12, md=4, lg=3, className="p-0"),

        # --- GRAPHICS CONTENT ---
        dbc.Col([
            html.Div(style=content_style, children=[
                html.Div(id="view-isometrica", children=[
                    html.H2("Análisis Isométrico", style={'color': COLOR_BLUE, 'fontWeight': 'bold'}, className="mb-4 text-center"),
                                                                # Gráfica de fuerza vs tiempo
                    html.Div(style=card_style, children=[html.H5("", className="text-center text-muted mb-3"), dcc.Graph(id='graph-iso-f-t', config={'displayModeBar': False}, style={'height': '700px'})])
                ]),
                html.Div(id="view-isotonica", style={'display': 'none'}, children=[
                    html.H2("Análisis Isotónico", style={'color': COLOR_BLUE, 'fontWeight': 'bold'}, className="mb-4 text-center"),
                    html.Div(style=card_red_style, children=[
                        html.H5("Configuración PID", style={'color': COLOR_RED, 'fontWeight': 'bold', 'borderBottom': f'1px solid {COLOR_RED}', 'paddingBottom':'10px'}, className="mb-3"),
                        dbc.Row([
                            dbc.Col([
                                html.Label("Ángulo Objetivo (°)", style={'color': COLOR_TEXT_DARK, 'fontWeight': 'bold'}),
                                dbc.Input(id="pid-setpoint", type="number", value=0, style={'fontSize': '1.8rem', 'textAlign': 'center', 'fontWeight': 'bold', 'color': COLOR_BLUE, 'borderColor': COLOR_BLUE, 'backgroundColor': '#eef6ff', 'height':'60px'}),
                                html.Small("(Rango sugerido: 0-20°)", className="text-muted d-block text-center mt-1")
                            ], width=12, lg=4),
                            dbc.Col([
                                dbc.Row([
                                dbc.Col([html.Label("Kp", style={'color': COLOR_TEXT_DARK, 'fontWeight': 'bold'}), dbc.Input(id="pid-kp", type="number", value=0, step=0.1, style=input_style)], width=4),
                                dbc.Col([html.Label("Ki", style={'color': COLOR_TEXT_DARK, 'fontWeight': 'bold'}), dbc.Input(id="pid-ki", type="number", value=0, step=0.01, style=input_style)], width=4),
                                dbc.Col([html.Label("Kd", style={'color': COLOR_TEXT_DARK, 'fontWeight': 'bold'}), dbc.Input(id="pid-kd", type="number", value=0, step=0.1, style=input_style)], width=4),
                            ])], width=12, lg=5, className="pt-3 pt-lg-0"),
                            dbc.Col([dbc.Button("ACTIVAR PID", id="btn-send-pid", color="danger", className="w-100 h-100 fw-bold shadow-sm", style={'fontSize':'1.2rem', 'minHeight':'60px'})], width=12, lg=3, className="pt-3 pt-lg-0"),
                        ]),
                        html.Div(id="pid-feedback", className="text-center mt-3 fw-bold", style={'color': COLOR_BLUE})
                    ]),
                    dbc.Row([
                                                                            # Gráfica de presión vs tiempo y presión vs longitud
                        dbc.Col(html.Div(style=card_style, children=[html.H6("", className="text-center text-muted"), dcc.Graph(id='graph-isot-p-t', config={'displayModeBar': False}, style={'height': '300px'})]), width=12, lg=6),
                        dbc.Col(html.Div(style=card_style, children=[html.H6("", className="text-center text-muted"), dcc.Graph(id='graph-isot-p-l', config={'displayModeBar': False}, style={'height': '300px'})]), width=12, lg=6),
                    ], className="mb-3"),
                                                                                # Gráfica de longitud vs tiempo
                    dbc.Row([dbc.Col(html.Div(style=card_style, children=[html.H6("", className="text-center text-muted"), dcc.Graph(id='graph-isot-l-t', config={'displayModeBar': False}, style={'height': '300px'})]), width=12)])
                ])
            ])
        ], width=12, md=8, lg=9, className="p-0")
    ], className="g-0")
], fluid=True, style={'padding': '0', 'backgroundColor': COLOR_BG_LIGHT})


#                CALLBACKS

app.clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks > 0) {
            const emptyLayout = {
                'title': {'text': ''},
                'template': 'plotly_white',
                'xaxis': {'range': [0, 10], 'title': 'Tiempo (s)'},
                'yaxis': {'range': [0, 10], 'title': ''}
            };
            const emptyFig = {'data': [], 'layout': emptyLayout};
            const emptyData = {'t': [], 'f': [], 'p': [], 'l': [], 'a': [], 'pwm': []};
            return [emptyFig, emptyFig, emptyFig, emptyFig, emptyData];
        }
        return window.dash_clientside.no_update;
    }
    """,
    [Output('graph-iso-f-t', 'figure', allow_duplicate=True), 
     Output('graph-isot-p-t', 'figure', allow_duplicate=True), 
     Output('graph-isot-p-l', 'figure', allow_duplicate=True), 
     Output('graph-isot-l-t', 'figure', allow_duplicate=True),
     Output('main-store', 'data', allow_duplicate=True)],
    [Input('btn-clear', 'n_clicks')],
    prevent_initial_call=True
)

# --- 2. IP Y PERSISTENCIA ---
@app.callback(
    [Output("ip-store", "data"), Output("ip-feedback-text", "children"), Output("input-ip-address", "value")],
    [Input("btn-update-ip", "n_clicks"), Input("ip-store", "data")], [State("input-ip-address", "value")]
)
def manage_ip(n_clicks, stored_ip, input_val):
    trigger = ctx.triggered_id
    if trigger is None or trigger == 'ip-store':
        if stored_ip: set_target_ip(stored_ip); return dash.no_update, stored_ip, stored_ip
        return dash.no_update, "", "192.168.1.100" 
    if trigger == 'btn-update-ip' and input_val:
        set_target_ip(str(input_val))
        return input_val, input_val, dash.no_update 
    return dash.no_update, dash.no_update, dash.no_update

# --- 3. CALLBACK MAESTRO --
@app.callback(
    [Output('main-store', 'data'), 
     Output('ind-len', 'children'), Output('ind-pres', 'children'), Output('ind-force', 'children'), 
     Output('ind-time', 'children'), Output('ind-ang', 'children'), Output('ind-pwm', 'children'),
     Output('graph-iso-f-t', 'figure'), Output('graph-isot-p-t', 'figure'), Output('graph-isot-p-l', 'figure'), Output('graph-isot-l-t', 'figure'),
     Output('status-indicator', 'children'), Output('status-indicator', 'style'), Output('btn-start', 'disabled')],
    [Input('intervalo-lectura', 'n_intervals'), Input('btn-clear', 'n_clicks')], 
    [State('main-store', 'data'), State('session-store', 'data')]
)
def ciclo_datos(n, n_clear, data, session):
    
    # 1. PURGA DE BACKEND (Complementa al JS)
    trigger = ctx.triggered_id
    if trigger == 'btn-clear':
        purge_buffer()
        return (
            {'t': [], 'f': [], 'p': [], 'l': [], 'a': [], 'pwm': []}, 
            "0.0", "0.0", "0.0", "0.00", "0.0", "0", 
            dash.no_update, dash.no_update, dash.no_update, dash.no_update,
            "LISTO", {'textAlign': 'center', 'marginBottom':'15px', 'fontWeight':'bold', 'fontSize':'0.9rem', 'padding':'6px', 'borderRadius':'4px', 'backgroundColor': COLOR_GREEN, 'color': 'white'}, False
        )

    # 2. INICIALIZACIÓN
    if data is None: data = {'t': [], 'f': [], 'p': [], 'l': [], 'a': [], 'pwm': []}
    if session is None: session = {'running': False, 'start_time': None}
    
    try: conectado = is_esp_connected()
    except: conectado = False
    
    style_base = {'textAlign': 'center', 'marginBottom':'15px', 'fontWeight':'bold', 'fontSize':'0.9rem', 'padding':'6px', 'borderRadius':'4px'}
    status_txt = "DESCONECTADO"
    status_style = {**style_base, 'backgroundColor': COLOR_RED, 'color': 'white'}
    btn_start_disabled = True

    if conectado:
        btn_start_disabled = False
        if session.get('running'):
            status_txt, status_style = "GRABANDO...", {**style_base, 'backgroundColor': COLOR_GREEN, 'color': 'white', 'animation': 'pulse 1s infinite'}
        elif session.get('start_time'):
            status_txt, status_style = "PAUSADO", {**style_base, 'backgroundColor': COLOR_GREEN_DARK, 'color': COLOR_BG_LIGHT_DARK} 
        else:
            status_txt, status_style = "LISTO", {**style_base, 'backgroundColor': COLOR_GREEN, 'color': 'white'}

    # 3. PROCESAMIENTO DE DATOS CON "CERROJO DE TIEMPO" (MONOTONIC TIME)
    try:
        buffer_list, latest = get_sensor_buffer()
        f_disp, l_disp, p_disp, a_disp, pwm_disp = latest
    except:
        buffer_list = []
        f_disp, l_disp, p_disp, a_disp, pwm_disp = 0.0, 0.0, 0.0, 0.0, 0.0

    display_time = "0.00"

    if trigger != 'btn-clear' and session.get('start_time'):
        t_now = time.time()
        start_t = session['start_time']
        display_time = f"{t_now - start_t:.2f}"
        
        if session.get('running') and buffer_list:

            last_t = data['t'][-1] if len(data['t']) > 0 else 0.0
            ideal_base_time = (t_now - start_t) - 0.5
            safe_base_time = max(ideal_base_time, last_t + 0.001)
            num_points = len(buffer_list)
            time_step = 0.5 / max(num_points, 1) 
            
            for i, vals in enumerate(buffer_list):
                vf, vl, vp, va, vpwm = vals
                t_point = safe_base_time + (i * time_step)
                
                if len(data['t']) > 0 and t_point <= data['t'][-1]:
                     t_point = data['t'][-1] + 0.001

                data['t'].append(t_point)
                data['f'].append(vf)
                data['p'].append(vp)
                data['l'].append(vl)
                if 'a' in data: data['a'].append(va)
                if 'pwm' in data: data['pwm'].append(vpwm)
            
            # Limitar historial
            MAX_POINTS = 10000 
            if len(data['t']) > MAX_POINTS:
                excess = len(data['t']) - MAX_POINTS
                for k in data: data[k] = data[k][excess:]

    fig1 = create_chart(data['t'], data['f'], "Fuerza (N) vs Tiempo (s)", "Tiempo (s)", "Fuerza (N)", COLOR_BLUE)
    fig2 = create_chart(data['t'], data['p'], "Presión (PSI) vs Tiempo (s)", "Tiempo (s)", "Presión (PSI)", COLOR_RED)
    fig3 = create_chart(data['p'], data['l'], "Longitud (cm) vs Presión (PSI)", "Presión (PSI)", "Longitud (cm)", COLOR_GREEN)
    fig4 = create_chart(data['t'], data['l'], "Longitud (cm) vs Tiempo (s)", "Tiempo (s)", "Longitud (cm)", COLOR_BLUE)

    return (data, f"{l_disp:.1f}", f"{p_disp:.1f}", f"{f_disp:.1f}", display_time, f"{a_disp:.1f}", f"{int(pwm_disp)}", 
            fig1, fig2, fig3, fig4, status_txt, status_style, btn_start_disabled)

# --- 4. OTROS BOTONES ---
@app.callback(
    [Output('session-store', 'data', allow_duplicate=True), Output('btn-start', 'children'), Output('btn-start', 'color'), Output('btn-start', 'style')],
    [Input('btn-start', 'n_clicks'), Input('btn-clear', 'n_clicks')], [State('session-store', 'data')], prevent_initial_call=True
)
def botones_accion(n_start, n_clear, session):
    trigger = ctx.triggered_id
    if session is None: session = {'running': False, 'start_time': None}

    if trigger == 'btn-clear':
        return ({'running': False, 'start_time': None}, "INICIAR", "light", {'color': COLOR_BLUE, 'fontWeight':'bold'})

    if trigger == 'btn-start':
        session['running'] = not session['running']
        if session['running'] and session['start_time'] is None: session['start_time'] = time.time()
        
        if session['running']:
            return session, "PAUSAR", "warning", {'color': COLOR_BLUE, 'fontWeight':'bold'}
        else:
            return session, "SEGUIR", "light", {'color': COLOR_BLUE, 'fontWeight':'bold'}
    return dash.no_update, dash.no_update, dash.no_update, dash.no_update

@app.callback(Output("btn-tare", "children"), Input("btn-tare", "n_clicks"), prevent_initial_call=True)
def tarar_sensores(n):
    if send_tcp_command("TARA"): return "RESET DE VALORES"
    return "ERROR"

@app.callback(Output("pid-feedback", "children"), Input("btn-send-pid", "n_clicks"), [State("pid-setpoint", "value"), State("pid-kp", "value"), State("pid-ki", "value"), State("pid-kd", "value")], prevent_initial_call=True)
def send_pid_command(n, sp, kp, ki, kd):
    if sp is None: return "Error"
    if send_tcp_command(f"P:{sp}:{kp}:{ki}:{kd}"): return html.Span(f"PID Enviado: {sp}°", style={'color':'#28a745'})
    return html.Span("Error", style={'color': COLOR_RED})

@app.callback([Output("view-isometrica", "style"), Output("view-isotonica", "style"), Output("btn-nav-iso", "outline"), Output("btn-nav-isot", "outline"), Output("btn-nav-iso", "style"), Output("btn-nav-isot", "style")], [Input("btn-nav-iso", "n_clicks"), Input("btn-nav-isot", "n_clicks")])
def switch_view(b1, b2):
    act, inact = {'color': COLOR_BLUE, 'backgroundColor': 'white', 'borderColor': 'white'}, {'color': 'white', 'backgroundColor': COLOR_BLUE, 'borderColor': 'white'}
    if ctx.triggered_id == "btn-nav-isot": return {'display': 'none'}, {'display': 'block'}, True, False, inact, act
    return {'display': 'block'}, {'display': 'none'}, False, True, act, inact

@app.callback(Output('btn-set-pressure', 'disabled'), [Input('btn-set-pressure', 'n_clicks'), Input('knob-presion', 'value')], State('input-presion', 'value'), prevent_initial_call=True)
def set_pressure(n, knob, val):
    v = val if val is not None else knob
    if v is None: v = 0
    pwm = int((v / 30.0) * 255)
    send_tcp_command(str(pwm))
    return dash.no_update

@app.callback([Output('knob-presion', 'value'), Output('input-presion', 'value')], [Input('knob-presion', 'value'), Input('input-presion', 'value')], prevent_initial_call=True)
def sync(k, i): return (i, i) if ctx.triggered_id == 'input-presion' else (k, k)

@app.callback(Output("download-excel", "data"), Input("btn-download", "n_clicks"), State('main-store', 'data'), prevent_initial_call=True)
def download(n, data):
    if not data or not data.get('t'): return dash.no_update
    return dcc.send_data_frame(pd.DataFrame(data).to_excel, "Datos_McKibben_ITToluca.xlsx", index=False)

if __name__ == '__main__':

    app.run(debug=False, host='localhost', port=4050)
