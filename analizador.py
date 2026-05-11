#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════╗
║   OLEA NEUTRAL FI — ANALIZADOR DE RENTABILIDAD                  ║
║   Fondo Multiactivo Global | ISIN: ES0118537002                  ║
║   Histórico completo desde Enero 2004                            ║
╚══════════════════════════════════════════════════════════════════╝

INSTALACIÓN (ejecutar una sola vez en el terminal):

    pip install streamlit pandas numpy plotly

EJECUCIÓN:

    streamlit run analizador.py
"""

import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
from pandas.tseries.offsets import MonthEnd

# ─────────────────────────────────────────────────────────────────
# CONFIGURACIÓN DE PÁGINA (debe ser la PRIMERA llamada Streamlit)
# ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Olea Neutral FI | Analizador de Rentabilidad",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────
TASA_LIBRE_RIESGO = 0.02      # 2% anual para cálculo del Sharpe
OBJETIVO_TAE      = 0.05      # 5% TAE — objetivo declarado del fondo

# Paleta de colores
C_VERDE      = "#1B6B4A"  # verde Olea (acento principal)
C_VERDE_CLAR = "#2DBD7E"  # verde claro (valores positivos, línea fondo)
C_ROJO       = "#E84855"  # rojo (valores negativos, línea objetivo)
C_FONDO      = "#0d0d0d"
C_TARJETA    = "#161616"
C_BORDE      = "#242424"

NOMBRES_MES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
               "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

# ─────────────────────────────────────────────────────────────────
# CSS — TEMA OSCURO CON ACENTO VERDE OLEA
# ─────────────────────────────────────────────────────────────────
CSS = """
<style>
/* Fondo y texto base */
.stApp { background-color: #0d0d0d; color: #e0e0e0; }
.block-container { padding-top: 0.8rem; padding-bottom: 1rem; max-width: 1400px; }

/* Header */
.olea-header {
    background: linear-gradient(135deg, #071510 0%, #0a2018 100%);
    border: 1px solid #1B6B4A;
    border-radius: 8px;
    padding: 18px 30px 14px 30px;
    margin-bottom: 20px;
}
.olea-logo {
    color: #2DBD7E;
    font-size: 26px;
    font-weight: 800;
    font-family: 'Courier New', monospace;
    letter-spacing: 5px;
}
.olea-sub {
    color: #1B6B4A;
    font-size: 11px;
    font-family: 'Courier New', monospace;
    letter-spacing: 3px;
    margin-top: 5px;
}
.olea-isin {
    color: #444;
    font-size: 10px;
    font-family: 'Courier New', monospace;
    letter-spacing: 1px;
    margin-top: 3px;
}

/* Tarjetas de métricas ejecutivas */
.metric-card {
    background: linear-gradient(160deg, #0d1f16 0%, #111 100%);
    border: 1px solid #1B6B4A;
    border-radius: 8px;
    padding: 20px 18px;
    text-align: center;
    min-height: 110px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    margin-bottom: 4px;
}
.metric-label {
    color: #1B6B4A;
    font-size: 10px;
    font-family: 'Courier New', monospace;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 10px;
}
.metric-value {
    color: #e0e0e0;
    font-size: 30px;
    font-weight: 800;
    font-family: 'Courier New', monospace;
    line-height: 1.1;
}
.metric-pos { color: #2DBD7E; }
.metric-neg { color: #E84855; }
.metric-neu { color: #e0e0e0; }

/* Títulos de sección */
.sec-title {
    color: #2DBD7E;
    font-size: 12px;
    font-family: 'Courier New', monospace;
    letter-spacing: 3px;
    text-transform: uppercase;
    border-bottom: 1px solid #1B6B4A;
    padding-bottom: 8px;
    margin: 28px 0 16px 0;
}

/* Tabla mensual */
.tabla-wrap { overflow-x: auto; }
.tm {
    font-family: 'Courier New', monospace;
    font-size: 11.5px;
    width: 100%;
    border-collapse: collapse;
    white-space: nowrap;
}
.tm th {
    background-color: #0a2018;
    color: #2DBD7E;
    padding: 7px 9px;
    text-align: center;
    border: 1px solid #1B6B4A;
    font-size: 10px;
    letter-spacing: 1px;
    font-weight: 600;
}
.tm td {
    padding: 5px 9px;
    text-align: center;
    border: 1px solid #1a1a1a;
}
.tm .td-ano  { background:#0a1f14; color:#2DBD7E; font-weight:700;
               border:1px solid #1B6B4A; }
.tm .td-sep  { border-left: 2px solid #1B6B4A; }
.tm .td-vol  { color: #888; }
.tm .td-pos  { background: rgba(27,107,74,0.18); color: #2DBD7E; }
.tm .td-neg  { background: rgba(232,72,85,0.16); color: #E84855; }
.tm .td-null { color: #2a2a2a; }
.tm tbody tr:hover td { background-color: rgba(255,255,255,0.03); }

/* Tabla de períodos */
.tp {
    font-family: 'Courier New', monospace;
    font-size: 12px;
    width: 100%;
    border-collapse: collapse;
}
.tp th {
    background: #0a2018;
    color: #2DBD7E;
    padding: 8px 12px;
    text-align: center;
    border: 1px solid #1B6B4A;
    font-size: 10px;
    letter-spacing: 1.5px;
}
.tp td {
    padding: 7px 12px;
    text-align: center;
    border: 1px solid #1a1a1a;
    color: #ccc;
}
.tp .td-periodo { text-align: left; color: #2DBD7E; font-weight: 600; }
.tp tbody tr:nth-child(even) td { background: rgba(255,255,255,0.02); }
.tp tbody tr:hover td { background: rgba(27,107,74,0.08); }

/* Tabla drawdowns */
.tdd {
    font-family: 'Courier New', monospace;
    font-size: 12px;
    width: 100%;
    border-collapse: collapse;
}
.tdd th {
    background: #1a0a0c;
    color: #E84855;
    padding: 7px 10px;
    text-align: center;
    border: 1px solid #3a1a1e;
    font-size: 10px;
    letter-spacing: 1px;
}
.tdd td {
    padding: 6px 10px;
    text-align: center;
    border: 1px solid #1a1a1a;
    color: #ccc;
}
.tdd .td-n { color: #E84855; font-weight: 700; }
.tdd .td-dd { color: #E84855; font-weight: 700; }
.tdd .td-rec { color: #2DBD7E; }
.tdd tbody tr:nth-child(even) td { background: rgba(255,255,255,0.02); }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: #111;
    border-bottom: 1px solid #1B6B4A;
    gap: 0;
}
.stTabs [data-baseweb="tab"] {
    color: #555;
    font-family: 'Courier New', monospace;
    font-size: 11px;
    letter-spacing: 1.5px;
    padding: 8px 20px;
}
.stTabs [aria-selected="true"] {
    color: #2DBD7E !important;
    border-bottom: 2px solid #2DBD7E !important;
    background: transparent !important;
}

/* Responsive */
@media (max-width: 768px) {
    .metric-value { font-size: 22px; }
    .olea-logo { font-size: 18px; letter-spacing: 2px; }
    .tm { font-size: 10px; }
    .tm td, .tm th { padding: 4px 5px; }
}
</style>
"""

# ─────────────────────────────────────────────────────────────────
# DATOS — carga desde CSV con rentabilidades mensuales reales
# ─────────────────────────────────────────────────────────────────

# Rentabilidades mensuales reales (% sin dividir) — fuente: Olea Gestión
_DATOS_MENSUALES = [
    (2004,1,2.43),(2004,2,1.50),(2004,3,-2.42),(2004,4,1.20),(2004,5,-0.85),
    (2004,6,1.20),(2004,7,-1.50),(2004,8,-0.77),(2004,9,1.51),(2004,10,1.71),
    (2004,11,1.99),(2004,12,2.77),
    (2005,1,1.66),(2005,2,2.80),(2005,3,-0.66),(2005,4,-2.52),(2005,5,3.67),
    (2005,6,2.69),(2005,7,1.56),(2005,8,0.08),(2005,9,2.25),(2005,10,-0.91),
    (2005,11,3.55),(2005,12,2.53),
    (2006,1,2.35),(2006,2,1.96),(2006,3,2.11),(2006,4,0.26),(2006,5,-4.18),
    (2006,6,0.81),(2006,7,0.71),(2006,8,2.15),(2006,9,3.06),(2006,10,3.69),
    (2006,11,-0.17),(2006,12,3.12),
    (2007,1,1.80),(2007,2,-1.03),(2007,3,1.07),(2007,4,0.96),(2007,5,2.91),
    (2007,6,-1.26),(2007,7,-1.91),(2007,8,0.40),(2007,9,0.44),(2007,10,3.61),
    (2007,11,-2.84),(2007,12,-0.44),
    (2008,1,-4.24),(2008,2,-0.34),(2008,3,-1.62),(2008,4,2.80),(2008,5,1.52),
    (2008,6,-4.18),(2008,7,0.12),(2008,8,2.53),(2008,9,-9.47),(2008,10,-5.01),
    (2008,11,-1.23),(2008,12,-0.13),
    (2009,1,-2.42),(2009,2,-4.93),(2009,3,1.89),(2009,4,7.72),(2009,5,3.29),
    (2009,6,2.12),(2009,7,6.86),(2009,8,4.18),(2009,9,3.91),(2009,10,-0.63),
    (2009,11,0.28),(2009,12,4.43),
    (2010,1,-1.59),(2010,2,-0.16),(2010,3,4.32),(2010,4,0.20),(2010,5,-3.01),
    (2010,6,-1.17),(2010,7,3.03),(2010,8,-0.47),(2010,9,2.61),(2010,10,2.35),
    (2010,11,-1.49),(2010,12,2.64),
    (2011,1,0.53),(2011,2,1.61),(2011,3,-0.86),(2011,4,0.73),(2011,5,-0.83),
    (2011,6,-1.14),(2011,7,-1.86),(2011,8,-9.32),(2011,9,-6.50),(2011,10,5.90),
    (2011,11,-2.99),(2011,12,1.55),
    (2012,1,6.07),(2012,2,2.84),(2012,3,0.62),(2012,4,-2.72),(2012,5,-3.96),
    (2012,6,1.08),(2012,7,0.73),(2012,8,2.11),(2012,9,3.54),(2012,10,1.16),
    (2012,11,0.82),(2012,12,2.46),
    (2013,1,2.34),(2013,2,0.31),(2013,3,-0.03),(2013,4,1.71),(2013,5,1.00),
    (2013,6,-3.66),(2013,7,2.21),(2013,8,0.27),(2013,9,2.61),(2013,10,3.18),
    (2013,11,1.05),(2013,12,0.06),
    (2014,1,0.53),(2014,2,2.12),(2014,3,0.42),(2014,4,0.32),(2014,5,2.22),
    (2014,6,1.07),(2014,7,-0.16),(2014,8,1.00),(2014,9,0.26),(2014,10,-0.42),
    (2014,11,0.83),(2014,12,-0.57),
    (2015,1,3.58),(2015,2,3.15),(2015,3,0.96),(2015,4,0.39),(2015,5,0.59),
    (2015,6,-2.02),(2015,7,0.96),(2015,8,-3.29),(2015,9,-3.08),(2015,10,3.87),
    (2015,11,1.60),(2015,12,-2.24),
    (2016,1,-3.92),(2016,2,-2.70),(2016,3,2.40),(2016,4,1.53),(2016,5,0.38),
    (2016,6,-0.63),(2016,7,2.33),(2016,8,1.68),(2016,9,-0.37),(2016,10,1.23),
    (2016,11,1.00),(2016,12,2.28),
    (2017,1,0.09),(2017,2,2.36),(2017,3,0.76),(2017,4,0.08),(2017,5,0.18),
    (2017,6,-0.42),(2017,7,0.19),(2017,8,-0.36),(2017,9,1.59),(2017,10,1.46),
    (2017,11,-0.67),(2017,12,-0.06),
    (2018,1,0.84),(2018,2,-1.11),(2018,3,-1.72),(2018,4,1.76),(2018,5,0.25),
    (2018,6,-1.24),(2018,7,1.70),(2018,8,-1.22),(2018,9,0.30),(2018,10,-2.10),
    (2018,11,-0.91),(2018,12,-3.69),
    (2019,1,4.84),(2019,2,1.59),(2019,3,0.42),(2019,4,1.79),(2019,5,-2.45),
    (2019,6,2.57),(2019,7,0.97),(2019,8,-1.27),(2019,9,2.83),(2019,10,1.63),
    (2019,11,0.80),(2019,12,1.01),
    (2020,1,-0.35),(2020,2,-2.98),(2020,3,-8.63),(2020,4,3.66),(2020,5,1.07),
    (2020,6,0.10),(2020,7,-1.37),(2020,8,-0.13),(2020,9,-0.82),(2020,10,-0.64),
    (2020,11,5.44),(2020,12,1.89),
    (2021,1,-0.46),(2021,2,1.57),(2021,3,4.02),(2021,4,0.40),(2021,5,1.76),
    (2021,6,0.65),(2021,7,0.15),(2021,8,1.61),(2021,9,0.09),(2021,10,1.32),
    (2021,11,-1.32),(2021,12,1.40),
    (2022,1,-0.18),(2022,2,-3.80),(2022,3,0.52),(2022,4,-0.24),(2022,5,0.74),
    (2022,6,-4.80),(2022,7,3.40),(2022,8,-0.99),(2022,9,-4.63),(2022,10,2.44),
    (2022,11,3.34),(2022,12,-2.58),
    (2023,1,3.35),(2023,2,0.13),(2023,3,-1.11),(2023,4,0.65),(2023,5,0.85),
    (2023,6,0.17),(2023,7,1.82),(2023,8,-0.35),(2023,9,-0.58),(2023,10,-0.68),
    (2023,11,2.45),(2023,12,1.41),
    (2024,1,1.00),(2024,2,0.07),(2024,3,1.94),(2024,4,-0.58),(2024,5,1.61),
    (2024,6,0.28),(2024,7,1.79),(2024,8,0.36),(2024,9,0.97),(2024,10,-0.60),
    (2024,11,1.16),(2024,12,-0.46),
    (2025,1,1.81),(2025,2,1.86),(2025,3,-1.06),(2025,4,0.26),(2025,5,0.71),
    (2025,6,0.00),(2025,7,0.55),(2025,8,0.75),(2025,9,0.90),(2025,10,0.91),
    (2025,11,0.78),(2025,12,-0.10),
    (2026,1,0.70),(2026,2,0.97),(2026,3,-2.37),(2026,4,1.70),
]


def _nav_desde_lista(datos):
    fechas = [pd.Timestamp(2003, 12, 31)]
    navs   = [100.0]
    nav_val = 100.0
    for ano, mes, pct in datos:
        r = pct / 100.0
        fecha = pd.Timestamp(ano, mes, 1) + MonthEnd(0)
        nav_val *= (1.0 + r)
        fechas.append(fecha)
        navs.append(nav_val)
    nav = pd.Series(navs, index=pd.DatetimeIndex(fechas), name="NAV")
    return nav


@st.cache_data(show_spinner=False)
def cargar_datos():
    nav = _nav_desde_lista(_DATOS_MENSUALES)
    ret = nav.pct_change().dropna()
    return nav, ret


# ─────────────────────────────────────────────────────────────────
# CÁLCULOS
# ─────────────────────────────────────────────────────────────────

def calcular_metricas(nav_serie):
    """
    Devuelve dict con métricas clave para la serie dada.
    Todos los retornos son decimales (no porcentaje).
    """
    ret = nav_serie.pct_change().dropna()
    n_m = len(ret)
    n_a = n_m / 12.0

    ret_acum = nav_serie.iloc[-1] / nav_serie.iloc[0] - 1.0
    tae = (1.0 + ret_acum) ** (1.0 / n_a) - 1.0 if n_a > 0 else np.nan

    vol_anual = ret.std() * np.sqrt(12)
    sharpe = (tae - TASA_LIBRE_RIESGO) / vol_anual if vol_anual > 0 else np.nan

    peak = nav_serie.cummax()
    dd = (nav_serie - peak) / peak
    max_dd = dd.min()

    pct_pos = (ret > 0).sum() / len(ret) * 100.0

    return {
        "ret_acum": ret_acum,
        "tae":      tae,
        "vol_anual":vol_anual,
        "sharpe":   sharpe,
        "max_dd":   max_dd,
        "pct_pos":  pct_pos,
        "mejor_mes":ret.max(),
        "peor_mes": ret.min(),
        "n_meses":  n_m,
    }


def calcular_tabla_mensual(nav, ret):
    """
    DataFrame con rentabilidades mensuales.
    Columnas: Ene…Dic | Total | Vol | Sharpe
    Valores: retornos como decimales (se formatean en el render).
    """
    anos = sorted(ret.index.year.unique())
    filas = []

    for ano in anos:
        ret_a = ret[ret.index.year == ano]
        fila = {"Año": ano}

        for m_idx, m_nombre in enumerate(NOMBRES_MES, start=1):
            r = ret_a[ret_a.index.month == m_idx]
            fila[m_nombre] = r.iloc[0] if len(r) > 0 else np.nan

        n_m = len(ret_a)
        if n_m >= 1:
            total = (1.0 + ret_a).prod() - 1.0
            fila["Total"] = total
        else:
            fila["Total"] = np.nan
            n_m = 0

        if n_m >= 2:
            vol_anual = ret_a.std() * np.sqrt(12)
            fila["Vol"] = vol_anual
            # Sharpe con retorno anualizado para comparabilidad entre años
            ann_ret = (1.0 + fila["Total"]) ** (12.0 / n_m) - 1.0
            fila["Sharpe"] = (ann_ret - TASA_LIBRE_RIESGO) / vol_anual if vol_anual > 0 else np.nan
        else:
            fila["Vol"] = np.nan
            fila["Sharpe"] = np.nan

        filas.append(fila)

    return pd.DataFrame(filas).set_index("Año")


def calcular_drawdowns(nav_serie, top_n=6):
    """
    Identifica y devuelve los top_n peores períodos de drawdown.
    Retorna lista de dicts ordenada de mayor a menor caída.
    """
    running_max = nav_serie.cummax()
    dd = (nav_serie - running_max) / running_max

    in_dd = (dd < -0.001).values
    n = len(nav_serie)
    periodos = []  # lista de (s, e) índices enteros del período en drawdown

    i = 0
    while i < n:
        if in_dd[i]:
            s = i
            while i < n and in_dd[i]:
                i += 1
            periodos.append((s, i - 1))
        else:
            i += 1

    resultados = []
    for s, e in periodos:
        # Pico: buscar hacia atrás el último punto donde DD ≈ 0
        pico_i = s
        while pico_i > 0 and dd.iloc[pico_i - 1] < -0.0005:
            pico_i -= 1

        fecha_pico = nav_serie.index[pico_i]
        nav_pico_val = nav_serie.iloc[pico_i]

        # Trough (mínimo del drawdown)
        seg_dd = dd.iloc[pico_i: e + 1]
        fecha_min = seg_dd.idxmin()
        trough_i = nav_serie.index.get_loc(fecha_min)
        profundidad = dd[fecha_min]

        duracion = e - pico_i  # meses desde pico hasta fin del drawdown

        # Tiempo de recuperación desde el trough hasta superar el pico
        recuperacion_meses = None
        for k in range(e + 1, n):
            if nav_serie.iloc[k] >= nav_pico_val:
                recuperacion_meses = k - trough_i
                break

        resultados.append({
            "Pico":                fecha_pico,
            "Mínimo":              fecha_min,
            "Profundidad":         profundidad,
            "Duración (meses)":    duracion,
            "Recuperación (meses)":recuperacion_meses,
        })

    return sorted(resultados, key=lambda x: x["Profundidad"])[:top_n]


def serie_objetivo(nav_serie):
    """Serie de VL creciendo al 5% TAE desde el punto de inicio de nav_serie."""
    crec_m = (1.0 + OBJETIVO_TAE) ** (1.0 / 12.0) - 1.0
    base = nav_serie.iloc[0]
    vals = [base * (1.0 + crec_m) ** i for i in range(len(nav_serie))]
    return pd.Series(vals, index=nav_serie.index)


def metricas_por_periodo(nav, ret):
    """
    Calcula métricas para 4 períodos estándar.
    Devuelve lista de dicts lista para renderizar como tabla HTML.
    """
    hoy = nav.index[-1]
    periodos = {
        "Desde inicio":       nav.index[0],
        "Últimos 10 años":    hoy - pd.DateOffset(years=10),
        "Últimos 5 años":     hoy - pd.DateOffset(years=5),
        "Últimos 3 años":     hoy - pd.DateOffset(years=3),
    }

    filas = []
    for nombre, fecha_ini in periodos.items():
        nav_p = nav[nav.index >= fecha_ini]
        if len(nav_p) < 4:
            continue
        m = calcular_metricas(nav_p)
        filas.append({
            "Período":         nombre,
            "Rent. Acum.":     m["ret_acum"],
            "TAE":             m["tae"],
            "Vol. Anual":      m["vol_anual"],
            "Sharpe":          m["sharpe"],
            "% Meses +":       m["pct_pos"],
            "Mejor Mes":       m["mejor_mes"],
            "Peor Mes":        m["peor_mes"],
            "Máx. Drawdown":   m["max_dd"],
        })
    return filas


# ─────────────────────────────────────────────────────────────────
# GRÁFICOS (Plotly — tema oscuro uniforme)
# ─────────────────────────────────────────────────────────────────

_LAYOUT_BASE = dict(
    paper_bgcolor=C_FONDO,
    plot_bgcolor="#111111",
    font=dict(family="Courier New, monospace", color="#e0e0e0", size=11),
    margin=dict(l=50, r=20, t=45, b=40),
    hovermode="x unified",
    legend=dict(
        bgcolor="#161616",
        bordercolor=C_VERDE,
        borderwidth=1,
        font=dict(size=10),
    ),
    xaxis=dict(gridcolor="#1c1c1c", linecolor=C_BORDE, tickfont=dict(size=10)),
    yaxis=dict(gridcolor="#1c1c1c", linecolor=C_BORDE, tickfont=dict(size=10)),
)


def fig_evolucion(nav, titulo, fecha_inicio=None):
    """Evolución del VL vs objetivo 5% TAE (base 100 desde fecha_inicio)."""
    nav_p = nav[nav.index >= fecha_inicio].copy() if fecha_inicio else nav.copy()
    nav_p = nav_p / nav_p.iloc[0] * 100.0
    obj_p = serie_objetivo(nav_p)

    fig = go.Figure()

    # Área bajo la curva del fondo
    fig.add_trace(go.Scatter(
        x=nav_p.index, y=nav_p.values,
        name="Olea Neutral FI",
        line=dict(color=C_VERDE_CLAR, width=2.5),
        fill="tozeroy",
        fillcolor="rgba(27,107,74,0.07)",
        hovertemplate="<b>Olea:</b> %{y:.1f}<extra></extra>",
    ))

    # Línea objetivo punteada
    fig.add_trace(go.Scatter(
        x=obj_p.index, y=obj_p.values,
        name="Objetivo 5% TAE",
        line=dict(color=C_ROJO, width=1.5, dash="dot"),
        hovertemplate="<b>Objetivo:</b> %{y:.1f}<extra></extra>",
    ))

    fig.update_layout(
        **_LAYOUT_BASE,
        title=dict(text=titulo, font=dict(color=C_VERDE_CLAR, size=13), x=0.01),
        yaxis_title="VL (base 100)",
        height=420,
    )
    return fig


def fig_drawdown(nav):
    """Gráfico de área del drawdown histórico."""
    peak = nav.cummax()
    dd = (nav - peak) / peak * 100.0

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dd.index, y=dd.values,
        name="Drawdown",
        fill="tozeroy",
        fillcolor="rgba(232,72,85,0.12)",
        line=dict(color=C_ROJO, width=1.5),
        hovertemplate="<b>DD:</b> %{y:.2f}%<extra></extra>",
    ))
    # Línea en 0
    fig.add_hline(y=0, line_color="#333", line_width=1)

    fig.update_layout(
        **_LAYOUT_BASE,
        title=dict(text="Drawdown Histórico desde Inicio", font=dict(color=C_VERDE_CLAR, size=13), x=0.01),
        yaxis_title="Drawdown (%)",
        yaxis_tickformat=".1f",
        yaxis_ticksuffix="%",
        yaxis_gridcolor="#1c1c1c",
        height=340,
    )
    return fig


def fig_barras_objetivo(ret):
    """Barras anuales verdes/rojas vs línea del 5% TAE."""
    datos_ano = {}
    for ano in sorted(ret.index.year.unique()):
        r = ret[ret.index.year == ano]
        if len(r) > 0:
            datos_ano[ano] = (1.0 + r).prod() - 1.0

    anos = list(datos_ano.keys())
    vals = [datos_ano[a] * 100 for a in anos]
    colores = [C_VERDE_CLAR if v >= OBJETIVO_TAE * 100 else C_ROJO for v in vals]
    textos = [f"{v:+.2f}%" for v in vals]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=anos,
        y=vals,
        marker_color=colores,
        text=textos,
        textposition="outside",
        textfont=dict(size=9, family="Courier New, monospace"),
        hovertemplate="<b>%{x}</b><br>Rentabilidad: %{y:.2f}%<extra></extra>",
        showlegend=False,
    ))

    # Línea objetivo horizontal
    fig.add_hline(
        y=OBJETIVO_TAE * 100,
        line_dash="dot",
        line_color=C_ROJO,
        line_width=1.8,
        annotation_text="  Objetivo 5% TAE",
        annotation_position="top right",
        annotation_font=dict(color=C_ROJO, size=10, family="Courier New, monospace"),
    )

    fig.update_layout(
        **_LAYOUT_BASE,
        title=dict(text="Rentabilidad Anual vs Objetivo 5% TAE", font=dict(color=C_VERDE_CLAR, size=13), x=0.01),
        yaxis_title="Rentabilidad (%)",
        yaxis_tickformat=".0f",
        yaxis_ticksuffix="%",
        yaxis_gridcolor="#1c1c1c",
        bargap=0.2,
        height=420,
        showlegend=False,
        uniformtext=dict(mode="hide", minsize=7),
    )
    return fig


# ─────────────────────────────────────────────────────────────────
# RENDERIZADO HTML — secciones que requieren HTML personalizado
# ─────────────────────────────────────────────────────────────────

def _fmt_pct(v, decimals=2, sign=True):
    """Formatea un decimal como porcentaje."""
    if pd.isna(v):
        return "—"
    fmt = f"{{:+.{decimals}f}}%" if sign else f"{{:.{decimals}f}}%"
    return fmt.format(v * 100)

def _fmt_sharpe(v):
    if pd.isna(v):
        return "—"
    return f"{v:+.2f}"

def _clase_celda(v):
    if pd.isna(v):
        return "td-null"
    return "td-pos" if v >= 0 else "td-neg"


def html_tarjeta(label, valor_str, clase_color="metric-neu"):
    return f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value {clase_color}">{valor_str}</div>
    </div>"""


def html_tabla_mensual(df):
    """Tabla mensual verde/rojo con columnas Año | Ene…Dic | Total | Vol | Sharpe."""
    h = '<div class="tabla-wrap"><table class="tm"><thead><tr>'
    h += '<th>Año</th>'
    for m in NOMBRES_MES:
        h += f'<th>{m}</th>'
    h += '<th class="td-sep">Total</th><th>Vol</th><th>Sharpe</th>'
    h += '</tr></thead><tbody>'

    for ano, fila in df.iterrows():
        h += f'<tr><td class="td-ano">{ano}</td>'
        for m in NOMBRES_MES:
            v = fila.get(m, np.nan)
            if pd.isna(v):
                h += '<td class="td-null">—</td>'
            else:
                cls = _clase_celda(v)
                h += f'<td class="{cls}">{_fmt_pct(v)}</td>'

        # Total año
        t = fila.get("Total", np.nan)
        cls_t = _clase_celda(t)
        h += f'<td class="td-sep {cls_t}" style="font-weight:700">{_fmt_pct(t)}</td>'

        # Volatilidad
        vol = fila.get("Vol", np.nan)
        h += f'<td class="td-vol">{_fmt_pct(vol, sign=False) if not pd.isna(vol) else "—"}</td>'

        # Sharpe
        sh = fila.get("Sharpe", np.nan)
        cls_sh = _clase_celda(sh)
        h += f'<td class="{cls_sh}">{_fmt_sharpe(sh)}</td>'

        h += '</tr>'

    h += '</tbody></table></div>'
    return h


def html_tabla_periodos(filas):
    """Tabla comparativa de métricas por período."""
    cabeceras = ["Período", "Rent. Acum.", "TAE", "Vol. Anual",
                 "Sharpe", "% Meses +", "Mejor Mes", "Peor Mes", "Máx. Drawdown"]
    h = '<table class="tp"><thead><tr>'
    for c in cabeceras:
        h += f'<th>{c}</th>'
    h += '</tr></thead><tbody>'

    for f in filas:
        h += '<tr>'
        h += f'<td class="td-periodo">{f["Período"]}</td>'
        for key in ["Rent. Acum.", "TAE"]:
            v = f[key]
            cls = _clase_celda(v)
            h += f'<td class="{cls}">{_fmt_pct(v)}</td>'
        h += f'<td class="td-vol">{_fmt_pct(f["Vol. Anual"], sign=False)}</td>'

        sh = f["Sharpe"]
        cls_sh = _clase_celda(sh)
        h += f'<td class="{cls_sh}">{_fmt_sharpe(sh)}</td>'

        h += f'<td style="color:#aaa">{f["% Meses +"]:.0f}%</td>'

        h += f'<td class="td-pos">{_fmt_pct(f["Mejor Mes"])}</td>'
        h += f'<td class="td-neg">{_fmt_pct(f["Peor Mes"])}</td>'

        dd = f["Máx. Drawdown"]
        h += f'<td class="td-neg">{_fmt_pct(dd)}</td>'
        h += '</tr>'

    h += '</tbody></table>'
    return h


def html_tabla_drawdowns(drawdowns):
    """Tabla de los peores drawdowns."""
    h = '<table class="tdd"><thead><tr>'
    for col in ["#", "Pico (inicio)", "Mínimo (trough)", "Profundidad",
                "Duración", "Recuperación"]:
        h += f'<th>{col}</th>'
    h += '</tr></thead><tbody>'

    for i, d in enumerate(drawdowns, 1):
        pico_str = d["Pico"].strftime("%b %Y") if hasattr(d["Pico"], "strftime") else str(d["Pico"])
        min_str  = d["Mínimo"].strftime("%b %Y") if hasattr(d["Mínimo"], "strftime") else str(d["Mínimo"])
        prof_str = f'{d["Profundidad"]*100:.1f}%'
        dur_str  = f'{d["Duración (meses)"]} meses'
        rec = d["Recuperación (meses)"]
        rec_str  = f'{rec} meses' if rec else '<span style="color:#E84855">En curso</span>'

        h += f'''<tr>
            <td class="td-n">{i}</td>
            <td>{pico_str}</td>
            <td>{min_str}</td>
            <td class="td-dd">{prof_str}</td>
            <td style="color:#aaa">{dur_str}</td>
            <td class="td-rec">{rec_str}</td>
        </tr>'''

    h += '</tbody></table>'
    return h


# ─────────────────────────────────────────────────────────────────
# APLICACIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────────

def main():
    st.markdown(CSS, unsafe_allow_html=True)

    # ── Header ───────────────────────────────────────────────────
    st.markdown("""
    <div class="olea-header">
        <div class="olea-logo">◆ OLEA NEUTRAL FI</div>
        <div class="olea-sub">ANÁLISIS DE RENTABILIDAD · DESDE ENERO 2004</div>
        <div class="olea-isin">ISIN: ES0118537002 &nbsp;·&nbsp; Fondo Multiactivo Global &nbsp;·&nbsp;
        Objetivo: 5% TAE &nbsp;·&nbsp; Volatilidad objetivo: 5–9%</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Carga de datos ────────────────────────────────────────────
    with st.spinner("Cargando datos históricos del fondo…"):
        nav, ret = cargar_datos()

    st.info(
        "**Datos reales** — fuente: informes oficiales Olea Gestión.",
        icon="📊"
    )

    mg = calcular_metricas(nav)

    # ═══════════════════════════════════════════════════════════════
    # 01 · RESUMEN EJECUTIVO
    # ═══════════════════════════════════════════════════════════════
    st.markdown('<div class="sec-title">01 · Resumen Ejecutivo</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)

    def _clase(v, umbral=0):
        return "metric-pos" if v > umbral else "metric-neg"

    with c1:
        st.markdown(html_tarjeta(
            "Rentabilidad Acumulada",
            f"{mg['ret_acum']*100:+.1f}%",
            _clase(mg["ret_acum"]),
        ), unsafe_allow_html=True)
    with c2:
        st.markdown(html_tarjeta(
            "TAE Desde Inicio",
            f"{mg['tae']*100:.2f}%",
            _clase(mg["tae"] - OBJETIVO_TAE),  # verde si supera el objetivo
        ), unsafe_allow_html=True)
    with c3:
        st.markdown(html_tarjeta(
            "Volatilidad Anualizada",
            f"{mg['vol_anual']*100:.1f}%",
            "metric-neu",
        ), unsafe_allow_html=True)
    with c4:
        st.markdown(html_tarjeta(
            "Ratio Sharpe (rf = 2%)",
            f"{mg['sharpe']:.2f}",
            _clase(mg["sharpe"]),
        ), unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # 02 · TABLA MENSUAL
    # ═══════════════════════════════════════════════════════════════
    st.markdown('<div class="sec-title">02 · Rentabilidades Mensuales</div>', unsafe_allow_html=True)

    df_tabla = calcular_tabla_mensual(nav, ret)
    st.markdown(html_tabla_mensual(df_tabla), unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # 03 · EVOLUCIÓN DEL VALOR LIQUIDATIVO
    # ═══════════════════════════════════════════════════════════════
    st.markdown('<div class="sec-title">03 · Evolución del Valor Liquidativo</div>', unsafe_allow_html=True)

    hoy = nav.index[-1]
    tab1, tab2, tab3 = st.tabs([
        "  Desde Inicio (2004)  ",
        "  Últimos 10 Años  ",
        "  Últimos 3 Años  ",
    ])

    with tab1:
        st.plotly_chart(
            fig_evolucion(nav, "Olea Neutral FI vs Objetivo 5% TAE — Histórico completo"),
            use_container_width=True,
        )
    with tab2:
        st.plotly_chart(
            fig_evolucion(nav, "Olea Neutral FI vs Objetivo 5% TAE — Últimos 10 años",
                          hoy - pd.DateOffset(years=10)),
            use_container_width=True,
        )
    with tab3:
        st.plotly_chart(
            fig_evolucion(nav, "Olea Neutral FI vs Objetivo 5% TAE — Últimos 3 años",
                          hoy - pd.DateOffset(years=3)),
            use_container_width=True,
        )

    # ═══════════════════════════════════════════════════════════════
    # 04 · MÉTRICAS DE RIESGO POR PERÍODO
    # ═══════════════════════════════════════════════════════════════
    st.markdown('<div class="sec-title">04 · Métricas de Riesgo por Período</div>', unsafe_allow_html=True)

    filas_p = metricas_por_periodo(nav, ret)
    st.markdown(html_tabla_periodos(filas_p), unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # 05 · ANÁLISIS DE DRAWDOWN
    # ═══════════════════════════════════════════════════════════════
    st.markdown('<div class="sec-title">05 · Análisis de Drawdown</div>', unsafe_allow_html=True)

    st.plotly_chart(fig_drawdown(nav), use_container_width=True)

    st.markdown("**Los 6 peores períodos de drawdown:**", unsafe_allow_html=False)
    drawdowns = calcular_drawdowns(nav, top_n=6)
    if drawdowns:
        st.markdown(html_tabla_drawdowns(drawdowns), unsafe_allow_html=True)
    else:
        st.info("No se detectaron períodos de drawdown significativos.")

    # ═══════════════════════════════════════════════════════════════
    # 06 · COMPARATIVA CON OBJETIVO 5% TAE
    # ═══════════════════════════════════════════════════════════════
    st.markdown('<div class="sec-title">06 · Comparativa Anual vs Objetivo 5% TAE</div>', unsafe_allow_html=True)

    st.plotly_chart(fig_barras_objetivo(ret), use_container_width=True)

    # Mini-resumen estadístico del cumplimiento del objetivo
    anos_completos = {
        ano: (1.0 + ret[ret.index.year == ano]).prod() - 1.0
        for ano in ret.index.year.unique()
        if len(ret[ret.index.year == ano]) == 12
    }
    n_total = len(anos_completos)
    n_cumple = sum(1 for v in anos_completos.values() if v >= OBJETIVO_TAE)
    tae_hist = mg["tae"]

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric(
            "Años completos cumpliendo ≥ 5%",
            f"{n_cumple} de {n_total}",
            help="Solo años con 12 meses de datos (excluye 2026 parcial).",
        )
    with col_b:
        st.metric(
            "% Años sobre objetivo",
            f"{n_cumple/n_total*100:.0f}%",
        )
    with col_c:
        exceso = tae_hist - OBJETIVO_TAE
        delta_str = f"+{exceso*100:.2f}% sobre objetivo" if exceso >= 0 else f"{exceso*100:.2f}% bajo objetivo"
        st.metric(
            "TAE histórica vs objetivo 5%",
            f"{tae_hist*100:.2f}%",
            delta=delta_str,
        )

    # ── Footer ────────────────────────────────────────────────────
    st.markdown("---")
    n_m = mg["n_meses"]
    st.markdown(
        f'<div style="color:#333;font-family:\'Courier New\',monospace;font-size:10px;text-align:center">'
        f'Olea Gestión &nbsp;·&nbsp; Datos reales — fuente: informes oficiales Olea Gestión'
        f' &nbsp;·&nbsp; {n_m} meses de historia '
        f'({nav.index[0].strftime("%b %Y")} – {nav.index[-1].strftime("%b %Y")}) '
        f'&nbsp;·&nbsp; Actualizado {datetime.now().strftime("%d/%m/%Y %H:%M")}'
        f'</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
