# app.py -- Value Investing Screener (Streamlit)
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="Value Investing Screener", layout="wide")
st.title("📊 Value Investing Screener")

# ---- Sidebar settings ----
st.sidebar.header("Screener Settings")
tickers_input = st.sidebar.text_area(
    "Enter tickers (comma separated, e.g. AAPL,MSFT,INTC)",
    value="AAPL,MSFT,INTC,IBM,CSCO,ORCL,TXN,AVGO,QCOM,MU"
)

pe_max = st.sidebar.number_input("Max P/E (PE <= )", value=15.0, step=1.0)
pb_max = st.sidebar.number_input("Max P/B (PB <= )", value=3.0, step=0.1)
de_max = st.sidebar.number_input("Max Debt/Equity (<=)", value=100.0, step=1.0)
div_yield_min = st.sidebar.number_input("Min Dividend Yield (%) (>=)", value=0.0, step=0.1)
fcf_yield_min = st.sidebar.number_input("Min FCF Yield (%) (>=)", value=0.0, step=0.1)

# Graham parameters
st.sidebar.subheader("Graham Parameters")
est_growth = st.sidebar.number_input("Estimated annual growth rate g (%)", value=5.0, step=0.5)
aaa_rate = st.sidebar.number_input("AAA bond yield (%) (discount baseline)", value=4.0, step=0.1)
min_mos = st.sidebar.number_input("Minimum Margin of Safety (%)", value=20.0, step=1.0)

run_button = st.sidebar.button("Run Screener")

# parse tickers
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

@st.cache_data(ttl=3600)
def fetch_yf_info(ticker):
    tk = yf.Ticker(ticker)
    info = {}
    try:
        raw = tk.info
    except Exception:
        raw = {}
    price = None
    try:
        hist = tk.history(period="1d")
        if not hist.empty:
            price = float(hist["Close"].iloc[-1])
    except:
        price = None
    info['raw'] = raw
    info['price'] = price
    return info

def compute_metrics(ticker, info_raw, price, est_growth, aaa_rate):
    r = {}
    ri = info_raw.get('raw', {})
    r['Ticker'] = ticker
    r['Price (USD)'] = price
    r['P/E'] = ri.get('trailingPE', None)
    r['P/B'] = ri.get('priceToBook', None)
    try:
        dte = ri.get('debtToEquity', None)
        if dte is not None:
            dte = float(dte)
    except:
        dte = None
    r['Debt/Equity'] = dte
    dy = ri.get('dividendYield', None)
    r['Dividend Yield (%)'] = None if dy is None else float(dy) * 100
    fcf = ri.get('freeCashflow', None)
    r['FreeCashflow (USD)'] = fcf
    mcap = ri.get('marketCap', None)
    r['MarketCap (USD)'] = mcap
    try:
        if fcf is not None and mcap:
            r['FCF Yield (%)'] = float(fcf) / float(mcap) * 100
        else:
            r['FCF Yield (%)'] = None
    except:
        r['FCF Yield (%)'] = None
    eps = ri.get('trailingEps', None)
    try:
        if eps is not None and aaa_rate and aaa_rate > 0:
            graham = eps * (8.5 + 2 * (est_growth / 100.0)) * 4.4 / (aaa_rate / 100.0)
            r['Graham Value (est. USD)'] = graham
            if price and graham:
                mos = (graham - price) / graham * 100
                r['Margin of Safety (%)'] = mos
            else:
                r['Margin of Safety (%)'] = None
        else:
            r['Graham Value (est. USD)'] = None
            r['Margin of Safety (%)'] = None
    except Exception:
        r['Graham Value (est. USD)'] = None
        r['Margin of Safety (%)'] = None
    r['Sector'] = ri.get('sector', None)
    r['Industry'] = ri.get('industry', None)
    return r

if run_button:
    if not tickers:
        st.error("Please enter at least one ticker on the left.")
    else:
        rows = []
        total = len(tickers)
        progress = st.progress(0)
        for i, tk in enumerate(tickers):
            try:
                info = fetch_yf_info(tk)
                row = compute_metrics(tk, info, info.get('price'), est_growth, aaa_rate)
                rows.append(row)
            except Exception:
                rows.append({'Ticker': tk, 'Price (USD)': None})
            progress.progress((i+1)/total)
        df = pd.DataFrame(rows)
        st.subheader("Raw Results")
        st.dataframe(df)

        # apply filters
        mask = pd.Series([True] * len(df))
        if pe_max is not None:
            mask = mask & (df['P/E'].fillna(np.inf) <= pe_max)
        if pb_max is not None:
            mask = mask & (df['P/B'].fillna(np.inf) <= pb_max)
        if de_max is not None:
            mask = mask & (df['Debt/Equity'].fillna(np.inf) <= de_max)
        if div_yield_min is not None:
            mask = mask & (df['Dividend Yield (%)'].fillna(-np.inf) >= div_yield_min)
        if fcf_yield_min is not None:
            mask = mask & (df['FCF Yield (%)'].fillna(-np.inf) >= fcf_yield_min)
        if min_mos is not None:
            mask = mask & (df['Margin of Safety (%)'].fillna(-np.inf) >= min_mos)

        df_filtered = df[mask].copy()
        st.subheader(f"Filtered Results (matching {len(df_filtered)} / {len(df)})")
        st.dataframe(df_filtered)

        # export CSV / Excel
        def to_excel_bytes(df_in):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_in.to_excel(writer, index=False, sheet_name='Screener')
            return output.getvalue()

        csv = df_filtered.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", data=csv, file_name="screener.csv", mime="text/csv")
        excel_bytes = to_excel_bytes(df_filtered)
        st.download_button("Download Excel", data=excel_bytes,
                           file_name="screener.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
