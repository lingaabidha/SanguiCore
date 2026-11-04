import streamlit as st
from datetime import datetime

from utils import (
    is_live_mode,
    get_reference_date,
    get_data_date,
    all_batches_expired_today,
)

st.set_page_config(
    page_title="SanguiCore",
    page_icon="🩸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------------------------
# GLOBAL STYLING
# Background/base theme/toolbar come from .streamlit/config.toml. This CSS
# block implements the approved design-freeze system: glass cards, the AI
# insight ribbon, the Decision Engine teaser treatment, a floating assistant
# chip (shown on every page), and subtle fade-up motion on load.
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600&display=swap');

:root {
    --bp-ink: #111111;
    --bp-muted: #8a7a7c;
    --bp-border: #E5E7EB;
    --bp-red: #C41E3A;
    --bp-dark-red: #8B0000;
    --bp-green: #16A34A;
    --bp-amber: #B8860B;
    --bp-teal: #0B6E7F;
    --bp-radius: 16px;
}

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

@keyframes bpFadeUp {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
}
.bp-anim { animation: bpFadeUp .5s ease both; }

.bp-glass {
    background: rgba(255,255,255,0.72);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border: 1px solid rgba(255,255,255,0.6);
    box-shadow: 0 8px 28px rgba(17,17,17,0.06);
    border-radius: var(--bp-radius);
}

/* Glass-card sections built with st.container(key="glasscard_...") so the
   title, chart/table/filters and card background are real DOM children of
   one wrapper -- unlike two separate st.markdown() calls for the opening
   and closing <div>, which Streamlit renders as two disconnected fragments
   and left the title/content sitting outside (below) the card. */
div[class*="st-key-glasscard"] {
    background: rgba(255,255,255,0.72);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border: 1px solid rgba(255,255,255,0.6);
    box-shadow: 0 8px 28px rgba(17,17,17,0.06);
    border-radius: var(--bp-radius);
    padding: 1rem 1.1rem;
    margin-bottom: 1rem;
    animation: bpFadeUp .5s ease both;
}

/* ===== Top bar ===== */
.bp-topbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.1rem;
}
.bp-topbar-left { display: flex; align-items: center; gap: 10px; }
.bp-topbar-logo {
    width: 34px; height: 34px; border-radius: 10px;
    background: #111; display: flex; align-items: center; justify-content: center;
    font-size: 16px;
}
.bp-topbar-title {
    margin: 0; font-family: 'Space Grotesk', sans-serif;
    font-weight: 700; font-size: 17px; color: var(--bp-ink);
}
.bp-topbar-sub { margin: 0; font-size: 11px; color: var(--bp-muted); }

/* ===== AI insight ribbon ===== */
.bp-ai-ribbon {
    padding: 0.9rem 1.1rem;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 12px;
}
.bp-ai-icon {
    width: 30px; height: 30px; border-radius: 9px; flex-shrink: 0;
    background: linear-gradient(135deg, var(--bp-red), var(--bp-dark-red));
    display: flex; align-items: center; justify-content: center; font-size: 14px;
}
.bp-ai-ribbon p { margin: 0; font-size: 13.5px; color: var(--bp-ink); line-height: 1.4; }

/* ===== KPI glass cards ===== */
.bp-kpi-card { padding: 0.9rem 1.1rem; }
.bp-kpi-label { margin: 0; font-size: 11px; color: var(--bp-muted); }
.bp-kpi-value {
    margin: 4px 0 0; font-family: 'IBM Plex Mono', monospace;
    font-size: 22px; font-weight: 600; color: var(--bp-ink);
}
.bp-kpi-sub { margin: 0; font-size: 11px; font-weight: 600; }
.bp-green { color: var(--bp-green); }
.bp-red { color: var(--bp-red); }
.bp-amber { color: var(--bp-amber); }
.bp-teal { color: var(--bp-teal); }

.bp-section-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.05rem;
    font-weight: 600;
    margin: 0 0 0.6rem 0;
    color: var(--bp-ink);
}

/* ===== Inventory chips ===== */
.bp-chip {
    font-size: 11px;
    border-radius: 8px;
    padding: 4px 9px;
    display: inline-block;
}

/* ===== Decision Engine teaser ===== */
.bp-decision-teaser {
    background: #111;
    border-radius: 18px;
    padding: 1.1rem 1.3rem;
    position: relative;
    overflow: hidden;
}
.bp-decision-label {
    margin: 0; font-size: 11px; color: #e8a0ab; font-weight: 600;
    letter-spacing: .04em; text-transform: uppercase; position: relative;
}
.bp-decision-title {
    margin: 6px 0 4px; font-size: 15px; color: #fff; font-weight: 600; position: relative;
}
.bp-decision-sub {
    margin: 0 0 4px; font-size: 12px; color: #c7c7c7; position: relative;
}

/* ===== Signature pulse-line motif — replaces generic glow/gradient effects
   used everywhere else. This is the one visual element unique to
   SanguiCore: a drawing heartbeat line, tied directly to the name. ===== */
@keyframes bpPulseDraw {
    0%   { stroke-dashoffset: 240; }
    70%  { stroke-dashoffset: 0; }
    100% { stroke-dashoffset: 0; }
}
.bp-pulse-line {
    position: absolute;
    bottom: 6px;
    right: 0;
    opacity: 0.4;
    pointer-events: none;
}
.bp-pulse-line path {
    stroke-dasharray: 240;
    animation: bpPulseDraw 2.8s ease-in-out infinite;
}

