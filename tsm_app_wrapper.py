import streamlit as st
import pandas as pd
import numpy as np
from plotly.subplots import make_subplots
import plotly.graph_objects as go

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime


@st.cache_data(show_spinner=False)
def load_data_cached(path):
    return load_csv_skip_until_header(path)


# Page title
st.set_page_config(layout="wide")
st.title("PI TSM Coils Analysis Dashboard")

# ============================================================
# CSV FILE UPLOADER SECTION
# ============================================================
DEFAULT_FILE = "0A10000F_2026_05_12_08_37_37_coil.csv"

if "active_file" not in st.session_state:
    st.session_state.active_file = DEFAULT_FILE

uploaded_file = st.file_uploader("Upload new CSV", type=["csv"])

if uploaded_file is not None:
    with open("temp_uploaded.csv", "wb") as f:
        f.write(uploaded_file.getbuffer())

    st.session_state.active_file = "temp_uploaded.csv"
    load_data_cached.clear()   # THIS is what refreshes the plots
    st.success("New file loaded ✔")



    # ============================================================
    # CSV LOADER — BACKWARD COMPATIBLE
    # ============================================================
def load_csv_skip_until_header(path):
    """
    Reads CSV and skips the old calibration block until real header appears.
    Works for both old and new CSV formats.
    """
    required_cols = ["ch0_raw_phase", "ch0_raw_amplitude"]

    with open(path, "r", errors="ignore") as f:
        lines = f.readlines()

    header_index = None
    for i, line in enumerate(lines):
        if all(col in line for col in required_cols):
            header_index = i
            break

    if header_index is None:
        raise RuntimeError(
            "ERROR: Could not find the CSV header containing "
            "ch0_raw_phase and ch0_raw_amplitude."
        )

    # Load CSV starting at the detected header line
    df = pd.read_csv(
        path,
        sep=';',
        on_bad_lines='skip',
        skiprows=header_index
    )

    df.columns = df.columns.str.strip()
    return df


# ============================================================
# HELPERS
# ============================================================
def unwrap_rad(series):
    """unwrap phase and return in radians"""
    arr = np.asarray(series, dtype=float)
    return np.unwrap(arr)


def pct_span(s):
    mn = s.min()
    mx = s.max()
    if mn == 0 or mn is None:
        return 0.0
    return (mx - mn) / mn * 100.0


def phase_delta_rad(series):
    """Return delta phase in radians (max - min)"""
    arr = np.asarray(series, dtype=float)
    return float(arr.max() - arr.min())


def phase_delta_deg(series):
    """Return delta phase in degrees from rad"""
    return phase_delta_rad(series) * 180.0 / np.pi

def add_subplot_annotation(fig, text, row, col, cols_total):
    # Calculate subplot index (Plotly numbers subplots left→right, top→bottom)
    subplot_index = (row - 1) * cols_total + col

    # First subplot uses "x domain", others use "x2 domain", "x3 domain", ...
    if subplot_index == 1:
        xref = "x domain"
        yref = "y domain"
    else:
        xref = f"x{subplot_index} domain"
        yref = f"y{subplot_index} domain"

    fig.add_annotation(
        text=text,
        x=0.01,
        y=1.08,
        xref=xref,
        yref=yref,
        showarrow=False,
        align="left",
        font=dict(size=14)
    )





# ============================================================
# MAIN
# ============================================================

# Backwards-compatible load
df = load_data_cached(st.session_state.active_file)
# df = load_csv_skip_until_header(r"0A100015_2026_05_12_12_42_28_coil.csv")

# ============================================================
# EXTRACT AMPLITUDES
# ============================================================
ch0 = df["ch0_raw_amplitude"]  # RX1
ch1 = df["ch1_raw_amplitude"]  # RX2
ch2 = df["ch2_raw_amplitude"]  # RX3
ch3 = df["ch3_raw_amplitude"]  # RX4
ch4 = df["ch4_raw_amplitude"]  # REF
ch5 = df["ch5_raw_amplitude"]  # ITX

# ============================================================
# EXTRACT PHASES (CSV ALREADY IN RADIANS)
# ============================================================
p0 = unwrap_rad(df["ch0_raw_phase"])
p1 = unwrap_rad(df["ch1_raw_phase"])
p2 = unwrap_rad(df["ch2_raw_phase"])
p3 = unwrap_rad(df["ch3_raw_phase"])
p4 = unwrap_rad(df["ch4_raw_phase"])  # REF
p5 = unwrap_rad(df["ch5_raw_phase"])  # ITX

