import numpy as np
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from mplsoccer import VerticalPitch, Radar

st.set_page_config(page_title="Dashboard de Fútbol", layout="wide")
st.title("⚽ Dashboard de Tiros - Mundial 2022")

df = pd.read_csv("tiros.csv")
df["distancia"] = np.sqrt((120 - df["x"]) ** 2 + (40 - df["y"]) ** 2)

tab1, tab2 = st.tabs(["🗺️ Mapa de tiros", "🕸️ Comparar jugadores"])

# ---------------- PESTAÑA 1: MAPA ----------------
with tab1:
    equipo = st.selectbox("Equipo", sorted(df["team"].unique()))
    d = df[df["team"] == equipo]

    jugadores = ["Todos"] + sorted(d["player"].unique())
    jugador = st.selectbox("Jugador", jugadores)
    if jugador != "Todos":
        d = d[d["player"] == jugador]

    c1, c2, c3 = st.columns(3)
    c1.metric("Tiros", len(d))
    c2.metric("Goles", int(d["gol"].sum()))
    c3.metric("xG total", round(d["xg_propio"].sum(), 2))

    pitch = VerticalPitch(pitch_type="statsbomb", half=True,
                          pitch_color="#0b0f1a", line_color="white")
    fig, ax = pitch.draw(figsize=(7, 6))
    fig.patch.set_facecolor("#0b0f1a")
    g = d[d["gol"] == 1]
    o = d[d["gol"] == 0]
    pitch.scatter(o.x, o.y, s=o.xg_propio * 800 + 30, c="gray", alpha=0.6, ax=ax)
    pitch.scatter(g.x, g.y, s=g.xg_propio * 800 + 30, c="#ff6b2c",
                  edgecolors="white", ax=ax)
    st.pyplot(fig)

    st.subheader("Tiros más peligrosos")
    st.dataframe(d.sort_values("xg_propio", ascending=False).head(10))

# ---------------- PESTAÑA 2: RADAR ----------------
with tab2:
    st.write("Compara dos jugadores (solo aparecen quienes tienen 8 tiros o más).")

    res = df.groupby("player").agg(
        tiros=("gol", "count"),
        goles=("gol", "sum"),
        xg_total=("xg_propio", "sum"),
        xg_por_tiro=("xg_propio", "mean"),
        distancia=("distancia", "mean"),
    )
    res = res[res["tiros"] >= 8]
    nombres = sorted(res.index.tolist())

    col_a, col_b = st.columns(2)
    j1 = col_a.selectbox("Jugador 1", nombres, index=0)
    j2 = col_b.selectbox("Jugador 2", nombres, index=1)

    params = ["tiros", "goles", "xg_total", "xg_por_tiro", "distancia"]
    low = res[params].min().tolist()
    high = res[params].max().tolist()

    radar = Radar(params, low, high)
    fig2, ax2 = radar.setup_axis()
    fig2.patch.set_facecolor("#0b0f1a")
    radar.draw_circles(ax=ax2, facecolor="#1a1f2e", edgecolor="#444444")
    radar.draw_radar_compare(
        res.loc[j1, params].tolist(), res.loc[j2, params].tolist(), ax=ax2,
        kwargs_radar={"facecolor": "#ff6b2c", "alpha": 0.6},
        kwargs_compare={"facecolor": "#2cc4ff", "alpha": 0.6},
    )
    radar.draw_range_labels(ax=ax2, fontsize=10, color="white")
    radar.draw_param_labels(ax=ax2, fontsize=12, color="white")
    st.pyplot(fig2)
    st.caption(f"🟠 {j1}   |   🔵 {j2}")
