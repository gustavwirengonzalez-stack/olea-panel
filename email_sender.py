#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Email diario de mercados — Olea Gestión.
Script autónomo sin dependencias de Streamlit.
Uso: python email_sender.py
"""

import os
import sys
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from io import StringIO

import requests
import pandas as pd

try:
    import yfinance as yf
    _YF_OK = True
except ImportError:
    _YF_OK = False

# ─────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────

TIPO_BCE_PCT      = 2.00
INFLACION_EUR_PCT = 3.0

UMBRAL_BRENT_USD       = 120.0
UMBRAL_VIX             = 25.0
UMBRAL_EURIBOR_CAMBIO  = 0.05
UMBRAL_EUROSTOXX_CAIDA = -1.5

EMAIL_REMITENTE     = os.environ.get("EMAIL_REMITENTE", "")
EMAIL_PASSWORD      = os.environ.get("EMAIL_PASSWORD",  "")
EMAIL_DESTINATARIOS = [
    "gustavwirengonzalez@gmail.com",
    "gustav.wiren@studenti.luiss.it",
]

# ─────────────────────────────────────────────────────────────────
# OBTENCIÓN DE DATOS
# ─────────────────────────────────────────────────────────────────

def _yf(ticker: str, nombre: str) -> dict:
    base = {"nombre": nombre, "ok": False,
            "valor": None, "cambio_abs": None, "cambio_pct": None}
    if not _YF_OK:
        return base
    try:
        info   = yf.Ticker(ticker).fast_info
        precio = info.last_price
        previo = info.previous_close
        if not precio:
            hist = yf.Ticker(ticker).history(period="5d", interval="1d").dropna(subset=["Close"])
            if len(hist) >= 2:
                precio, previo = float(hist["Close"].iloc[-1]), float(hist["Close"].iloc[-2])
            elif len(hist) == 1:
                precio = previo = float(hist["Close"].iloc[-1])
        if precio is None:
            return base
        previo     = previo or precio
        cambio_abs = float(precio) - float(previo)
        cambio_pct = (cambio_abs / float(previo) * 100) if previo else 0.0
        return {**base, "ok": True, "valor": float(precio),
                "cambio_abs": cambio_abs, "cambio_pct": cambio_pct}
    except Exception:
        return base


def _ecb_yc(plazo: str, nombre: str) -> dict:
    base = {"nombre": nombre, "ok": False,
            "valor": None, "cambio_abs": None, "cambio_pct": None}
    try:
        key = f"B.U2.EUR.4F.G_N_A.SV_C_YM.{plazo}"
        url = (f"https://data-api.ecb.europa.eu/service/data/YC/{key}"
               f"?lastNObservations=5")
        r = requests.get(url, timeout=12,
                         headers={"Accept": "application/vnd.sdmx.data+json;version=1.0.0-wd"})
        r.raise_for_status()
        obs = list(r.json()["dataSets"][0]["series"].values())[0]["observations"]
        idx = sorted(obs.keys(), key=lambda x: int(x))
        if not idx:
            return base
        v_actual = float(obs[idx[-1]][0])
        v_previo = float(obs[idx[-2]][0]) if len(idx) >= 2 else v_actual
        cambio_abs = v_actual - v_previo
        cambio_pct = (cambio_abs / abs(v_previo) * 100) if v_previo else 0.0
        return {**base, "ok": True, "valor": v_actual,
                "cambio_abs": cambio_abs, "cambio_pct": cambio_pct}
    except Exception:
        return base


def _ecb_euribor() -> dict:
    base = {"nombre": "Euríbor 12M", "ok": False,
            "valor": None, "cambio_abs": None, "cambio_pct": None}
    try:
        url = ("https://data-api.ecb.europa.eu/service/data/FM/"
               "M.U2.EUR.RT.MM.EURIBOR1YD_.HSTA?lastNObservations=5")
        r = requests.get(url, timeout=12,
                         headers={"Accept": "application/vnd.sdmx.data+json;version=1.0.0-wd"})
        r.raise_for_status()
        obs = list(r.json()["dataSets"][0]["series"].values())[0]["observations"]
        idx = sorted(obs.keys(), key=lambda x: int(x))
        if not idx:
            return base
        v_actual = float(obs[idx[-1]][0])
        v_previo = float(obs[idx[-2]][0]) if len(idx) >= 2 else v_actual
        cambio_abs = v_actual - v_previo
        cambio_pct = (cambio_abs / abs(v_previo) * 100) if v_previo else 0.0
        return {**base, "ok": True, "valor": v_actual,
                "cambio_abs": cambio_abs, "cambio_pct": cambio_pct}
    except Exception:
        return base


def _fred_ig_spread() -> dict:
    base = {"nombre": "Spread IG Créd.", "ok": False,
            "valor": None, "cambio_abs": None, "cambio_pct": None}
    try:
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLC0A0CM"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        df = pd.read_csv(StringIO(r.text), names=["fecha", "valor"], skiprows=1)
        df = df[df["valor"] != "."].copy()
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce").dropna()
        df = df.dropna(subset=["valor"])
        if len(df) < 2:
            return base
        v_actual = float(df["valor"].iloc[-1])
        v_previo = float(df["valor"].iloc[-2])
        cambio_abs = v_actual - v_previo
        cambio_pct = (cambio_abs / abs(v_previo) * 100) if v_previo else 0.0
        return {**base, "ok": True, "valor": v_actual,
                "cambio_abs": cambio_abs, "cambio_pct": cambio_pct}
    except Exception:
        return base


def cargar_datos() -> dict:
    return {
        "bce":      {"nombre": "Tipo BCE",          "ok": True, "valor": TIPO_BCE_PCT,      "cambio_abs": 0.0, "cambio_pct": 0.0},
        "inflacion":{"nombre": "Inflación Eurozona", "ok": True, "valor": INFLACION_EUR_PCT, "cambio_abs": 0.0, "cambio_pct": 0.0},
        "euribor":  _ecb_euribor(),
        "bund":     _ecb_yc("SR_10Y", "Bund 10Y"),
        "treasury": _yf("^TNX",      "Treasury 10Y"),
        "eurostoxx":_yf("^STOXX50E", "Euro Stoxx 50"),
        "sp500":    _yf("^GSPC",     "S&P 500"),
        "brent":    _yf("BZ=F",      "Petróleo Brent"),
        "oro":      _yf("GC=F",      "Oro"),
        "vix":      _yf("^VIX",      "VIX"),
        "eurusd":   _yf("EURUSD=X",  "EUR / USD"),
    }

# ─────────────────────────────────────────────────────────────────
# ALERTAS
# ─────────────────────────────────────────────────────────────────

def evaluar_alertas(d: dict) -> list:
    alertas = []
    b = d.get("brent", {})
    if b.get("ok") and b.get("valor") and b["valor"] > UMBRAL_BRENT_USD:
        alertas.append(f"BRENT  {b['valor']:.2f} USD — Supera umbral de {UMBRAL_BRENT_USD:.0f} USD")
    v = d.get("vix", {})
    if v.get("ok") and v.get("valor") and v["valor"] > UMBRAL_VIX:
        alertas.append(f"VIX  {v['valor']:.2f} pts — Volatilidad elevada, umbral {UMBRAL_VIX:.0f}")
    e = d.get("euribor", {})
    if e.get("ok") and e.get("cambio_abs") and e["cambio_abs"] > UMBRAL_EURIBOR_CAMBIO:
        alertas.append(f"EURÍBOR 12M  +{e['cambio_abs']:.4f}% MoM — Subida superior a {UMBRAL_EURIBOR_CAMBIO}%")
    es = d.get("eurostoxx", {})
    if es.get("ok") and es.get("cambio_pct") and es["cambio_pct"] < UMBRAL_EUROSTOXX_CAIDA:
        alertas.append(f"EURO STOXX 50  {es['cambio_pct']:.2f}% en el día — Caída superior al {abs(UMBRAL_EUROSTOXX_CAIDA):.1f}%")
    return alertas


def _es_primer_viernes() -> bool:
    hoy = datetime.now().date()
    return hoy.weekday() == 4 and hoy.day <= 7

# ─────────────────────────────────────────────────────────────────
# CONSTRUCCIÓN DEL EMAIL
# ─────────────────────────────────────────────────────────────────

def _fila(etiqueta: str, d: dict, dec: int = 2, suf: str = "") -> str:
    if not d.get("ok") or d.get("valor") is None:
        return f"  {'  ' + etiqueta:<24} N/D"
    v     = d["valor"]
    v_str = f"{v:,.{dec}f}{suf}" if abs(v) >= 10_000 else f"{v:.{dec}f}{suf}"
    ca, cp = d.get("cambio_abs"), d.get("cambio_pct")
    if ca is not None and cp is not None:
        signo = "+" if ca >= 0 else ""
        chg   = f"  {signo}{ca:.{dec}f} ({signo}{cp:.2f}%)"
    else:
        chg = ""
    return f"  {'  ' + etiqueta:<24} {v_str:<16}{chg}"


def construir_cuerpo(alertas: list, datos: dict) -> str:
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

    if _es_primer_viernes():
        lineas += [
            "  ⚠  HOY — Dato de empleo USA (Non-Farm Payrolls) a las 14:30h",
            "     Alta volatilidad esperada en la apertura americana.",
            "",
        ]

    if alertas:
        lineas += [f"  ⚠  ALERTAS ACTIVAS ({len(alertas)})", sep_simple]
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

    lineas += ["  DATOS CLAVE DEL DÍA", sep_simple]
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

# ─────────────────────────────────────────────────────────────────
# ENVÍO
# ─────────────────────────────────────────────────────────────────

def enviar_email(alertas: list, datos: dict) -> bool:
    if not EMAIL_REMITENTE or not EMAIL_PASSWORD:
        print("ERROR: EMAIL_REMITENTE o EMAIL_PASSWORD no configurados en variables de entorno.")
        return False

    fecha  = datetime.now().strftime("%d/%m/%Y")
    asunto = f"📊 MERCADOS HOY — {fecha}"
    cuerpo = construir_cuerpo(alertas, datos)

    try:
        msg            = MIMEMultipart()
        msg["From"]    = EMAIL_REMITENTE
        msg["To"]      = ", ".join(EMAIL_DESTINATARIOS)
        msg["Subject"] = asunto
        msg.attach(MIMEText(cuerpo, "plain", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
            servidor.login(EMAIL_REMITENTE, EMAIL_PASSWORD)
            servidor.sendmail(EMAIL_REMITENTE, EMAIL_DESTINATARIOS, msg.as_string())

        print(f"✔ Email enviado a: {', '.join(EMAIL_DESTINATARIOS)}")
        return True

    except smtplib.SMTPAuthenticationError:
        print("ERROR: Autenticación SMTP fallida. Verifica EMAIL_REMITENTE y EMAIL_PASSWORD.")
        return False
    except Exception as e:
        print(f"ERROR al enviar el email: {e}")
        return False

# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
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
        sys.exit(1)

    if alertas:
        print(f"\n  ⚠  {len(alertas)} alerta(s) activa(s):")
        for a in alertas:
            print(f"     ▮  {a}")
    else:
        print("\n  ✔ Sin alertas — todos los indicadores dentro del rango normal.")

    print("\n  Enviando email...")
    ok = enviar_email(alertas, datos)
    print(sep)
    sys.exit(0 if ok else 1)
