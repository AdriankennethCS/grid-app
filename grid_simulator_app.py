import json
from pathlib import Path
from textwrap import dedent

import numpy as np
import pandas as pd
import streamlit as st

# Force light styling regardless of dark browser themes
st.markdown("""
    <style>
    table {
        background-color: white !important;
        color: black !important;
    }
    th, td {
        background-color: white !important;
        color: black !important;
    }
    .stDataFrame div {
        background-color: white !important;
        color: black !important;
        font-family: monospace;
        text-align: right;
    }
    </style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# Template storage
# ------------------------------------------------------------------
TEMPLATE_PATH = Path(__file__).with_name("grid_templates.json")

def load_templates() -> dict:
    if TEMPLATE_PATH.exists():
        try:
            return json.loads(TEMPLATE_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return {}

def save_templates(tpls: dict):
    TEMPLATE_PATH.write_text(json.dumps(tpls, indent=2))

# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------
st.set_page_config(page_title="Crypto Grid‑Bot Calculator", page_icon="📈", layout="centered")

# ------------------------------------------------------------------
# Table hover styling
# ------------------------------------------------------------------
st.markdown(dedent("""
    <style>
        .dataframe tbody tr:hover {background-color:#e8f0ff !important;}
        .stDataFrame {overflow-x:auto;}
    </style>
"""), unsafe_allow_html=True)

# ------------------------------------------------------------------
# Color palette
# ------------------------------------------------------------------
POS_CLR = "#2a9d8f"   # Green
NEG_TXT = "#e63946"   # Red text
NEG_BG  = "#ffecec"   # Red background
ROW_EVEN = "#ffffff"
ROW_ODD = "#f7f7f7"

def style_pos_neg(val: float) -> str:
    if val < 0:
        return f"color:{NEG_TXT};"
    if val > 0:
        return f"color:{POS_CLR};"
    return ""

def style_drawdown(val: float) -> str:
    return f"background-color:{NEG_BG}; color:{NEG_TXT};" if val < 0 else ""

# ------------------------------------------------------------------
# Core calc
# ------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def build_grid(min_px: float, max_px: float, start_px: float, levels: int, usdt_slice: float,
               leverage: int, price_dp: int):
    intervals = levels - 1
    raw_gap = (max_px - min_px) / intervals
    raw_prices = max_px - np.arange(levels) * raw_gap
    prices = np.round(raw_prices, price_dp)

    qty = np.floor_divide(usdt_slice / prices, 10) * 10
    qty = np.where(qty == 0, 10, qty)
    acc_qty = qty.cumsum()
    vwap = np.round((qty * prices).cumsum() / acc_qty, price_dp)

    unreal = np.round((prices - start_px) * acc_qty, 2)

    draw = np.zeros_like(prices)
    for i in range(1, levels):
        draw[i] = draw[i-1] + (prices[i-1] - prices[i]) * acc_qty[i-1]
    draw = -np.round(draw, 2)

    m_slice = np.round(usdt_slice / leverage, 2)
    acc_margin = np.round(m_slice * np.arange(1, levels + 1), 2)
    notional = np.round(usdt_slice * np.arange(1, levels + 1), 2)

    df = pd.DataFrame({
        "Level": np.arange(1, levels + 1),
        "Price": prices,
        "Qty": qty,
        "Acc Qty": acc_qty,
        "Avg Price": vwap,
        "Unrealised": unreal,
        "Drawdown": draw,
        "PnL": unreal,
        "Margin per lvl": m_slice,
        "Acc Margin": acc_margin,
        "Nominal (lev)": notional,
    })
    return df, raw_gap

# ------------------------------------------------------------------
# UI
# ------------------------------------------------------------------

tpls = load_templates()

def template_to_kwargs(d):
    return {
        "px_top": d["max_price"],
        "px_bottom": d["min_price"],
        "spot": d["start_price"],
        "levels": d["levels"],
        "slice_val": d["usdt_slice"],
        "leverage": d["leverage"],
        "price_dp": d.get("price_dp", 6),
        "gap_dp": d.get("gap_dp", 8),
    }

st.title("📈 Crypto Grid‑Bot Calculator – with Templates")

with st.sidebar:
    st.header("Templates")
    tpl_names = list(tpls.keys())
    selected_tpl = st.selectbox("Load template", ["<None>"] + tpl_names)

    kwargs = template_to_kwargs(tpls[selected_tpl]) if selected_tpl != "<None>" else {}

    st.header("Parameters")
    px_top = st.number_input("Max price", value=kwargs.get("px_top", 7.0), min_value=0.0, format="%f")
    px_bottom = st.number_input("Min price", value=kwargs.get("px_bottom", 1.0), min_value=0.0, format="%f")
    spot = st.number_input("Start price (spot)", value=kwargs.get("spot", 2.7916), min_value=0.0, format="%f")
    levels = st.number_input("Levels (rows)", value=kwargs.get("levels", 124), min_value=2, max_value=200, step=1)
    slice_val = st.number_input("USDT per level", value=kwargs.get("slice_val", 203.252), min_value=0.0, format="%f")
    leverage = st.number_input("Leverage", value=kwargs.get("leverage", 50), min_value=1, step=1)
    price_dp = st.number_input("Price decimals", value=kwargs.get("price_dp", 6), min_value=2, max_value=10, step=1)
    gap_dp = st.number_input("Gap decimals (display)", value=kwargs.get("gap_dp", 8), min_value=3, max_value=10, step=1)

    st.caption("Exactly *Levels* rows (1…N). Qty blocks of 10 like the workbook.")

    new_tpl_name = st.text_input("Save current as template (name)")
    if st.button("Save template") and new_tpl_name:
        tpls[new_tpl_name] = {
            "max_price": px_top,
            "min_price": px_bottom,
            "start_price": spot,
            "levels": levels,
            "usdt_slice": slice_val,
            "leverage": leverage,
            "price_dp": price_dp,
            "gap_dp": gap_dp,
        }
        save_templates(tpls)
        st.success(f"Template '{new_tpl_name}' saved – reload sidebar to see it.")

if px_top <= px_bottom:
    st.error("Max price must be > Min price")
    st.stop()

if st.button("Calculate grid", type="primary"):
    df, raw_gap = build_grid(px_bottom, px_top, spot, levels, slice_val, leverage, price_dp)

    zebra = pd.DataFrame(
        [[f"background-color:{ROW_ODD if i % 2 else ROW_EVEN};" for _ in df.columns] for i in range(len(df))],
        index=df.index, columns=df.columns)

    styled = (df.style
        .set_properties(**{'background-color': 'white', 'color': 'black', 'border-color': 'black'})
        .apply(lambda _: zebra, axis=None)
        .applymap(style_pos_neg, subset=["Unrealised", "PnL"])
        .applymap(style_drawdown, subset=["Drawdown"])
    )

    st.subheader("Grid Table – matches Excel row/qty/draw‑down")
    st.markdown(f"Gap: **{raw_gap:.{gap_dp}f}**  • Rows: {levels}  • Slice: {slice_val} USDT")
    st.dataframe(styled, use_container_width=True, hide_index=True)

    st.download_button("Download CSV", df.to_csv(index=False).encode(), "grid_table.csv", "text/csv")
    st.caption("Templates stored in 'grid_templates.json'. Pale‑red Draw‑down, red/green PnL.")

