import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from mplsoccer import Pitch

# ==========================================
# 1. CONFIGURACIÓN GENERAL DE LA PÁGINA
# ==========================================
st.set_page_config(
    page_title="FOOTBALL DATA PRO | Analytics & Scouting",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==========================================
# 2. ESTILOS VISUALES (DISEÑO BRUTAL OSCURO)
# ==========================================
st.markdown(
    """
<style>
    .stApp {
        background: radial-gradient(circle at top left, #0f172a 0%, #060913 55%, #03050a 100%);
        color: #f8fafc;
    }
    .hero-banner {
        background: linear-gradient(135deg, rgba(16,185,129,0.18) 0%, rgba(14,165,233,0.14) 50%, rgba(245,158,11,0.14) 100%);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 18px;
        padding: 22px 26px;
        margin-bottom: 18px;
        box-shadow: 0 12px 32px rgba(0,0,0,0.45);
    }
    .hero-title {
        font-size: 30px;
        font-weight: 800;
        letter-spacing: -0.5px;
        margin: 0;
        color: #ffffff;
    }
    .hero-sub {
        color: #94a3b8;
        font-size: 14px;
        margin-top: 6px;
    }
    .kpi-card {
        background: rgba(15, 23, 42, 0.85);
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 14px;
        padding: 16px;
        box-shadow: 0 6px 18px rgba(0,0,0,0.3);
    }
    .kpi-label {
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        color: #94a3b8;
        font-weight: 700;
    }
    .kpi-value {
        font-size: 26px;
        font-weight: 800;
        color: #10b981;
        margin-top: 4px;
    }
    .kpi-delta {
        font-size: 12px;
        color: #38bdf8;
        margin-top: 2px;
    }
    .player-card {
        background: linear-gradient(160deg, #111827 0%, #0b1120 100%);
        border: 1px solid rgba(16, 185, 129, 0.35);
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.45);
    }
    .player-name {
        font-size: 22px;
        font-weight: 800;
        color: #ffffff;
        margin-bottom: 2px;
    }
    .player-meta {
        font-size: 13px;
        color: #10b981;
        font-weight: 600;
        margin-bottom: 14px;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ==========================================
# 3. CATÁLOGO DE LIGAS Y TORNEOS GLOBALES
# ==========================================
LIGAS_DISPONIBLES = [
    "UEFA Champions League",
    "UEFA Europa League",
    "UEFA Conference League",
    "LaLiga (España)",
    "Premier League (Inglaterra)",
    "Serie A (Italia)",
    "Bundesliga (Alemania)",
    "Ligue 1 (Francia)",
    "Saudi Pro League (Arabia)",
    "J1 League (Japón - Asia)",
    "K League 1 (Corea - Asia)",
    "AFC Champions League Elite (Asia)",
    "Liga Nacional de Guatemala",
]

# ==========================================
# 4. MOTOR DE DATOS (API + BASE MULTILIGA)
# ==========================================
def calcular_xg_modelo(x: float, y: float, es_cabeza: bool = False, situacion: str = "Jugada abierta") -> float:
    """
    Modelo estadístico de Goles Esperados (xG) basado en distancia y ángulo al arco
    sobre una cancha estándar de 120x80 (arco centrado en x=120, y=40).
    """
    dx = max(0.5, 120.0 - x)
    dy = abs(40.0 - y)
    distancia = np.sqrt(dx**2 + dy**2)

    # Ángulo entre postes (ancho de portería ~ 7.32 unidades en escala 120x80)
    angulo = np.arctan2(7.32 * dx, max(0.01, dx**2 + dy**2 - (7.32 / 2.0) ** 2))
    angulo = max(0.02, abs(angulo))

    # Regresión logística calibrada para fútbol
    z = -0.55 - (0.068 * distancia) + (1.35 * angulo)
    if es_cabeza:
        z -= 0.72
    if situacion == "Penalti":
        return 0.78
    if situacion == "Tiro libre":
        z -= 0.45
    if situacion == "Contragolpe":
        z += 0.25

    xg = 1.0 / (1.0 + np.exp(-z))
    return round(float(np.clip(xg, 0.01, 0.92)), 2)


@st.cache_data(show_spinner=False)
def generar_datos_liga(liga: str, api_key: str = ""):
    """
    Genera resultados, tabla de posiciones, ficha de jugadores y eventos de tiro (xG)
    para la liga seleccionada. Si se ingresa una API Key válida de API-Football, intenta
    consultar partidos reales de esa liga y combina con los datos analíticos.
    """
    seed = abs(hash(liga)) % (2**31 - 1)
    rng = np.random.default_rng(seed)

    equipos_por_liga = {
        "UEFA Champions League": ["Real Madrid", "Man City", "Bayern Múnich", "Inter Milan", "Arsenal", "PSG", "Barcelona", "Atlético Madrid"],
        "UEFA Europa League": ["Athletic Club", "Roma", "Ajax", "Porto", "Tottenham", "Real Sociedad", "Lyon", "Fenerbahçe"],
        "UEFA Conference League": ["Chelsea", "Fiorentina", "Real Betis", "Heidenheim", "Copenhague", "Gent", "Omonia", "Legia"],
        "LaLiga (España)": ["Real Madrid", "Barcelona", "Atlético Madrid", "Athletic Club", "Real Sociedad", "Villarreal", "Betis", "Girona"],
        "Premier League (Inglaterra)": ["Man City", "Arsenal", "Liverpool", "Chelsea", "Aston Villa", "Newcastle", "Tottenham", "Brighton"],
        "Serie A (Italia)": ["Inter Milan", "Napoli", "Atalanta", "Juventus", "AC Milan", "Lazio", "Roma", "Fiorentina"],
        "Bundesliga (Alemania)": ["Bayern Múnich", "Bayer Leverkusen", "RB Leipzig", "Dortmund", "Stuttgart", "Eintracht", "Friburgo", "Wolfsburgo"],
        "Ligue 1 (Francia)": ["PSG", "Mónaco", "Marsella", "Lille", "Lyon", "Niza", "Lens", "Rennes"],
        "Saudi Pro League (Arabia)": ["Al-Hilal", "Al-Nassr", "Al-Ittihad", "Al-Ahli", "Al-Qadsiah", "Al-Taawoun", "Al-Fateh", "Al-Ettifaq"],
        "J1 League (Japón - Asia)": ["Vissel Kobe", "Sanfrecce Hiroshima", "Machida Zelvia", "Gamba Osaka", "Yokohama F.M.", "Urawa Reds", "Kawasaki", "Kashima"],
        "K League 1 (Corea - Asia)": ["Ulsan HD", "Gangwon FC", "FC Seoul", "Pohang Steelers", "Suwon FC", "Jeonbuk", "Incheon", "Daegu"],
        "AFC Champions League Elite (Asia)": ["Al-Hilal", "Al-Nassr", "Vissel Kobe", "Ulsan HD", "Al-Sadd", "Shandong Taishan", "Buriram Utd", "Johor DT"],
        "Liga Nacional de Guatemala": ["Comunicaciones", "Municipal", "Antigua GFC", "Cobán Imperial", "Xelajú MC", "Malacateco", "Mixco", "Guastatoya"],
    }

    equipos = equipos_por_liga.get(liga, [f"Club {i+1}" for i in range(8)])

    # Intento opcional de consulta real a API-Football si el usuario pega su clave
    api_status = "Modo Analítico Multiliga Activo"
    partidos_reales_rows = []
    if api_key.strip():
        try:
            headers = {"x-apisports-key": api_key.strip()}
            resp = requests.get("https://v3.football.api-sports.io/fixtures?last=10", headers=headers, timeout=6)
            if resp.status_code == 200:
                data_json = resp.json()
                for item in data_json.get("response", [])[:8]:
                    home = item["teams"]["home"]["name"]
                    away = item["teams"]["away"]["name"]
                    gh = item["goals"]["home"] if item["goals"]["home"] is not None else 0
                    ga = item["goals"]["away"] if item["goals"]["away"] is not None else 0
                    partidos_reales_rows.append({
                        "Liga": item["league"]["name"],
                        "Local": home,
                        "GL": gh,
                        "GV": ga,
                        "Visita": away,
                        "xG Local": round(max(0.2, gh * 0.85 + rng.uniform(-0.3, 0.5)), 2),
                        "xG Visita": round(max(0.2, ga * 0.85 + rng.uniform(-0.3, 0.5)), 2),
                        "Estado": "FT",
                    })
                if partidos_reales_rows:
                    api_status = "Conectado a API-Football (Resultados en vivo/recientes)"
        except Exception:
            api_status = "Sin conexión API externa — Usando motor de datos local"

    # Tabla de posiciones y resultados recientes
    tabla_rows = []
    for idx, eq in enumerate(equipos):
        pj = 12
        pg = int(np.clip(8 - idx + rng.integers(-1, 2), 1, pj))
        pe = int(np.clip(rng.integers(1, 4), 0, pj - pg))
        pp = pj - pg - pe
        gf = int(pg * rng.uniform(1.5, 2.4) + pe * 0.9)
        gc = int(pp * rng.uniform(1.4, 2.2) + pe * 0.9 + idx * 0.7)
        pts = pg * 3 + pe
        xg_a_favor = round(gf * rng.uniform(0.88, 1.15), 2)
        xg_en_contra = round(gc * rng.uniform(0.88, 1.15), 2)
        tabla_rows.append({
            "Pos": idx + 1,
            "Equipo": eq,
            "PJ": pj,
            "PG": pg,
            "PE": pe,
            "PP": pp,
            "GF": gf,
            "GC": gc,
            "DG": gf - gc,
            "xG": xg_a_favor,
            "xGA": xg_en_contra,
            "PTS": pts,
        })

    df_tabla = pd.DataFrame(tabla_rows).sort_values(by=["PTS", "DG", "GF"], ascending=False).reset_index(drop=True)
    df_tabla["Pos"] = df_tabla.index + 1

    # Resultados de partidos de la liga
    if partidos_reales_rows:
        df_resultados = pd.DataFrame(partidos_reales_rows)
    else:
        res_rows = []
        for i in range(4):
            h = equipos[i * 2]
            a = equipos[i * 2 + 1]
            gl = int(rng.integers(0, 4))
            ga = int(rng.integers(0, 3))
            xg_h = round(max(0.25, gl * 0.78 + rng.uniform(0.15, 0.75)), 2)
            xg_a = round(max(0.25, ga * 0.78 + rng.uniform(0.15, 0.75)), 2)
            res_rows.append({
                "Jornada": f"J{12 - (i % 3)}",
                "Local": h,
                "Marcador": f"{gl} - {ga}",
                "Visita": a,
                "xG Local": xg_h,
                "xG Visita": xg_a,
                "Estado": "Finalizado",
            })
        df_resultados = pd.DataFrame(res_rows)

    # Plantilla / Ficha individual de jugadores por liga
    posiciones = ["DEL", "EXT", "MED", "DEF", "DEL", "MED", "DEF", "DEL"]
    nombres_base = [
        "Mateo Silva", "Lucas Morales", "Diego Navarro", "Julián Ríos",
        "Sebastián Castro", "Andrés Mendoza", "Thiago Paredes", "Samuel Herrera",
    ]
    jugadores_rows = []
    for i, nombre in enumerate(nombres_base):
        equipo_j = equipos[i % len(equipos)]
        pos = posiciones[i % len(posiciones)]
        edad = int(rng.integers(19, 34))
        pj_j = int(rng.integers(8, 13))
        minutos = pj_j * int(rng.integers(68, 90))
        goles = int(rng.integers(0, 10)) if pos in ["DEL", "EXT", "MED"] else int(rng.integers(0, 3))
        asistencias = int(rng.integers(0, 8))
        xg_j = round(max(0.1, goles * rng.uniform(0.75, 1.25) + rng.uniform(0.2, 1.4)), 2)
        xa_j = round(max(0.1, asistencias * rng.uniform(0.8, 1.2) + rng.uniform(0.1, 1.1)), 2)
        tiros_90 = round(rng.uniform(1.2, 4.8), 1)
        pases_clave_90 = round(rng.uniform(0.8, 3.6), 1)
        duelos_ganados_pct = round(rng.uniform(45.0, 74.0), 1)
        progresion_90 = round(rng.uniform(2.5, 9.2), 1)
        rating = round(float(np.clip(6.4 + (goles * 0.14) + (asistencias * 0.12) + (duelos_ganados_pct - 50) * 0.015, 6.2, 9.2)), 2)

        jugadores_rows.append({
            "Jugador": f"{nombre} ({equipo_j[:3].upper()})",
            "Nombre Real": nombre,
            "Equipo": equipo_j,
            "Posición": pos,
            "Edad": edad,
            "PJ": pj_j,
            "Minutos": minutos,
            "Goles": goles,
            "Asistencias": asistencias,
            "xG Total": xg_j,
            "xA Total": xa_j,
            "Tiros / 90": tiros_90,
            "Pases Clave / 90": pases_clave_90,
            "Duelos Ganados %": duelos_ganados_pct,
            "Acciones Progresivas / 90": progresion_90,
            "Rating": rating,
        })

    df_jugadores = pd.DataFrame(jugadores_rows)

    # Tiros para el mapa de tiros (coordenadas x: 65..118, y: 8..72)
    tiros_rows = []
    situaciones = ["Jugada abierta", "Contragolpe", "Tiro libre", "Penalti"]
    for idx_t in range(42):
        jug = df_jugadores.iloc[idx_t % len(df_jugadores)]
        x_shot = float(rng.uniform(72.0, 117.5))
        y_shot = float(rng.uniform(12.0, 68.0))
        es_cab = bool(rng.random() < 0.22)
        sit = str(rng.choice(situaciones, p=[0.72, 0.15, 0.09, 0.04]))
        xg_val = calcular_xg_modelo(x_shot, y_shot, es_cabeza=es_cab, situacion=sit)
        es_gol = bool(rng.random() < min(0.88, xg_val * 1.15))

        tiros_rows.append({
            "Jugador": jug["Jugador"],
            "Equipo": jug["Equipo"],
            "Minuto": int(rng.integers(1, 92)),
            "x": round(x_shot, 1),
            "y": round(y_shot, 1),
            "xG": xg_val,
            "Gol": es_gol,
            "Resultado": "GOL" if es_gol else "Atajado / Fuera",
            "Situación": sit,
            "Cabeza": es_cab,
        })

    df_tiros = pd.DataFrame(tiros_rows)
    return df_tabla, df_resultados, df_jugadores, df_tiros, api_status


# ==========================================
# 5. BARRA LATERAL (CONTROLES Y FILTROS)
# ==========================================
with st.sidebar:
    st.markdown("## 🎛️ Panel de Control")
    liga_sel = st.selectbox("Selecciona Liga o Torneo", LIGAS_DISPONIBLES, index=0)
    api_key_input = st.text_input(
        "API-Football Key (Opcional)",
        type="password",
        help="Si tienes una clave de API-Football, pégala aquí para consultar partidos reales adicionales.",
    )

    df_tabla, df_resultados, df_jugadores, df_tiros, api_status = generar_datos_liga(liga_sel, api_key_input)

    equipo_filtro = st.selectbox(
        "Filtrar por Equipo",
        ["Todos los equipos"] + sorted(df_jugadores["Equipo"].unique().tolist()),
    )

    jugadores_filtrados_df = (
        df_jugadores if equipo_filtro == "Todos los equipos" else df_jugadores[df_jugadores["Equipo"] == equipo_filtro]
    )
    if jugadores_filtrados_df.empty:
        jugadores_filtrados_df = df_jugadores

    jugador_a = st.selectbox("Jugador Principal (Cuadro y Radar)", jugadores_filtrados_df["Jugador"].tolist(), index=0)
    jugador_b = st.selectbox(
        "Comparar Contra (Radar)",
        df_jugadores["Jugador"].tolist(),
        index=min(1, len(df_jugadores) - 1),
    )

    st.markdown("---")
    st.caption(f"Estado: {api_status}")


# ==========================================
# 6. ENCABEZADO Y MÉTRICAS PRINCIPALES (KPIs)
# ==========================================
st.markdown(
    f"""
<div class="hero-banner">
    <div class="hero-title">⚽ FOOTBALL ANALYTICS & SCOUTING STUDIO</div>
    <div class="hero-sub">Competencia activa: <b>{liga_sel}</b> · Modelo xG · Mapas de Tiros · Fichas de Jugadores · Comparativa Radar</div>
</div>
""",
    unsafe_allow_html=True,
)

total_goles_tiros = int(df_tiros["Gol"].sum())
xg_total_muestra = round(float(df_tiros["xG"].sum()), 2)
lider_tabla = df_tabla.iloc[0]
mejor_jugador = df_jugadores.sort_values("Rating", ascending=False).iloc[0]

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(
        f"""<div class="kpi-card"><div class="kpi-label">Líder de Tabla</div><div class="kpi-value">{lider_tabla['Equipo']}</div><div class="kpi-delta">{lider_tabla['PTS']} pts · DG {lider_tabla['DG']:+d}</div></div>""",
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        f"""<div class="kpi-card"><div class="kpi-label">Goles vs xG (Muestra)</div><div class="kpi-value">{total_goles_tiros} / {xg_total_muestra}</div><div class="kpi-delta">Eficiencia: {round(total_goles_tiros / max(0.1, xg_total_muestra), 2)}x</div></div>""",
        unsafe_allow_html=True,
    )
with c3:
    st.markdown(
        f"""<div class="kpi-card"><div class="kpi-label">Jugador Top Rating</div><div class="kpi-value">{mejor_jugador['Rating']}</div><div class="kpi-delta">{mejor_jugador['Jugador']}</div></div>""",
        unsafe_allow_html=True,
    )
with c4:
    st.markdown(
        f"""<div class="kpi-card"><div class="kpi-label">Tiros Analizados</div><div class="kpi-value">{len(df_tiros)}</div><div class="kpi-delta">xG Promedio: {round(float(df_tiros['xG'].mean()), 2)}</div></div>""",
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 7. PESTAÑAS PRINCIPALES DEL DASHBOARD
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Resultados y Tabla",
    "👤 Cuadro y Ficha del Jugador",
    "🎯 Mapa de Tiros y xG",
    "🕸️ Radar Comparativo",
])

# --- TAB 1: RESULTADOS Y TABLA ---
with tab1:
    col_res, col_tab = st.columns([1.05, 1.35])
    with col_res:
        st.subheader("Resultados Recientes")
        st.dataframe(df_resultados, use_container_width=True, hide_index=True)

        # Gráfico de goles vs xG por equipo en tabla
        fig_bar = go.Figure()
        top_eq = df_tabla.head(8)
        fig_bar.add_trace(go.Bar(name="Goles a Favor (GF)", x=top_eq["Equipo"], y=top_eq["GF"], marker_color="#10b981"))
        fig_bar.add_trace(go.Bar(name="Goles Esperados (xG)", x=top_eq["Equipo"], y=top_eq["xG"], marker_color="#38bdf8"))
        fig_bar.update_layout(
            barmode="group",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(15,23,42,0.6)",
            font_color="#f8fafc",
            height=320,
            margin=dict(l=10, r=10, t=25, b=10),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_tab:
        st.subheader(f"Tabla de Posiciones — {liga_sel}")
        st.dataframe(df_tabla, use_container_width=True, hide_index=True)

# --- TAB 2: CUADRO Y FICHA DE CADA JUGADOR ---
with tab2:
    st.subheader("Cuadro Detallado del Jugador Seleccionado")
    fila_a = df_jugadores[df_jugadores["Jugador"] == jugador_a].iloc[0]

    col_ficha, col_stats = st.columns([1, 1.4])
    with col_ficha:
        st.markdown(
            f"""
        <div class="player-card">
            <div class="player-name">{fila_a['Nombre Real']}</div>
            <div class="player-meta">{fila_a['Equipo']} · Posición: {fila_a['Posición']} · {fila_a['Edad']} años</div>
            <p><b>Partidos Jugados:</b> {fila_a['PJ']} &nbsp;|&nbsp; <b>Minutos:</b> {fila_a['Minutos']}'</p>
            <p><b>Goles:</b> {fila_a['Goles']} &nbsp;|&nbsp; <b>Asistencias:</b> {fila_a['Asistencias']}</p>
            <p><b>xG Total:</b> {fila_a['xG Total']} &nbsp;|&nbsp; <b>xA Total:</b> {fila_a['xA Total']}</p>
            <p><b>Tiros / 90:</b> {fila_a['Tiros / 90']} &nbsp;|&nbsp; <b>Pases Clave / 90:</b> {fila_a['Pases Clave / 90']}</p>
            <p><b>Duelos Ganados:</b> {fila_a['Duelos Ganados %']}% &nbsp;|&nbsp; <b>Rating:</b> ⭐ {fila_a['Rating']}</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col_stats:
        st.markdown("#### Cuadro General de Jugadores de la Liga")
        st.dataframe(df_jugadores, use_container_width=True, hide_index=True)

# --- TAB 3: MAPA DE TIROS Y CALCULADORA XG ---
with tab3:
    col_pitch, col_calc = st.columns([1.35, 1])

    with col_pitch:
        st.subheader("Mapa de Tiros en Cancha (mplsoccer)")
        tiros_vis = df_tiros if equipo_filtro == "Todos los equipos" else df_tiros[df_tiros["Equipo"] == equipo_filtro]
        if tiros_vis.empty:
            tiros_vis = df_tiros

        pitch = Pitch(pitch_type="statsbomb", pitch_color="#0b1320", line_color="#475569", linewidth=1.4)
        fig, ax = pitch.draw(figsize=(8, 5.5))
        fig.patch.set_facecolor("#060913")

        no_goles = tiros_vis[~tiros_vis["Gol"]]
        goles_df = tiros_vis[tiros_vis["Gol"]]

        pitch.scatter(
            no_goles["x"],
            no_goles["y"],
            s=no_goles["xG"] * 480 + 35,
            color="#38bdf8",
            edgecolors="#e2e8f0",
            alpha=0.72,
            ax=ax,
            label="Tiro sin gol (tamaño = xG)",
        )
        pitch.scatter(
            goles_df["x"],
            goles_df["y"],
            s=go
