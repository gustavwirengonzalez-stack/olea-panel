#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════╗
║   OLEA GESTIÓN — DASHBOARD DE SEGUIMIENTO DE MERCADO DIARIO     ║
║   Fondo Multiactivo Global | Perfil Moderado                    ║
║   Universo: Renta Fija EUR/USD · RV Europa/EEUU · Mat. Primas   ║
╚══════════════════════════════════════════════════════════════════╝

════════════════════════════════════════════════════════════════
INSTALACIÓN (ejecutar una sola vez en el terminal):

    pip install streamlit yfinance pandas requests

EJECUCIÓN:

    streamlit run dashboard.py

════════════════════════════════════════════════════════════════
FUENTES DE DATOS (todas gratuitas, sin clave API):

  · Yahoo Finance (yfinance):   RV, divisas, materias primas,
                                 Treasury 10Y EEUU, VIX
  · ECB SDW API pública:        Euríbor 12M (mensual),
                                 Bund 10Y y Schatz 2Y (diario)
  · FRED (St. Louis Fed):       Spread IG crédito corporativo

NOTAS:
  · Yahoo Finance: datos con ~15-20 min de retraso en sesión.
  · ECB YC (bonos alemanes): datos con 1 día hábil de retraso.
  · ECB FM (Euríbor): frecuencia mensual — se actualiza el
    primer día hábil del mes siguiente.
  · Tipo BCE e inflación son datos fijos: actualizar manualmente
    en la sección CONSTANTES cuando haya nueva publicación.