# ============================================================
# AMPLITUDE RATIOS
# ch4 IS THE REFERENCE COILS
# ch5 IS THE ITX
# ============================================================
rx1_ref = ch0 / ch4
rx2_ref = ch1 / ch4
rx3_ref = ch2 / ch4
rx4_ref = ch3 / ch4

rx1_itx = ch0 / ch5
rx2_itx = ch1 / ch5
rx3_itx = ch2 / ch5
rx4_itx = ch3 / ch5


###############################################################
# SUMMARY TABLE IMPLEMENTATION
def build_summary_table():
    rows = []

    amps = [
        ("RX1 amplitude", ch0),
        ("RX2 amplitude", ch1),
        ("RX3 amplitude", ch2),
        ("RX4 amplitude", ch3),
        ("REF amplitude", ch4),
        ("ITX amplitude", ch5),
    ]

    for name, data in amps:
        rows.append({
            "Signal": name,
            "Amplitude Δ %": round(pct_span(data), 3),
            "Phase Δ rad": round(phase_delta_rad(data), 5),
            "Phase Δ deg": round(phase_delta_deg(data), 2),
        })

    return pd.DataFrame(rows)


summary_df = build_summary_table()

# DOWNLOAD BUTTON
st.dataframe(summary_df, width='stretch')
st.subheader("Download analysis")

csv_bytes = summary_df.to_csv(index=False).encode("utf-8")

st.download_button(
    label="📥 Download summary report",
    data=csv_bytes,
    file_name="tsm_analysis_summary.csv",
    mime="text/csv"
)




# ============================================================
# FIGURE 1: AMPLITUDE NORMALIZED TO REF
# ============================================================
fig_ref = make_subplots(rows=2, cols=2)

pairs_ref = [
    ("RX1/REF (ch0/ch4)", rx1_ref, 1, 1),
    ("RX2/REF (ch1/ch4)", rx2_ref, 1, 2),
    ("RX3/REF (ch2/ch4)", rx3_ref, 2, 1),
    ("RX4/REF (ch3/ch4)", rx4_ref, 2, 2),
]

for title, data, r, c in pairs_ref:
    p = pct_span(data)

    fig_ref.add_trace(
        go.Scatter(y=data, mode="lines", showlegend=False),
        row=r, col=c
    )

    add_subplot_annotation(fig_ref, f"<b>{title}</b><br>Δ={p:.2f}%", r, c, 2)

fig_ref.update_layout(height=650, title="Amplitude vs REF")



# ============================================================
# FIGURE 2: AMPLITUDE NORMALIZED TO ITX
# ============================================================
fig_itx = make_subplots(rows=2, cols=2)

pairs_itx = [
    ("RX1/ITX (ch0/ch5)", rx1_itx, 1, 1),
    ("RX2/ITX (ch1/ch5)", rx2_itx, 1, 2),
    ("RX3/ITX (ch2/ch5)", rx3_itx, 2, 1),
    ("RX4/ITX (ch3/ch5)", rx4_itx, 2, 2),
]

for title, data, r, c in pairs_itx:
    p = pct_span(data)

    fig_itx.add_trace(
        go.Scatter(y=data, mode="lines", showlegend=False),
        row=r, col=c
    )

    add_subplot_annotation(fig_itx, f"<b>{title}</b><br>Δ={p:.2f}%", r, c, 2)

fig_itx.update_layout(height=650, title="Amplitude vs ITX")


# ============================================================
# FIGURE 3: RAW AMPLITUDES
# ============================================================

fig_amp = make_subplots(rows=2, cols=3)

amps = [
    ("RX1 amplitude", ch0, 1,1),
    ("RX2 amplitude", ch1, 1,2),
    ("RX3 amplitude", ch2, 1,3),
    ("RX4 amplitude", ch3, 2,1),
    ("REF amplitude", ch4, 2,2),
    ("ITX amplitude", ch5, 2,3),
]

for title, data, r, c in amps:
    p = pct_span(data)

    fig_amp.add_trace(go.Scatter(y=data, mode="lines", showlegend=False),row=r, col=c)

    add_subplot_annotation(fig_amp, f"<b>{title}</b><br>Δ = {p:.2f} %", r, c, 3)

fig_amp.update_layout(height=750, title="Raw Amplitudes")


# ============================================================
# FIGURE 4: RAW PHASES (rad)
# ============================================================

fig_phase_raw = make_subplots(rows=2, cols=3)

