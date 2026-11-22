import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from mplsoccer import VerticalPitch

st.set_page_config(page_title="Dashboard de Fútbol", layout="wide")
st.title("⚽ Dashboard de Tiros - Mundial 2022")

df = pd.read_csv("tiros.csv")

equipo = st.sidebar.selectbox("Equipo", sorted(df["team"].unique()))
d = df[df["team"] == equipo]

jugadores = ["Todos"] + sorted(d["player"].unique())
jugador = st.sidebar.selectbox("Jugador", jugadores)
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