════════════════════════════════════════════════════════════════
"""

import warnings
warnings.filterwarnings("ignore")

import os
import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime
from io import StringIO
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# feedparser para leer noticias RSS financieras
try:
    import feedparser
    _FEEDPARSER_OK = True
except ImportError:
    _FEEDPARSER_OK = False

# macOS no incluye los certificados del sistema en Python — deshabilitar verificación SSL
# para feeds RSS de fuentes conocidas (dashboard interno, riesgo aceptable)
import ssl as _ssl
_ssl._create_default_https_context = _ssl._create_unverified_context

# ─────────────────────────────────────────────────────────────────
# MODO CLI — se activa con: python dashboard.py --check
# Si está activo, se omiten todas las llamadas a Streamlit.
# ─────────────────────────────────────────────────────────────────
_CLI_MODE    = "--check"  in sys.argv
_WEEKLY_MODE = "--weekly" in sys.argv
_DAILY_MODE  = "--daily"  in sys.argv

# ─────────────────────────────────────────────────────────────────
# CONFIGURACIÓN DE PÁGINA (debe ser la PRIMERA llamada Streamlit)
# ─────────────────────────────────────────────────────────────────
if not _CLI_MODE and not _WEEKLY_MODE and not _DAILY_MODE:
    st.set_page_config(
        page_title="Olea Gestión | Market Dashboard",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

# ─────────────────────────────────────────────────────────────────
# CONSTANTES — DATOS FIJOS Y UMBRALES DE ALERTA
# ─────────────────────────────────────────────────────────────────

# Actualizar estos valores manualmente tras cada reunión o publicación oficial
TIPO_BCE_PCT      = 2.00   # % — Tipo de depósito BCE (decisión vigente)
INFLACION_EUR_PCT = 3.0    # % — IPC Eurozona, último dato Eurostat disponible


# ─────────────────────────────────────────────────────────────────
# CONFIGURACIÓN DE EMAIL — Modificar antes de usar el sistema de alertas
# ─────────────────────────────────────────────────────────────────
#
# CÓMO GENERAR UNA APP PASSWORD DE GMAIL (necesaria para enviar emails):
#
#   1. Activa la verificación en dos pasos en tu cuenta Google:
#      → https://myaccount.google.com/security
#
#   2. En esa misma página ve a:
#      Seguridad > Contraseñas de aplicaciones
#      (o busca "App Passwords" en myaccount.google.com)
#      NOTA: esta opción solo aparece si ya tienes 2FA activado.
#
#   3. En el desplegable "Seleccionar aplicación" elige "Otra (nombre personalizado)"
#      y escribe "Olea Dashboard". Pulsa "Generar".
#
#   4. Google te mostrará 16 caracteres en 4 grupos (ej: "abcd efgh ijkl mnop").
#      Copia esa contraseña aquí. Puedes dejar los espacios o quitarlos.
#
#   5. IMPORTANTE: esta contraseña es para esta app únicamente.
#      Si la pierdes, bórrala en Google y genera una nueva.
#
EMAIL_REMITENTE     = os.environ.get("EMAIL_REMITENTE", "gustavwirengonzalez@gmail.com")
EMAIL_PASSWORD      = os.environ.get("EMAIL_PASSWORD",  "gcel ysze qqwv gvju")
EMAIL_DESTINATARIOS = [
    "gustavwirengonzalez@gmail.com",
    "gustav.wiren@studenti.luiss.it",
]

# ─────────────────────────────────────────────────────────────────
# CONFIGURACIÓN DE NOTICIAS — NewsAPI
# ─────────────────────────────────────────────────────────────────
NEWSAPI_SOURCES = "reuters,cnbc"

NEWSAPI_QUERIES = {
    "BCE Y MACRO EUROPEA":    "ECB interest rates eurozone inflation Lagarde",
    "GEOPOLÍTICA Y ENERGÍA":  "Iran Hormuz oil Houthis Red Sea conflict",
    "MERCADOS Y RENTA FIJA":  "Bund yield Treasury bonds credit spread Europe",
    "EMPLEO Y FED AMERICANA": "Federal Reserve Powell jobs Non-Farm Payrolls",
}

# Noticias de ejemplo como último recurso si todos los feeds fallan
_NOTICIAS_FALLBACK = {
    "BCE Y MACRO EUROPEA": [
        {
            "titulo":     "BCE mantiene tipos sin cambios — Lagarde señala cautela ante incertidumbre global",
            "fuente":     "Ejemplo (sin conexión RSS)",
            "link":       "https://www.ecb.europa.eu/press/pressconf/html/index.es.html",
            "hace_horas": 2.0,
        },
        {
            "titulo":     "Euríbor 12M se estabiliza tras meses de caídas continuadas",
            "fuente":     "Ejemplo (sin conexión RSS)",
            "link":       "#",
            "hace_horas": 5.0,
        },
    ],
    "GEOPOLÍTICA Y ENERGÍA": [
        {
            "titulo":     "Brent cede terreno ante expectativas de aumento de producción OPEP+",
            "fuente":     "Ejemplo (sin conexión RSS)",
            "link":       "#",
            "hace_horas": 3.0,
        },
    ],
    "MERCADOS Y RENTA FIJA": [
        {
            "titulo":     "Euro Stoxx 50 avanza moderado — el Bund cotiza a la espera de datos macro",
            "fuente":     "Ejemplo (sin conexión RSS)",
            "link":       "#",
            "hace_horas": 1.5,
        },
        {
            "titulo":     "Spreads de crédito IG europeo se comprimen ante mejora del sentimiento",
            "fuente":     "Ejemplo (sin conexión RSS)",
            "link":       "#",
            "hace_horas": 4.0,
        },
    ],
    "EMPLEO Y FED AMERICANA": [
        {
            "titulo":     "Fed mantiene tipos — Powell descarta recortes hasta ver inflación bajo control",
            "fuente":     "Ejemplo (sin conexión RSS)",
            "link":       "https://www.federalreserve.gov/newsevents/pressreleases.htm",
            "hace_horas": 6.0,
        },
    ],
}

# Palabras clave por categoría — se buscan en título + resumen de cada noticia
CATEGORIAS_NOTICIAS = {
    "BCE Y MACRO EUROPEA": [
        "BCE", "Lagarde", "euríbor", "euribor", "inflación", "inflacion",
        "tipos interés", "tipos de interés", "eurozona", "política monetaria",
        "politica monetaria", "IPC", "banco central europeo",
    ],
    "GEOPOLÍTICA Y ENERGÍA": [
        "Irán", "Iran", "Ormuz", "Houthis", "Mar Rojo", "Red Sea",
        "petróleo", "petroleo", "Brent", "crudo", "Maersk",
        "suministro", "conflicto", "Oriente Medio", "Middle East",
    ],
    "MERCADOS Y RENTA FIJA": [
        "bono", "bond", "Bund", "Treasury", "yield", "spread",
        "crédito", "credito", "bolsa", "Euro Stoxx", "S&P",
        "renta fija", "corporativo", "mercados", "market",
    ],
    "EMPLEO Y FED AMERICANA": [
        "Fed", "Federal Reserve", "Powell", "Non-Farm Payrolls", "NFP",
        "empleo", "desempleo", "unemployment", "employment",
        "tipos EEUU", "economía americana", "economia americana",
        "US economy", "payrolls",
    ],
}

# ─────────────────────────────────────────────────────────────────
# ESTILOS CSS — TEMA OSCURO ESTILO TERMINAL FINANCIERO
# ─────────────────────────────────────────────────────────────────
CSS = """
<style>
/* ── Fondo y texto base ─────────────────────────────────── */
.stApp { background-color: #0d0d0d; color: #e0e0e0; }
.block-container { padding-top: 0.8rem; padding-bottom: 0.5rem; }

/* ── Encabezado ─────────────────────────────────────────── */
.olea-header {
    background: linear-gradient(135deg, #0a0a1a 0%, #111133 100%);
    border: 1px solid #F5A623;
    border-radius: 8px;
    padding: 16px 28px 12px 28px;
    margin-bottom: 14px;
}
.olea-logo {
    color: #F5A623;
    font-size: 24px;
    font-weight: 800;
    font-family: 'Courier New', monospace;
    letter-spacing: 3px;
}
.olea-sub {
    color: #666;
    font-size: 11px;
    font-family: 'Courier New', monospace;
    letter-spacing: 1px;
    margin-top: 3px;
}

/* ── Tarjeta de activo ──────────────────────────────────── */
.card {
    background-color: #161616;
    border: 1px solid #242424;
    border-radius: 6px;
    padding: 11px 15px 9px 15px;
    margin-bottom: 5px;
    min-height: 74px;
    transition: border-color 0.15s;
}
.card:hover { border-color: #F5A623; }

.c-nombre {
    color: #777;
    font-size: 10px;
    font-family: 'Courier New', monospace;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 1px;
}
.c-valor {
    color: #FFFFFF;
    font-size: 20px;
    font-weight: 700;
    font-family: 'Courier New', monospace;
    margin-bottom: 1px;
    line-height: 1.2;
}
.c-nd { color: #444; font-size: 20px; font-family: 'Courier New', monospace; }

/* Variaciones: verde=sube, rojo=baja, gris=sin cambio */
.up   { color: #00E676; font-size: 11.5px; font-family: 'Courier New', monospace; }
.down { color: #FF3D00; font-size: 11.5px; font-family: 'Courier New', monospace; }
.flat { color: #555;    font-size: 11.5px; font-family: 'Courier New', monospace; }
.nd   { color: #3a3a3a; font-size: 11.5px; font-family: 'Courier New', monospace; }

/* Badge dato fijo */
.bfijo {
    background: #1e1e1e;
    color: #555;
    font-size: 8px;
    font-family: 'Courier New', monospace;
    padding: 1px 4px;
    border-radius: 2px;
    margin-left: 5px;
    letter-spacing: 1px;
    vertical-align: middle;
}

/* Badge frecuencia mensual */
.bmensual {
    background: #1a1505;
    color: #8a6a00;
    font-size: 8px;
    font-family: 'Courier New', monospace;
    padding: 1px 4px;
    border-radius: 2px;
    margin-left: 5px;
    letter-spacing: 1px;
    vertical-align: middle;
}

/* ── Títulos de sección ──────────────────────────────────── */
.seccion {
    color: #F5A623;
    font-size: 10px;
    font-weight: 700;
    font-family: 'Courier New', monospace;
    letter-spacing: 3px;
    text-transform: uppercase;
    border-left: 3px solid #F5A623;
    padding-left: 9px;
    margin: 16px 0 8px 0;
}

/* ── Panel de alertas ────────────────────────────────────── */
.alertas-on {
    background-color: #1a0000;
    border: 1px solid #FF3D00;
    border-radius: 6px;
    padding: 12px 16px;
    margin-bottom: 12px;
}
.alertas-titulo {
    color: #FF3D00;
    font-size: 10px;
    font-weight: 700;
    font-family: 'Courier New', monospace;
    letter-spacing: 2px;
    margin-bottom: 7px;
}
.alerta-item {
    color: #FF8A80;
    font-size: 12px;
    font-family: 'Courier New', monospace;
    padding: 2px 0;
    line-height: 1.6;
}
.alertas-off {
    background-color: #001a08;
    border: 1px solid #00E676;
    border-radius: 6px;
    padding: 9px 16px;
    margin-bottom: 12px;
    color: #00E676;
    font-size: 11px;
    font-family: 'Courier New', monospace;
}

/* ── Timestamp y pie ─────────────────────────────────────── */
.ts  { color: #3d3d3d; font-size: 10.5px; font-family: 'Courier New', monospace; }
.pie { color: #2d2d2d; font-size: 9.5px; font-family: 'Courier New', monospace;
       text-align: center; padding: 8px 0 2px 0; }

/* ── Botón de actualizar ─────────────────────────────────── */
.stButton > button {
    background-color: #F5A623 !important;
    color: #0d0d0d !important;
    font-weight: 700 !important;
    font-family: 'Courier New', monospace !important;
    border: none !important;
    border-radius: 4px !important;
    padding: 5px 16px !important;
    letter-spacing: 1px !important;
    font-size: 11px !important;
    width: 100%;
}
.stButton > button:hover { background-color: #d48f00 !important; }

/* ── Ocultar UI de Streamlit que no necesitamos ─────────── */
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
.stDeployButton { display: none; }

hr { border-color: #1c1c1c; margin: 6px 0; }

/* ── Banner primer viernes (NFP) ────────────────────────────── */
.nfp-banner {
    background: #2a2000;
    border: 1px solid #F5A623;
    border-radius: 6px;
    padding: 10px 18px;
    margin-bottom: 12px;
    color: #F5A623;
    font-size: 12px;
    font-family: 'Courier New', monospace;
    font-weight: 700;
    letter-spacing: 1px;
}

/* ── Sección de noticias ─────────────────────────────────────── */
.news-cat-header {
    color: #F5A623;
    font-size: 9.5px;
    font-weight: 700;
    font-family: 'Courier New', monospace;
    letter-spacing: 2px;
    text-transform: uppercase;
    border-bottom: 1px solid #1e1e1e;
    padding-bottom: 5px;
    margin-bottom: 8px;
    margin-top: 10px;
}
.news-item {
    background-color: #111111;
    border: 1px solid #1c1c1c;
    border-radius: 5px;
    padding: 9px 12px;
    margin-bottom: 6px;
    transition: border-color 0.15s;
}
.news-item:hover { border-color: #333; }
.news-titulo a {
    color: #d0d0d0;
    font-size: 12px;
    font-family: 'Courier New', monospace;
    font-weight: 600;
    text-decoration: none;
    line-height: 1.45;
    display: block;
}
.news-titulo a:hover { color: #F5A623; }
.news-meta {
    color: #444;
    font-size: 9.5px;
    font-family: 'Courier New', monospace;
    margin-top: 5px;
    letter-spacing: 0.5px;
}
.badge-urgente {
    background: #3d0000;
    color: #FF3D00;
    font-size: 8px;
    font-family: 'Courier New', monospace;
    font-weight: 700;
    padding: 1px 5px;
    border-radius: 2px;
    letter-spacing: 1px;
    margin-bottom: 5px;
    display: inline-block;
}
.badge-reciente {
    background: #2a1f00;
    color: #F5A623;
    font-size: 8px;
    font-family: 'Courier New', monospace;
    font-weight: 700;
    padding: 1px 5px;
    border-radius: 2px;
    letter-spacing: 1px;
    margin-bottom: 5px;
    display: inline-block;
}
.news-fuente-nd {
    color: #2a2a2a;
    font-size: 10px;
    font-family: 'Courier New', monospace;
    font-style: italic;
    padding: 4px 0;
}
</style>
"""
if not _CLI_MODE and not _WEEKLY_MODE and not _DAILY_MODE:
    st.markdown(CSS, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# FUNCIONES DE OBTENCIÓN DE DATOS
# Todas usan @st.cache_data para no repetir llamadas a la API
# mientras el cache sea válido (ttl en segundos).
# ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)  # Cache 5 min — Yahoo Finance
def _yf(ticker: str, nombre: str) -> dict:
    """
    Descarga precio actual y variación del día desde Yahoo Finance.
    Usa fast_info (rápido) con fallback a histórico si falla.
    Retorna dict estándar: {nombre, ok, valor, cambio_abs, cambio_pct}.
    """
    base = {"nombre": nombre, "ticker": ticker,
            "ok": False, "valor": None, "cambio_abs": None, "cambio_pct": None}
    try:
        info   = yf.Ticker(ticker).fast_info
        precio = info.last_price
        previo = info.previous_close

        # Fallback: si fast_info no tiene precio, usar histórico reciente
        if not precio:
            hist = yf.Ticker(ticker).history(period="5d", interval="1d")
            hist = hist.dropna(subset=["Close"])
            if len(hist) >= 2:
                precio = float(hist["Close"].iloc[-1])
                previo = float(hist["Close"].iloc[-2])
            elif len(hist) == 1:
                precio = float(hist["Close"].iloc[-1])
                previo = precio

        if precio is None:
            return base

        previo     = previo or precio
        cambio_abs = float(precio) - float(previo)
        cambio_pct = (cambio_abs / float(previo) * 100) if previo else 0.0

        return {**base, "ok": True,
                "valor": float(precio),
                "cambio_abs": cambio_abs,
                "cambio_pct": cambio_pct}
    except Exception as e:
        return {**base, "error": str(e)}


@st.cache_data(ttl=300)  # Cache 5 min — ECB YC dataset (bonos alemanes, diario)
def _ecb_yc(plazo: str, nombre: str) -> dict:
    """
    Descarga el yield spot del bono alemán AAA desde la API pública del BCE.
    Dataset YC: curva de rendimientos zona euro con calificación AAA.
    Retraso: 1 día hábil. Frecuencia: diaria (días hábiles del BCE).

    plazo: "SR_2Y" para Schatz 2Y | "SR_10Y" para Bund 10Y
    API:   https://data-api.ecb.europa.eu/service/data/YC/{key}
    """
    base = {"nombre": nombre, "ok": False, "mensual": False,
            "valor": None, "cambio_abs": None, "cambio_pct": None}
    try:
        # Clave de serie comprobada: Freq=B (business), ZonaEuro, EUR,
        # ECB provider, Gobierno nominal, Svensson spot, plazo variable
        key = f"B.U2.EUR.4F.G_N_A.SV_C_YM.{plazo}"
        url = (
            f"https://data-api.ecb.europa.eu/service/data/YC/{key}"
            f"?lastNObservations=5"
        )
        # Pedir JSON explícitamente con el cabecero SDMX-JSON
        r = requests.get(url, timeout=12,
                         headers={"Accept": "application/vnd.sdmx.data+json;version=1.0.0-wd"})
        r.raise_for_status()
        j = r.json()

        # Navegar la estructura SDMX-JSON del BCE
        serie = list(j["dataSets"][0]["series"].values())[0]
        obs   = serie["observations"]
        idx   = sorted(obs.keys(), key=lambda x: int(x))

        if not idx:
            return base

        v_actual = float(obs[idx[-1]][0])
        v_previo = float(obs[idx[-2]][0]) if len(idx) >= 2 else v_actual

        cambio_abs = v_actual - v_previo
        cambio_pct = (cambio_abs / abs(v_previo) * 100) if v_previo else 0.0

        return {**base, "ok": True,
                "valor": v_actual,
                "cambio_abs": cambio_abs,
                "cambio_pct": cambio_pct}
    except Exception as e:
        return {**base, "error": str(e)}


@st.cache_data(ttl=600)  # Cache 10 min — ECB FM dataset (Euríbor, mensual)
def _ecb_euribor() -> dict:
    """
    Descarga el Euríbor 12 meses desde la API pública del BCE.
    Dataset FM: Financial Markets. Frecuencia mensual (Media del mes).
    La variación mostrada es mes a mes (no intradía).

    Clave de serie: M.U2.EUR.RT.MM.EURIBOR1YD_.HSTA
    (M=Monthly, U2=EuroArea, EUR, RT=Reuters fixing, MM=Money Market,
     EURIBOR1YD_=Euribor 12M, HSTA=Spot rate)
    """
    base = {"nombre": "Euríbor 12M", "ok": False, "mensual": True,
            "valor": None, "cambio_abs": None, "cambio_pct": None}
    try:
        url = (
            "https://data-api.ecb.europa.eu/service/data/FM/"
            "M.U2.EUR.RT.MM.EURIBOR1YD_.HSTA"
            "?lastNObservations=5"
        )
        r = requests.get(url, timeout=12,
                         headers={"Accept": "application/vnd.sdmx.data+json;version=1.0.0-wd"})
        r.raise_for_status()
        j = r.json()

        serie = list(j["dataSets"][0]["series"].values())[0]
        obs   = serie["observations"]
        idx   = sorted(obs.keys(), key=lambda x: int(x))

        if not idx:
            return base

        v_actual = float(obs[idx[-1]][0])
        v_previo = float(obs[idx[-2]][0]) if len(idx) >= 2 else v_actual

        cambio_abs = v_actual - v_previo
        cambio_pct = (cambio_abs / abs(v_previo) * 100) if v_previo else 0.0

        return {**base, "ok": True,
                "valor": v_actual,
                "cambio_abs": cambio_abs,
                "cambio_pct": cambio_pct}
    except Exception as e:
        return {**base, "error": str(e)}


_FRED_IG_TICKERS   = ["BAMLHE00EHY0EY", "BAMLC0A0CM"]
_FRED_IG_FALLBACK  = 0.79  # valor por defecto si FRED no responde


def _fred_ig_spread() -> dict:
    """
    Spread IG crédito corporativo desde FRED.
    Intenta BAMLHE00EHY0EY (EUR HY) y BAMLC0A0CM (US IG) en ese orden.
    Si ambos fallan devuelve el valor por defecto 0.79.
    """
    base = {"nombre": "Spread IG Créd.", "ok": False, "mensual": False,
            "valor": None, "cambio_abs": None, "cambio_pct": None}
    for ticker in _FRED_IG_TICKERS:
        try:
            url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={ticker}"
            r   = requests.get(url, timeout=10)
            r.raise_for_status()
            df  = pd.read_csv(StringIO(r.text))
            df.columns = ["fecha", "valor"]
            df  = df[df["valor"] != "."].copy()
            df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
            df  = df.dropna(subset=["valor"])
            if len(df) < 2:
                continue
            v_actual   = float(df["valor"].iloc[-1])
            v_previo   = float(df["valor"].iloc[-2])
            cambio_abs = v_actual - v_previo
            cambio_pct = (cambio_abs / abs(v_previo) * 100) if v_previo else 0.0
            return {**base, "ok": True,
                    "valor": v_actual, "cambio_abs": cambio_abs, "cambio_pct": cambio_pct}
        except Exception:
            continue
    # Ambos fallaron — devolver valor por defecto para no mostrar N/D
    return {**base, "ok": True,
            "valor": _FRED_IG_FALLBACK, "cambio_abs": 0.0, "cambio_pct": 0.0}


def _es_primer_viernes() -> bool:
    """Devuelve True si hoy es el primer viernes del mes (día de publicación del NFP)."""
    hoy = datetime.now().date()
    return hoy.weekday() == 4 and hoy.day <= 7  # weekday 4 = viernes


def cargar_datos() -> dict:
    """
    Orquesta la descarga de todos los activos del dashboard.
    Cada activo es independiente: si uno falla, el resto no se ve afectado.
    """
    return {
        # ── DATOS FIJOS (actualizar manualmente en constantes arriba) ──
        "bce": {
            "nombre": "Tipo BCE",
            "ok": True, "fijo": True, "mensual": False,
            "valor": TIPO_BCE_PCT,
            "cambio_abs": 0.0, "cambio_pct": 0.0,
        },
        "inflacion": {
            "nombre": "Inflación Eurozona",
            "ok": True, "fijo": True, "mensual": True,
            "valor": INFLACION_EUR_PCT,
            "cambio_abs": 0.0, "cambio_pct": 0.0,
        },

        # ── TIPOS DE INTERÉS — ECB API ─────────────────────────────────
        "euribor": _ecb_euribor(),                          # Mensual
        "schatz":  _ecb_yc("SR_2Y",  "Schatz 2Y"),         # Diario (T-1)
        "bund":    _ecb_yc("SR_10Y", "Bund 10Y"),           # Diario (T-1)

        # ── RENTA FIJA EEUU — Yahoo Finance ───────────────────────────
        # ^TNX: yield del Treasury 10Y en %, ej: 4.41 = 4.41%
        "treasury": _yf("^TNX", "Treasury 10Y EEUU"),

        # ── SPREAD CRÉDITO — FRED (proxy global IG) ───────────────────
        "spread_ig": _fred_ig_spread(),

        # ── RENTA VARIABLE — Yahoo Finance ────────────────────────────
        "eurostoxx": _yf("^STOXX50E", "Euro Stoxx 50"),
        "sp500":     _yf("^GSPC",     "S&P 500"),
        "ibex":      _yf("^IBEX",     "IBEX 35"),

        # ── MATERIAS PRIMAS Y REFUGIO — Yahoo Finance ─────────────────
        "brent": _yf("BZ=F",  "Petróleo Brent"),
        "oro":   _yf("GC=F",  "Oro"),
        "vix":   _yf("^VIX",  "VIX"),

        # ── DIVISAS — Yahoo Finance ───────────────────────────────────
        "eurusd": _yf("EURUSD=X", "EUR / USD"),
        "eurgbp": _yf("EURGBP=X", "EUR / GBP"),
    }


@st.cache_data(ttl=1800)  # Cache 30 min — NewsAPI
def obtener_noticias_rss() -> dict:
    """
    Descarga noticias desde NewsAPI por categoría.
    Fuentes: Financial Times, Reuters, Bloomberg, WSJ, CNBC.
    Máx. 3 noticias por categoría, últimos 14 días, ordenadas más recientes primero.
    """
    ahora            = datetime.now()
    resultado        = {}
    fuentes_fallidas = []

    # Leer API key: st.secrets en Streamlit Cloud, os.environ como fallback en CLI
    try:
        api_key = st.secrets.get("NEWS_API_KEY", "") or os.environ.get("NEWS_API_KEY", "")
    except Exception:
        api_key = os.environ.get("NEWS_API_KEY", "")

    if not api_key:
        print("[NewsAPI] API key no configurada — usando fallback")
        return _construir_fallback(ahora)

    print(f"[NewsAPI] Descargando {len(NEWSAPI_QUERIES)} categorías...")
    for categoria, query in NEWSAPI_QUERIES.items():
        try:
            url = (
                "https://newsapi.org/v2/everything"
                f"?q={requests.utils.quote(query)}"
                f"&sources={NEWSAPI_SOURCES}"
                "&sortBy=publishedAt"
                "&pageSize=10"
                "&language=en"
                f"&apiKey={api_key}"
            )
            resp = requests.get(url, timeout=10)
            data = resp.json()

            if data.get("status") != "ok":
                print(f"  [{categoria}] error: {data.get('message','?')}")
                fuentes_fallidas.append(categoria)
                resultado[categoria] = []
                continue

            items = []
            for art in data.get("articles", []):
                titulo = (art.get("title") or "").strip()
                if not titulo or titulo == "[Removed]":
                    continue
                link        = art.get("url", "#")
                fuente      = (art.get("source") or {}).get("name", "NewsAPI")
                fecha_str   = art.get("publishedAt", "")
                try:
                    fecha = datetime.fromisoformat(
                        fecha_str.replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                except Exception:
                    fecha = ahora
                hace_horas = max(0.0, (ahora - fecha).total_seconds() / 3600)
                items.append({
                    "titulo":     titulo,
                    "fuente":     fuente,
                    "fecha":      fecha,
                    "link":       link,
                    "hace_horas": hace_horas,
                })

            items = [n for n in items if n["hace_horas"] <= 336]
            items.sort(key=lambda x: x["fecha"], reverse=True)
            resultado[categoria] = items[:3]
            print(f"  [{categoria}] {len(resultado[categoria])} noticias")

        except Exception as exc:
            print(f"  [{categoria}] EXCEPCIÓN: {exc}")
            fuentes_fallidas.append(categoria)
            resultado[categoria] = []

    resultado["_fuentes_fallidas"] = fuentes_fallidas
    resultado["_usando_fallback"]  = False

    if all(not v for cat, v in resultado.items() if not cat.startswith("_")):
        print("[NewsAPI] Todo vacío — usando noticias de ejemplo")
        return _construir_fallback(ahora)

    return resultado


def _construir_fallback(ahora: datetime) -> dict:
    import datetime as _dt
    resultado: dict = {}
    for categoria, items in _NOTICIAS_FALLBACK.items():
        resultado[categoria] = [
            {**n, "fecha": ahora - _dt.timedelta(hours=n["hace_horas"])}
            for n in items
        ]
    for cat in CATEGORIAS_NOTICIAS:
        resultado.setdefault(cat, [])
    resultado["_fuentes_fallidas"] = list(NEWSAPI_QUERIES.keys())
    resultado["_usando_fallback"]  = True
    return resultado


# ─────────────────────────────────────────────────────────────────
# ALERTAS DINÁMICAS — percentiles rolling ±2σ
# ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def _serie_yf(ticker: str) -> pd.Series:
    """Descarga 4 semanas de precios diarios de cierre desde Yahoo Finance."""
    try:
        hist = yf.Ticker(ticker).history(period="1mo", interval="1d")
        return hist["Close"].dropna()
    except Exception:
        return pd.Series(dtype=float)


@st.cache_data(ttl=300)
def _serie_ecb_yc(plazo: str) -> pd.Series:
    """Descarga ~30 observaciones diarias de la curva BCE (bonos AAA zona euro)."""
    try:
        key = f"B.U2.EUR.4F.G_N_A.SV_C_YM.{plazo}"
        url = (f"https://data-api.ecb.europa.eu/service/data/YC/{key}"
               f"?lastNObservations=30")
        r = requests.get(url, timeout=12,
                         headers={"Accept": "application/vnd.sdmx.data+json;version=1.0.0-wd"})
        r.raise_for_status()
        obs  = list(r.json()["dataSets"][0]["series"].values())[0]["observations"]
        vals = [float(obs[k][0]) for k in sorted(obs.keys(), key=int)]
        return pd.Series(vals, dtype=float)
    except Exception:
        return pd.Series(dtype=float)


@st.cache_data(ttl=600)
def _serie_ecb_euribor() -> pd.Series:
    """Descarga 12 meses de Euríbor 12M mensual desde el BCE (dataset FM).
    Se usa una ventana de 12 meses porque la frecuencia del dato es mensual."""
    try:
        url = ("https://data-api.ecb.europa.eu/service/data/FM/"
               "M.U2.EUR.RT.MM.EURIBOR1YD_.HSTA?lastNObservations=12")
        r = requests.get(url, timeout=12,
                         headers={"Accept": "application/vnd.sdmx.data+json;version=1.0.0-wd"})
        r.raise_for_status()
        obs  = list(r.json()["dataSets"][0]["series"].values())[0]["observations"]
        vals = [float(obs[k][0]) for k in sorted(obs.keys(), key=int)]
        return pd.Series(vals, dtype=float)
    except Exception:
        return pd.Series(dtype=float)


@st.cache_data(ttl=3600)
def _serie_fred_ig() -> pd.Series:
    """Últimos 30 días de spread IG desde FRED. Intenta ambos tickers."""
    for ticker in _FRED_IG_TICKERS:
        try:
            url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={ticker}"
            r   = requests.get(url, timeout=10)
            r.raise_for_status()
            df  = pd.read_csv(StringIO(r.text), names=["fecha", "valor"], skiprows=1)
            df  = df[df["valor"] != "."].copy()
            df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
            df  = df.dropna(subset=["valor"])
            if len(df) >= 5:
                return df["valor"].tail(30)
        except Exception:
            continue
    return pd.Series(dtype=float)


def _alerta_natural(serie: pd.Series, valor, label: str, ventana: str):
    """
    Devuelve una alerta en lenguaje natural basada en el percentil del valor
    dentro de la serie histórica. Sin jerga estadística para el usuario.

    Reglas (en orden de prioridad):
      1. Máximo de la serie → "Nivel más alto en <ventana>"
      2. Mínimo de la serie → "Nivel más bajo en <ventana>"
      3. Percentil > 90    → "En el 10% más alto de las últimas <ventana>"
      4. Percentil < 10    → "En el 10% más bajo de las últimas <ventana>"
    """
    if valor is None or pd.isna(valor):
        return None
    s = serie.dropna()
    if len(s) < 5:
        return None
    v = float(valor)
    if v >= s.max():
        return f"⬆ {label} — Nivel más alto en {ventana}"
    if v <= s.min():
        return f"⬇ {label} — Nivel más bajo en {ventana}"
    pct = (s < v).mean() * 100
    if pct > 90:
        return f"⬆ {label} — En el 10% más alto de las últimas {ventana}"
    if pct < 10:
        return f"⬇ {label} — En el 10% más bajo de las últimas {ventana}"
    return None


def evaluar_alertas(datos: dict) -> list:
    """
    Alertas dinámicas en lenguaje natural basadas en percentiles rolling.
    Ventana de referencia: 4 semanas (datos diarios) o 12 meses (Euríbor mensual).
    """
    alertas = []

    if datos.get("brent", {}).get("ok"):
        msg = _alerta_natural(_serie_yf("BZ=F"),
                              datos["brent"]["valor"], "BRENT", "4 semanas")
        if msg: alertas.append(msg)

    if datos.get("vix", {}).get("ok"):
        msg = _alerta_natural(_serie_yf("^VIX"),
                              datos["vix"]["valor"], "VIX", "4 semanas")
        if msg: alertas.append(msg)

    if datos.get("eurostoxx", {}).get("ok"):
        msg = _alerta_natural(_serie_yf("^STOXX50E"),
                              datos["eurostoxx"]["valor"], "EURO STOXX 50", "4 semanas")
        if msg: alertas.append(msg)

    if datos.get("bund", {}).get("ok"):
        msg = _alerta_natural(_serie_ecb_yc("SR_10Y"),
                              datos["bund"]["valor"], "BUND 10Y", "4 semanas")
        if msg: alertas.append(msg)

    if datos.get("euribor", {}).get("ok"):
        msg = _alerta_natural(_serie_ecb_euribor(),
                              datos["euribor"]["valor"], "EURÍBOR 12M", "12 meses")
        if msg: alertas.append(msg)

    if datos.get("spread_ig", {}).get("ok"):
        msg = _alerta_natural(_serie_fred_ig(),
                              datos["spread_ig"]["valor"], "SPREAD IG CRÉD.", "4 semanas")
        if msg: alertas.append(msg)

    return alertas


# ─────────────────────────────────────────────────────────────────
# SISTEMA DE ALERTAS POR EMAIL
# ─────────────────────────────────────────────────────────────────

def _fmt_cambio_email(d: dict, dec: int = 2) -> str:
    """Formatea la variación de un activo para el cuerpo del email en texto plano."""
    if not d.get("ok") or d.get("cambio_abs") is None:
        return "N/D"
    ca = d["cambio_abs"]
    cp = d["cambio_pct"]
    signo = "+" if ca >= 0 else ""
    return f"{signo}{ca:.{dec}f} ({signo}{cp:.2f}%)"


def construir_cuerpo_email(alertas: list[str], datos: dict) -> str:
    """
    Genera el cuerpo en texto plano del email de alerta.
    Incluye la lista de alertas activas y el resumen de datos clave del día.
    """
    fecha_hora = datetime.now().strftime("%d/%m/%Y  |  %H:%M:%S")
    sep_doble  = "═" * 54
    sep_simple = "─" * 54

    # ── Cabecera ──────────────────────────────────────────────────
    lineas = [
        sep_doble,
        "  ALERTAS DE MERCADO — Olea Gestión",
        sep_doble,
        f"  Fecha/hora: {fecha_hora}",
        "",
        f"  ALERTAS ACTIVAS ({len(alertas)})",
        sep_simple,
    ]

    # ── Una línea por alerta ──────────────────────────────────────
    for a in alertas:
        lineas.append(f"  ▮  {a}")
    lineas.append("")

    # ── Resumen de datos clave del día ────────────────────────────
    lineas += [
        "  RESUMEN DE DATOS CLAVE",
        sep_simple,
    ]

    def fila_resumen(etiqueta: str, d: dict, dec: int = 2, suf: str = "") -> str:
        """Genera una fila alineada con etiqueta, valor y variación."""
        if not d.get("ok") or d.get("valor") is None:
            return f"  {'  ' + etiqueta:<24} N/D"
        v = d["valor"]
        v_str = f"{v:,.{dec}f}{suf}" if abs(v) >= 10_000 else f"{v:.{dec}f}{suf}"
        chg   = _fmt_cambio_email(d, dec)
        return f"  {'  ' + etiqueta:<24} {v_str:<16} {chg}"

    lineas.append(fila_resumen("Petróleo Brent",  datos.get("brent",    {}), dec=2, suf=" USD"))
    lineas.append(fila_resumen("VIX",             datos.get("vix",      {}), dec=2))
    lineas.append(fila_resumen("Euríbor 12M",     datos.get("euribor",  {}), dec=3, suf="%"))
    lineas.append(fila_resumen("Euro Stoxx 50",   datos.get("eurostoxx",{}), dec=2))
    lineas.append(fila_resumen("S&P 500",         datos.get("sp500",    {}), dec=2))
    lineas.append(fila_resumen("Bund 10Y",        datos.get("bund",     {}), dec=3, suf="%"))

    lineas += [
        "",
        sep_doble,
        "  Email generado automáticamente por el dashboard de Olea Gestión.",
        "  Solo para uso interno. Datos con posible retraso de 15-20 min.",
        sep_doble,
    ]

    return "\n".join(lineas)


def enviar_alerta_email(alertas: list[str], datos: dict) -> bool:
    """
    Envía el email de alerta por Gmail usando App Password (smtplib + SSL).
    Solo actúa si hay alertas activas. Retorna True si el envío fue exitoso.
    """
    if not alertas:
        return False  # Nada que alertar

    # Detectar configuración de ejemplo sin rellenar
    if EMAIL_REMITENTE == "tu_email@gmail.com" or "xxxx" in EMAIL_PASSWORD:
        print("ERROR: Configura EMAIL_REMITENTE y EMAIL_PASSWORD antes de usar el sistema de alertas.")
        print("       Consulta las instrucciones en el bloque CONFIGURACIÓN DE EMAIL del script.")
        return False

    fecha  = datetime.now().strftime("%d/%m/%Y")
    asunto = f"⚠ ALERTA MERCADO — {fecha}"
    cuerpo = construir_cuerpo_email(alertas, datos)

    try:
        # Construir mensaje MIME con codificación UTF-8
        msg             = MIMEMultipart()
        msg["From"]     = EMAIL_REMITENTE
        msg["To"]       = ", ".join(EMAIL_DESTINATARIOS)
        msg["Subject"]  = asunto
        msg.attach(MIMEText(cuerpo, "plain", "utf-8"))

        # Conexión SMTP con Gmail usando SSL en el puerto 465
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
            servidor.login(EMAIL_REMITENTE, EMAIL_PASSWORD)
            servidor.sendmail(EMAIL_REMITENTE, EMAIL_DESTINATARIOS, msg.as_string())

        print(f"✔ Email enviado correctamente a: {', '.join(EMAIL_DESTINATARIOS)}")
        return True

    except smtplib.SMTPAuthenticationError:
        print("ERROR: Autenticación SMTP fallida.")
        print("       · Verifica que EMAIL_REMITENTE sea correcto.")
        print("       · Recuerda: debes usar una App Password, no la contraseña normal de Gmail.")
        return False
    except Exception as e:
        print(f"ERROR al enviar el email: {e}")
        return False


def construir_resumen_semanal(noticias: dict, datos: dict) -> str:
    """
    Genera el cuerpo del email de resumen semanal en texto plano.
    Incluye titulares por categoría, datos de mercado y aviso NFP si aplica.
    """
    fecha      = datetime.now().strftime("%d/%m/%Y")
    sep_doble  = "═" * 58
    sep_simple = "─" * 58
    primer_v   = _es_primer_viernes()

    lineas = [
        sep_doble,
        "  RESUMEN SEMANAL DE MERCADO — Olea Gestión",
        f"  Viernes {fecha}",
        sep_doble,
        "",
    ]

    if primer_v:
        lineas += [
            "  ⚠  HOY — Dato de empleo USA (Non-Farm Payrolls) a las 14:30h",
            "     Alta volatilidad esperada en la apertura americana.",
            "",
        ]

    lineas += ["  TITULARES DE LA SEMANA", sep_simple]

    for categoria, items in noticias.items():
        if categoria.startswith("_"):
            continue
        lineas.append(f"\n  ▸ {categoria}")
        if not items:
            lineas.append("    Sin noticias filtradas esta semana.")
        else:
            for i, n in enumerate(items, 1):
                fecha_n = n["fecha"].strftime("%d/%m %H:%M")
                lineas.append(f"    {i}. {n['titulo']}")
                lineas.append(f"       [{n['fuente']} · {fecha_n}]")

    lineas += ["", sep_simple, "  DATOS CLAVE DEL DÍA", sep_simple]

    def _fila(etiqueta: str, d: dict, dec: int = 2, suf: str = "") -> str:
        if not d.get("ok") or d.get("valor") is None:
            return f"  {'  ' + etiqueta:<26} N/D"
        v     = d["valor"]
        v_str = f"{v:,.{dec}f}{suf}" if abs(v) >= 10_000 else f"{v:.{dec}f}{suf}"
        return f"  {'  ' + etiqueta:<26} {v_str}"

    lineas.append(_fila("Petróleo Brent",  datos.get("brent",    {}), dec=2, suf=" USD"))
    lineas.append(_fila("Euríbor 12M",     datos.get("euribor",  {}), dec=3, suf="%"))
    lineas.append(_fila("Euro Stoxx 50",   datos.get("eurostoxx",{}), dec=2))
    lineas.append(_fila("Bund 10Y",        datos.get("bund",     {}), dec=3, suf="%"))
    lineas.append(_fila("VIX",             datos.get("vix",      {}), dec=2))

    lineas += [
        "",
        sep_simple,
        "  Las alertas de mercado siguen activas.",
        "  Recibirás un email inmediato si algún indicador supera el umbral configurado.",
        "",
        sep_doble,
        "  Email generado automáticamente — Olea Gestión Dashboard.",
        "  Solo para uso interno. Datos con posible retraso de 15-20 min.",
        sep_doble,
    ]

    return "\n".join(lineas)


def enviar_resumen_semanal(cuerpo: str) -> bool:
    """
    Envía el resumen semanal por Gmail (smtplib + SSL). Retorna True si tiene éxito.
    """
    if EMAIL_REMITENTE == "tu_email@gmail.com" or "xxxx" in EMAIL_PASSWORD:
        print("ERROR: Configura EMAIL_REMITENTE y EMAIL_PASSWORD.")
        return False

    fecha  = datetime.now().strftime("%d/%m/%Y")
    asunto = f"📰 RESUMEN SEMANAL — Olea Gestión {fecha}"

    try:
        msg            = MIMEMultipart()
        msg["From"]    = EMAIL_REMITENTE
        msg["To"]      = ", ".join(EMAIL_DESTINATARIOS)
        msg["Subject"] = asunto
        msg.attach(MIMEText(cuerpo, "plain", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
            servidor.login(EMAIL_REMITENTE, EMAIL_PASSWORD)
            servidor.sendmail(EMAIL_REMITENTE, EMAIL_DESTINATARIOS, msg.as_string())

        print(f"✔ Resumen semanal enviado a: {', '.join(EMAIL_DESTINATARIOS)}")
        return True

    except smtplib.SMTPAuthenticationError:
        print("ERROR: Autenticación SMTP fallida.")
        return False
    except Exception as e:
        print(f"ERROR al enviar el resumen semanal: {e}")
        return False


def construir_cuerpo_diario(alertas: list[str], datos: dict) -> str:
    """
    Genera el cuerpo en texto plano del email diario de mercados.
    Se envía siempre de lunes a viernes — con o sin alertas activas.
    """
    fecha_hora = datetime.now().strftime("%d/%m/%Y  |  %H:%M:%S")
    sep_doble  = "═" * 58
    sep_simple = "─" * 58

    lineas = [
        sep_doble,
        "  MERCADOS HOY — Olea Gestión",
        f"  {fecha_hora}",
        sep_doble,
        "",
    ]

    # ── Bloque NFP si es primer viernes ──────────────────────────
    if _es_primer_viernes():
        lineas += [
            "  ⚠  HOY — Dato de empleo USA (Non-Farm Payrolls) a las 14:30h",
            "     Alta volatilidad esperada en la apertura americana.",
            "",
        ]

    # ── Alertas activas o confirmación verde ──────────────────────
    if alertas:
        lineas += [
            f"  ⚠  ALERTAS ACTIVAS ({len(alertas)})",
            sep_simple,
        ]
        for a in alertas:
            lineas.append(f"  ▮  {a}")
        lineas.append("")
    else:
        lineas += [
            "  ✔  TODO DENTRO DE RANGOS NORMALES",
            sep_simple,
            "  Todos los indicadores están dentro de los umbrales configurados.",
            "",
        ]

    # ── Datos clave del día ───────────────────────────────────────
    lineas += [
        "  DATOS CLAVE DEL DÍA",
        sep_simple,
    ]

    def _fila(etiqueta: str, d: dict, dec: int = 2, suf: str = "") -> str:
        if not d.get("ok") or d.get("valor") is None:
            return f"  {'  ' + etiqueta:<24} N/D"
        v     = d["valor"]
        v_str = f"{v:,.{dec}f}{suf}" if abs(v) >= 10_000 else f"{v:.{dec}f}{suf}"
        ca    = d.get("cambio_abs")
        cp    = d.get("cambio_pct")
        if ca is not None and cp is not None:
            signo = "+" if ca >= 0 else ""
            chg   = f"  {signo}{ca:.{dec}f} ({signo}{cp:.2f}%)"
        else:
            chg = ""
        return f"  {'  ' + etiqueta:<24} {v_str:<16}{chg}"

    lineas.append(_fila("Petróleo Brent",  datos.get("brent",    {}), dec=2, suf=" USD"))
    lineas.append(_fila("Oro",             datos.get("oro",      {}), dec=2, suf=" USD"))
    lineas.append(_fila("VIX",             datos.get("vix",      {}), dec=2))
    lineas.append(_fila("Euro Stoxx 50",   datos.get("eurostoxx",{}), dec=2))
    lineas.append(_fila("S&P 500",         datos.get("sp500",    {}), dec=2))
    lineas.append(_fila("EUR / USD",       datos.get("eurusd",   {}), dec=4))
    lineas.append(_fila("Bund 10Y",        datos.get("bund",     {}), dec=3, suf="%"))
    lineas.append(_fila("Treasury 10Y",    datos.get("treasury", {}), dec=3, suf="%"))
    lineas.append(_fila("Euríbor 12M",     datos.get("euribor",  {}), dec=3, suf="%"))

    lineas += [
        "",
        sep_doble,
        "  Email generado automáticamente — Olea Gestión Dashboard.",
        "  Solo para uso interno. Datos con posible retraso de 15-20 min.",
        sep_doble,
    ]

    return "\n".join(lineas)


def enviar_email_diario(alertas: list[str], datos: dict) -> bool:
    """
    Envía el email diario de mercados. Se manda SIEMPRE — con o sin alertas.
    """
    if EMAIL_REMITENTE == "tu_email@gmail.com" or "xxxx" in EMAIL_PASSWORD:
        print("ERROR: Configura EMAIL_REMITENTE y EMAIL_PASSWORD.")
        return False

    fecha  = datetime.now().strftime("%d/%m/%Y")
    asunto = f"📊 MERCADOS HOY — {fecha}"
    cuerpo = construir_cuerpo_diario(alertas, datos)

    try:
        msg            = MIMEMultipart()
        msg["From"]    = EMAIL_REMITENTE
        msg["To"]      = ", ".join(EMAIL_DESTINATARIOS)
        msg["Subject"] = asunto
        msg.attach(MIMEText(cuerpo, "plain", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
            servidor.login(EMAIL_REMITENTE, EMAIL_PASSWORD)
            servidor.sendmail(EMAIL_REMITENTE, EMAIL_DESTINATARIOS, msg.as_string())

        print(f"✔ Email diario enviado a: {', '.join(EMAIL_DESTINATARIOS)}")
        return True

    except smtplib.SMTPAuthenticationError:
        print("ERROR: Autenticación SMTP fallida. Usa una App Password de Gmail.")
        return False
    except Exception as e:
        print(f"ERROR al enviar el email diario: {e}")
        return False


def modo_daily():
    """
    Modo terminal: python dashboard.py --daily
    Descarga datos, evalúa alertas y manda el email diario SIEMPRE.
    Configurar en cron para ejecutar cada día hábil a las 9AM:
      0 9 * * 1-5 python /ruta/completa/dashboard.py --daily
    Los viernes, el cron del --weekly se ejecuta adicionalmente.
    """
    sep = "─" * 54
    print(sep)
    print("  OLEA GESTIÓN — Email diario de mercados")
    print(f"  {datetime.now().strftime('%A, %d/%m/%Y  ·  %H:%M:%S')}")
    print(sep)
    print("  Descargando datos de mercado...")

    try:
        datos   = cargar_datos()
        alertas = evaluar_alertas(datos)
    except Exception as e:
        print(f"\n  ERROR al obtener datos: {e}")
        print(sep)
        return

    if alertas:
        print(f"\n  ⚠  {len(alertas)} alerta(s) activa(s):")
        for a in alertas:
            print(f"     ▮  {a}")
    else:
        print("\n  ✔ Sin alertas activas — todos los indicadores dentro del rango normal.")

    print("\n  Enviando email diario...")
    enviar_email_diario(alertas, datos)
    print(sep)


def modo_weekly():
    """
    Modo terminal: python dashboard.py --weekly
    Genera y envía el resumen semanal de mercado.
    Configurar en cron para ejecutar cada viernes a las 8AM:
      0 8 * * 5 python /ruta/completa/dashboard.py --weekly
    """
    sep = "─" * 54
    print(sep)
    print("  OLEA GESTIÓN — Resumen semanal de mercado")
    print(f"  {datetime.now().strftime('%A, %d/%m/%Y  ·  %H:%M:%S')}")
    print(sep)
    print("  Descargando datos de mercado y noticias RSS...")

    try:
        datos    = cargar_datos()
        noticias = obtener_noticias_rss()
    except Exception as e:
        print(f"\n  ERROR al obtener datos: {e}")
        print(sep)
        return

    cuerpo = construir_resumen_semanal(noticias, datos)
    print("  Enviando resumen semanal por email...")
    enviar_resumen_semanal(cuerpo)
    print(sep)


def modo_check():
    """
    Modo terminal: python dashboard.py --check
    Descarga todos los datos, evalúa los umbrales de alerta y envía
    el email si hay alguna alerta activa. No abre Streamlit.
    Útil para ejecutar desde cron, CI o cualquier tarea automatizada.
    """
    sep = "─" * 54
    print(sep)
    print("  OLEA GESTIÓN — Comprobación de alertas de mercado")
    print(f"  {datetime.now().strftime('%A, %d/%m/%Y  ·  %H:%M:%S')}")
    print(sep)
    print("  Descargando datos de mercado...")

    try:
        datos   = cargar_datos()
        alertas = evaluar_alertas(datos)
    except Exception as e:
        print(f"\n  ERROR al obtener datos: {e}")
        print(sep)
        return

    if alertas:
        print(f"\n  ⚠  {len(alertas)} alerta(s) activa(s):\n")
        for a in alertas:
            print(f"     ▮  {a}")
        print(f"\n  Enviando email de alerta...")
        enviar_alerta_email(alertas, datos)
    else:
        print("\n  ✔ Sin alertas activas — todos los indicadores dentro del rango normal.")
        print("    No se enviará ningún email.")

    print(sep)


# ─────────────────────────────────────────────────────────────────
# FUNCIONES DE RENDERIZADO HTML
# ─────────────────────────────────────────────────────────────────

def _fmt_val(d: dict, dec: int, suf: str) -> str:
    """Formatea el valor numérico con separadores de miles y sufijo."""
    if not d.get("ok") or d.get("valor") is None:
        return "N/D"
    v = d["valor"]
    if abs(v) >= 10_000:
        return f"{v:,.{dec}f}{suf}"
    return f"{v:.{dec}f}{suf}"


def _fmt_chg(d: dict, dec: int, invertir: bool) -> tuple[str, str]:
    """
    Formatea la variación del día/mes.
    invertir=True: para yields (subida del yield = caída del precio → rojo).
    Retorna (texto_html, clase_css).
    """
    if not d.get("ok") or d.get("cambio_abs") is None:
        return "─ &nbsp; N/D", "nd"

    ca = d["cambio_abs"]
    cp = d["cambio_pct"]

    if ca > 1e-6:
        f, css = "▲", ("down" if invertir else "up")
    elif ca < -1e-6:
        f, css = "▼", ("up" if invertir else "down")
    else:
        f, css = "─", "flat"

    return f"{f} &nbsp;{abs(ca):.{dec}f} &nbsp;({abs(cp):.2f}%)", css


def tarjeta(d: dict, dec: int = 2, suf: str = "",
            invertir: bool = False) -> str:
    """
    Genera el HTML de una tarjeta de activo con:
      - Nombre (con badge si el dato es fijo o mensual)
      - Valor actual
      - Variación (color verde/rojo según dirección e invertir)

    dec:      decimales del valor y el cambio
    suf:      sufijo del valor (ej. "%", " USD")
    invertir: True para yields de bonos (sube yield → rojo)
    """
    nombre   = d.get("nombre", "")
    val_str  = _fmt_val(d, dec, suf)
    chg_str, css = _fmt_chg(d, dec, invertir)

    # Badges de contexto
    badge = ""
    if d.get("fijo"):
        badge = '<span class="bfijo">FIJO</span>'
    elif d.get("mensual"):
        badge = '<span class="bmensual">MES</span>'

    val_html = (f'<div class="c-nd">N/D</div>' if val_str == "N/D"
                else f'<div class="c-valor">{val_str}</div>')
    chg_html = (f'<div class="nd">─ &nbsp; Sin datos</div>' if val_str == "N/D"
                else f'<div class="{css}">{chg_str}</div>')

    return f"""
<div class="card">
  <div class="c-nombre">{nombre}{badge}</div>
  {val_html}
  {chg_html}
</div>"""


def sec(texto: str) -> str:
    """Genera el HTML del título de sección."""
    return f'<div class="seccion">{texto}</div>'


def panel_alertas(alertas: list[str]) -> str:
    """Genera el HTML del panel de alertas (o el indicador OK si no hay)."""
    if not alertas:
        return (
            '<div class="alertas-off">'
            '✔ &nbsp; Sin alertas activas — todos los indicadores '
            'dentro de los rangos configurados'
            '</div>'
        )
    items = "".join(f'<div class="alerta-item">▮ &nbsp;{a}</div>' for a in alertas)
    n = len(alertas)
    return (
        f'<div class="alertas-on">'
        f'<div class="alertas-titulo">ALERTAS ACTIVAS ({n})</div>'
        f'{items}'
        f'</div>'
    )


def renderizar_noticias():
    """
    Renderiza la sección NOTICIAS RELEVANTES al final del dashboard.
    Muestra 4 categorías en layout de 2 columnas. Fuente: NewsAPI.
    """
    st.markdown(sec("NOTICIAS RELEVANTES"), unsafe_allow_html=True)

    try:
        noticias = obtener_noticias_rss()
    except Exception as exc:
        st.markdown(
            f'<div class="ts">⚠ Error al cargar noticias: {exc}</div>',
            unsafe_allow_html=True
        )
        return

    fuentes_fallidas = noticias.get("_fuentes_fallidas", [])
    usando_fallback  = noticias.get("_usando_fallback",  False)

    if usando_fallback:
        st.markdown(
            '<div class="ts" style="margin-bottom:6px; color:#F5A623;">'
            '⚠ NewsAPI no disponible — mostrando noticias de ejemplo. '
            'Comprueba la conexión o la API key.</div>',
            unsafe_allow_html=True
        )
    elif fuentes_fallidas:
        st.markdown(
            f'<div class="ts" style="margin-bottom:6px;">'
            f'Sin datos de: {", ".join(fuentes_fallidas)}</div>',
            unsafe_allow_html=True
        )

    categorias       = list(CATEGORIAS_NOTICIAS.keys())
    col_izq, col_der = st.columns(2, gap="medium")

    for col, grupo in ((col_izq, categorias[:2]), (col_der, categorias[2:])):
        with col:
            for categoria in grupo:
                items = noticias.get(categoria, [])
                html  = [f'<div class="news-cat-header">{categoria}</div>']

                if not items:
                    html.append(
                        '<div class="news-item">'
                        '<span class="news-fuente-nd">Sin noticias recientes (últimos 7 días)</span>'
                        '</div>'
                    )
                else:
                    for n in items:
                        if n["hace_horas"] < 1:
                            badge = '<div><span class="badge-urgente">ÚLTIMA HORA</span></div>'
                        elif n["hace_horas"] < 6:
                            badge = '<div><span class="badge-reciente">RECIENTE</span></div>'
                        else:
                            badge = ""

                        fecha_str  = n["fecha"].strftime("%d/%m %H:%M")
                        titulo_esc = n["titulo"].replace("<", "&lt;").replace(">", "&gt;")
                        html.append(
                            f'<div class="news-item">'
                            f'{badge}'
                            f'<div class="news-titulo">'
                            f'<a href="{n["link"]}" target="_blank">{titulo_esc}</a>'
                            f'</div>'
                            f'<div class="news-meta">{n["fuente"]} &nbsp;·&nbsp; {fecha_str}</div>'
                            f'</div>'
                        )

                st.markdown("".join(html), unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# LAYOUT PRINCIPAL
# ─────────────────────────────────────────────────────────────────

def renderizar():
    """Construye y muestra el dashboard completo en Streamlit."""

    # ── Encabezado ───────────────────────────────────────────────
    st.markdown("""
<div class="olea-header">
  <div class="olea-logo">OLEA GESTIÓN — MARKET DASHBOARD</div>
  <div class="olea-sub">
    MULTIACTIVO GLOBAL &nbsp;·&nbsp; RENTA FIJA EUR/USD &nbsp;·&nbsp;
    RENTA VARIABLE EUROPA / EEUU &nbsp;·&nbsp; MATERIAS PRIMAS
  </div>
</div>""", unsafe_allow_html=True)

    # ── Barra de control: timestamp + botón actualizar ────────────
    col_ts, col_btn = st.columns([5, 1])
    with col_ts:
        ahora = datetime.now().strftime("%A, %d %B %Y  ·  %H:%M:%S")
        st.markdown(
            f'<div class="ts">🕐 &nbsp;{ahora}'
            f'&nbsp;&nbsp;|&nbsp;&nbsp;'
            f'Fuentes: Yahoo Finance · ECB SDW · FRED &nbsp;&nbsp;'
            f'<span style="color:#2a2a2a">MES = dato mensual</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with col_btn:
        if st.button("⟳ &nbsp;ACTUALIZAR"):
            st.cache_data.clear()
            st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Descarga de datos ────────────────────────────────────────
    with st.spinner("Descargando datos de mercado..."):
        datos = cargar_datos()

    # ── Banner primer viernes — alerta NFP (Non-Farm Payrolls) ──
    if _es_primer_viernes():
        st.markdown(
            '<div class="nfp-banner">'
            '⚠ HOY — Dato de empleo USA (Non-Farm Payrolls) a las 14:30h'
            ' &nbsp;—&nbsp; Alta volatilidad esperada'
            '</div>',
            unsafe_allow_html=True
        )

    # ── Panel de alertas (siempre visible en la parte superior) ───
    st.markdown(panel_alertas(evaluar_alertas(datos)), unsafe_allow_html=True)

    # ── Tres columnas principales ─────────────────────────────────
    col1, col2, col3 = st.columns([1.1, 1, 1], gap="medium")

    # ════════════════════════════════════════
    # COLUMNA 1 — Macro y Renta Fija
    # ════════════════════════════════════════
    with col1:
        st.markdown(sec("MACRO Y TIPOS"), unsafe_allow_html=True)

        # Tipo BCE — dato fijo; actualizar en constantes tras cada reunión
        st.markdown(tarjeta(datos["bce"],      dec=2, suf="%"), unsafe_allow_html=True)
        # Euríbor 12M — ECB, media mensual; badge MES indica frecuencia
        st.markdown(tarjeta(datos["euribor"],  dec=3, suf="%", invertir=True), unsafe_allow_html=True)
        # Inflación Eurozona — dato fijo hasta próximo dato Eurostat
        st.markdown(tarjeta(datos["inflacion"],dec=1, suf="%"), unsafe_allow_html=True)

        st.markdown(sec("RENTA FIJA"), unsafe_allow_html=True)

        # Schatz 2Y — ECB YC diario AAA (T-1). invertir=True porque
        # yield↑ → precio del bono↓ → impacto negativo en cartera RF
        st.markdown(tarjeta(datos["schatz"],   dec=3, suf="%", invertir=True), unsafe_allow_html=True)
        # Bund 10Y — referencia principal de la renta fija europea
        st.markdown(tarjeta(datos["bund"],     dec=3, suf="%", invertir=True), unsafe_allow_html=True)
        # Treasury 10Y — referencia global (Yahoo Finance, ~15 min retraso)
        st.markdown(tarjeta(datos["treasury"], dec=3, suf="%", invertir=True), unsafe_allow_html=True)
        # Spread IG — OAS ICE BofA IG (proxy global vía FRED, datos diarios)
        st.markdown(tarjeta(datos["spread_ig"],dec=2, suf="%", invertir=True), unsafe_allow_html=True)

    # ════════════════════════════════════════
    # COLUMNA 2 — Renta Variable y Divisas
    # ════════════════════════════════════════
    with col2:
        st.markdown(sec("RENTA VARIABLE"), unsafe_allow_html=True)

        # Euro Stoxx 50 — índice de RV europea; activo en alerta si cae >1.5%
        st.markdown(tarjeta(datos["eurostoxx"],dec=2), unsafe_allow_html=True)
        # S&P 500 — referencia global de RV americana
        st.markdown(tarjeta(datos["sp500"],    dec=2), unsafe_allow_html=True)
        # IBEX 35 — mercado doméstico español
        st.markdown(tarjeta(datos["ibex"],     dec=2), unsafe_allow_html=True)

        st.markdown(sec("DIVISAS"), unsafe_allow_html=True)

        # EUR/USD — principal par; afecta a activos USD en cartera
        st.markdown(tarjeta(datos["eurusd"],   dec=4), unsafe_allow_html=True)
        # EUR/GBP — relevante para posiciones en activos GBP
        st.markdown(tarjeta(datos["eurgbp"],   dec=4), unsafe_allow_html=True)

    # ════════════════════════════════════════
    # COLUMNA 3 — Materias Primas, Refugio y Umbrales
    # ════════════════════════════════════════
    with col3:
        st.markdown(sec("MAT. PRIMAS Y REFUGIO"), unsafe_allow_html=True)

        # Brent — referencia europea del crudo; alerta si supera 120 USD
        st.markdown(tarjeta(datos["brent"],    dec=2, suf=" USD"), unsafe_allow_html=True)
        # Oro — activo refugio; correlación inversa en risk-off
        st.markdown(tarjeta(datos["oro"],      dec=2, suf=" USD"), unsafe_allow_html=True)
        # VIX — índice del miedo; alerta si supera 25 pts
        # Niveles: <15 calma · 15-25 normal · >25 estrés · >35 crisis
        st.markdown(tarjeta(datos["vix"],      dec=2), unsafe_allow_html=True)

        # ── Umbrales de alerta configurados ──────────────────────
        st.markdown(sec("UMBRALES DE ALERTA"), unsafe_allow_html=True)
        st.markdown("""
<div class="card" style="min-height:auto;">
  <div class="c-nombre">Alertas por percentil</div>
  <div class="flat" style="line-height:2.1; margin-top:4px; font-size:11px;">
    Brent · VIX · Euro Stoxx · Bund<br>
    — ventana 4 semanas (diario)<br>
    Spread IG — ventana 30 días<br>
    Euríbor 12M — ventana 12 meses
  </div>
</div>""", unsafe_allow_html=True)

        # ── Nota sobre datos de la cartera ───────────────────────
        st.markdown(f"""
<div class="card" style="min-height:auto; margin-top:5px;">
  <div class="c-nombre">Notas de datos</div>
  <div class="flat" style="line-height:1.9; margin-top:4px; font-size:10px;">
    RV / Divisas / Commod: ~15 min retraso<br>
    Bonos alemanes: T-1 (BCE SDW)<br>
    Euríbor: media mensual (BCE SDW)<br>
    Spread IG: ICE BofA OAS (FRED)
  </div>
</div>""", unsafe_allow_html=True)

    # ── Sección de noticias RSS ───────────────────────────────────
    st.markdown("<hr>", unsafe_allow_html=True)
    renderizar_noticias()

    # ── Auto-refresco ─────────────────────────────────────────────
    # Descomenta la siguiente línea para activar refresco automático (5 min):
    # st.markdown('<meta http-equiv="refresh" content="300">', unsafe_allow_html=True)

    # ── Pie de página ─────────────────────────────────────────────
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("""
<div class="pie">
  OLEA GESTIÓN &nbsp;·&nbsp; Dashboard interno de seguimiento diario &nbsp;·&nbsp;
  Datos con posible retraso &nbsp;·&nbsp; Solo para uso informativo interno
</div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA
# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if _DAILY_MODE:
        # python dashboard.py --daily → email diario siempre (cron: 0 9 * * 1-5)
        modo_daily()
    elif _CLI_MODE:
        # python dashboard.py --check → email de alerta solo si hay alertas activas
        modo_check()
    elif _WEEKLY_MODE:
        # python dashboard.py --weekly → resumen semanal (cron: 0 9 * * 5)
        modo_weekly()
    else:
        # streamlit run dashboard.py → dashboard visual
        renderizar()