.bp-placeholder {
    background-color: rgba(255,255,255,0.6);
    border: 1px dashed var(--bp-border);
    border-radius: 14px;
    padding: 1.4rem 1.6rem;
    color: var(--bp-muted);
}

/* ===== Page hero — dark header band used by feature pages (Decision
   Engine, Emergency Mode). Same design language as the Decision Engine
   teaser on Mission Control: black card, red accent, pulse-line motif. ===== */
.bp-hero {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    background: #111111;
    border-radius: 18px;
    padding: 1.3rem 1.5rem;
    margin-bottom: 1.1rem;
    position: relative;
    overflow: hidden;
}
.bp-hero-left h1 {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    font-size: 1.5rem;
    color: #ffffff;
    margin: 0 0 6px;
    position: relative;
}
.bp-hero-left h1 span { color: var(--bp-red); }
.bp-hero-left p {
    margin: 0;
    font-size: 13px;
    color: #c7c7c7;
    max-width: 560px;
    position: relative;
}
.bp-status-card {
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 14px;
    padding: 0.8rem 1.2rem;
    text-align: center;
    min-width: 110px;
    flex-shrink: 0;
    position: relative;
}
.bp-status-card h2 {
    margin: 0;
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    font-size: 1.3rem;
    color: #ffffff;
}
.bp-status-card p {
    margin: 2px 0 8px;
    font-size: 11px;
    color: #c7c7c7;
}
.bp-hero-badge {
    display: inline-block;
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: .02em;
    color: #7CFFB2;
    background: rgba(124,255,178,.12);
    border: 1px solid rgba(124,255,178,.25);
    border-radius: 20px;
    padding: 3px 10px;
}
.bp-hero-badge.bp-hero-badge-amber {
    color: #ffd27c;
    background: rgba(255,210,124,.12);
    border-color: rgba(255,210,124,.25);
}
.bp-hero-badge.bp-hero-badge-red {
    color: #ff9aa6;
    background: rgba(255,154,166,.12);
    border-color: rgba(255,154,166,.25);
}

[data-testid="stSidebar"] {
    background: #111111;
    border-right: 1px solid rgba(196,30,58,.35);
}
[data-testid="stSidebar"] * { color: #E5E7EB !important; }

/* ===== Floating AI assistant chip, shown on every page ===== */

</style>

""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# SIDEBAR BRANDING — shown above the navigation on every page
# ---------------------------------------------------------------------------
# If the real date has moved past every expiry date in the sample data,
# Live mode would leave no usable stock -- fall back to the data snapshot.
# (Must happen BEFORE the toggle widget is created.)
_live_fallback = False
if st.session_state.get("live_mode") and all_batches_expired_today():
    st.session_state["live_mode"] = False
    _live_fallback = True

with st.sidebar:
    st.markdown("### 🩸 SanguiCore")
    st.caption("Decision Support System")
    st.markdown("---")

    st.toggle(
        "Live mode",
        key="live_mode",
        help=(
            "Off: analysis is anchored to the newest date in the dataset "
            "(stable, ideal for demos). On: uses today's real date; batches "
            "already past expiry are excluded from usable stock."
        ),
    )
    if _live_fallback:
        st.warning("Every batch in the sample data has expired by today's real date, so Live mode was switched off.")

# ---------------------------------------------------------------------------
# NAVIGATION — grouped sections, each pointing to a real page file.
# ---------------------------------------------------------------------------
pages = {
    "Home": [
        st.Page("home.py", title="Mission Control", icon="📊", default=True),
    ],
    "Operations": [
        st.Page("pages/inventory.py", title="Inventory", icon="🧪"),
        st.Page("pages/ai_prediction.py", title="AI Risk Analysis", icon="🤖"),
        st.Page("pages/decision_engine.py", title="Decision Engine", icon="🧠"),
        st.Page("pages/emergency_mode.py", title="Emergency Response", icon="🚨"),
        st.Page("pages/donor_management.py", title="Donor Management", icon="🩸"),
    ],
    "Insights": [
        st.Page("pages/analytics.py", title="Analytics", icon="📈"),
    ],
}

nav = st.navigation(pages)


@st.fragment(run_every=1)
def live_status_bar():
    """Ticking clock strip shown at the top of every page."""
    now = datetime.now()
    live = is_live_mode()
    dot_color = "#16A34A" if live else "#B8860B"
    label = "LIVE" if live else "DATA SNAPSHOT"
    detail = (
        "using today's real date"
        if live
        else f"analysis as of {get_data_date():%d %b %Y}"
    )
    st.markdown(
        f"""
        <div style="display:flex;justify-content:space-between;align-items:center;
                    gap:12px;flex-wrap:wrap;padding:6px 14px;margin-bottom:8px;
                    background:rgba(255,255,255,0.72);border:1px solid #E5E7EB;
                    border-radius:12px;font-size:12.5px;color:#111;">
            <span><span style="color:{dot_color};font-size:14px;">●</span>
                  <b style="letter-spacing:.06em;">{label}</b>
                  <span style="color:#8a7a7c;"> · {detail}</span></span>
            <span style="font-family:'IBM Plex Mono',monospace;font-weight:600;">
                {now:%a, %d %b %Y · %H:%M:%S}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


live_status_bar()

with st.sidebar:
    st.markdown("---")

nav.run()