phases = [
    ("RX1 phase", p0, 1, 1),
    ("RX2 phase", p1, 1, 2),
    ("RX3 phase", p2, 1, 3),
    ("RX4 phase", p3, 2, 1),
    ("REF phase", p4, 2, 2),
    ("ITX phase", p5, 2, 3),
]

for title, data, r, c in phases:
    drad = phase_delta_rad(data)
    ddeg = phase_delta_deg(data)

    fig_phase_raw.add_trace(
        go.Scatter(y=data, mode="lines", showlegend=False),
        row=r, col=c
    )

    add_subplot_annotation(
        fig_phase_raw,
        f"<b>{title}</b><br>Δ={drad:.5f} rad | {ddeg:.2f}°",
        r, c, 3
    )

fig_phase_raw.update_layout(height=750, title="Raw Phases")


# ============================================================
# FIGURE 5: PHASE DIFF VS REF (rad)
# ============================================================
fig_phase_ref = make_subplots(rows=2, cols=2)

pairs_phase_ref = [
    ("RX1 - REF", p0 - p4, 1, 1),
    ("RX2 - REF", p1 - p4, 1, 2),
    ("RX3 - REF", p2 - p4, 2, 1),
    ("RX4 - REF", p3 - p4, 2, 2),
]

for title, data, r, c in pairs_phase_ref:
    drad = phase_delta_rad(data)
    ddeg = phase_delta_deg(data)

    fig_phase_ref.add_trace(go.Scatter(y=data, mode="lines", showlegend=False), row=r, col=c)
    add_subplot_annotation(fig_phase_ref, f"<b>{title}</b><br>Δ={drad:.5f} rad | {ddeg:.2f}°", r, c, 2)

fig_phase_ref.update_layout(height=650, title="Phase vs REF")


# ============================================================
# FIGURE 6: PHASE DIFF VS ITX (rad)
# ============================================================
fig_phase_itx = make_subplots(rows=2, cols=2)

pairs_phase_itx = [
    ("RX1 - ITX", p0 - p5, 1, 1),
    ("RX2 - ITX", p1 - p5, 1, 2),
    ("RX3 - ITX", p2 - p5, 2, 1),
    ("RX4 - ITX", p3 - p5, 2, 2),
]

for title, data, r, c in pairs_phase_itx:
    drad = phase_delta_rad(data)
    ddeg = phase_delta_deg(data)

    fig_phase_itx.add_trace(go.Scatter(y=data, mode="lines", showlegend=False), row=r, col=c)
    add_subplot_annotation(fig_phase_itx, f"<b>{title}</b><br>Δ={drad:.5f} rad | {ddeg:.2f}°", r, c, 2)

fig_phase_itx.update_layout(height=650, title="Phase vs ITX")



# ============================================================
# Convert matplotlib figures → Plotly and display
# ============================================================

st.subheader("Amplitude vs REF")
st.plotly_chart(fig_ref, width="stretch")

st.subheader("Amplitude vs ITX")
st.plotly_chart(fig_itx, width="stretch")

st.subheader("Raw Amplitudes")
st.plotly_chart(fig_amp, width="stretch")

st.subheader("Raw Phases")
st.plotly_chart(fig_phase_raw, width="stretch")

st.subheader("Phase vs REF")
st.plotly_chart(fig_phase_ref, width="stretch")

st.subheader("Phase vs ITX")
st.plotly_chart(fig_phase_itx, width="stretch")




# PDF DOWNLOADER
def create_pdf_report(summary_df, filename):
    pdf_path = "tsm_analysis_report.pdf"

    doc = SimpleDocTemplate(pdf_path)
    styles = getSampleStyleSheet()
    content = []

    # Title
    content.append(Paragraph("TSM Coil Analysis Report", styles['Title']))
    content.append(Spacer(1,12))

    # Metadata
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    content.append(Paragraph(f"<b>Dataset:</b> {filename}", styles['Normal']))
    content.append(Paragraph(f"<b>Generated:</b> {now}", styles['Normal']))
    content.append(Spacer(1,12))

    # Convert dataframe → table
    table_data = [summary_df.columns.tolist()] + summary_df.values.tolist()
    table = Table(table_data)
    content.append(table)

    doc.build(content)

    return pdf_path


# Add the download button in Streamlit
st.subheader("Export report")
pdf_file = create_pdf_report(summary_df, st.session_state.active_file)

with open(pdf_file, "rb") as f:
    st.download_button(
        label="📄 Download PDF report",
        data=f,
        file_name="tsm_analysis_report.pdf",
        mime="application/pdf"
    )