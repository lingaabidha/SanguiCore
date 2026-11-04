import streamlit as st
import pandas as pd
from datetime import datetime
from utils import (
    status_color,
    shortage_risk_signals,
    article_for,
    load_usable_inventory,
    load_usage,
    load_requests,
    get_reference_date,
    get_threshold,
    compute_readiness,
    render_html,
)

# ---------------------------------------------------------------------------
# LOAD REAL DATA
# ---------------------------------------------------------------------------
try:
    inventory = load_usable_inventory()
    requests = load_requests()
    usage = load_usage()
except Exception as exc:
    st.error(f"Could not load one of the core datasets: {exc}")
    st.stop()

if inventory.empty or usage.empty:
    st.warning("Inventory or usage data is empty, so Mission Control can't compute live KPIs yet.")
    st.stop()

today = get_reference_date()
EXPIRY_WATCH_DAYS = get_threshold("expiry_watch_days")

# ---------------------------------------------------------------------------
# CORE CALCULATIONS
# ---------------------------------------------------------------------------
total_units = int(inventory["Quantity"].sum())

expiring_soon = inventory[
    (inventory["Expiry_Date"] >= today) &
    (inventory["Expiry_Date"] <= today + pd.Timedelta(days=EXPIRY_WATCH_DAYS))
]
expiring_count = int(expiring_soon["Quantity"].sum())

pending_requests = int((requests["Status"] == "Pending").sum())
partial_requests = int((requests["Status"] == "Partial").sum())

total_by_group = inventory.groupby("Blood_Group")["Quantity"].sum().sort_index()
critical_by_group = (
    inventory[inventory["Status"] == "Critical"]
    .groupby("Blood_Group")["Quantity"].sum()
    .reindex(total_by_group.index, fill_value=0)
)
critical_pct_by_group = (critical_by_group / total_by_group * 100).round(1)

readiness = compute_readiness(inventory)
blood_health_score = readiness["blood_health_score"]
emergency_readiness = readiness["emergency_readiness"]
readiness_status = readiness["readiness_status"]
health_status = readiness["health_status"]

active_alerts = int(critical_by_group.gt(0).sum()) + (1 if pending_requests > 0 else 0) + (1 if expiring_count > 0 else 0)

# ---------------------------------------------------------------------------
# AI INSIGHT RIBBON — a real, computed sentence, not placeholder copy
# ---------------------------------------------------------------------------
if critical_pct_by_group.empty or critical_pct_by_group.max() == 0:
    top_group = total_by_group.idxmax() if not total_by_group.empty else "N/A"
    top_pct = 0.0
else:
    top_group = critical_pct_by_group.idxmax()
    top_pct = critical_pct_by_group.max()

max_date = usage["Issue_Date"].max()
last7 = usage[usage["Issue_Date"] > max_date - pd.Timedelta(days=7)].groupby("Blood_Group")["Units_Issued"].sum()
prev7 = usage[(usage["Issue_Date"] <= max_date - pd.Timedelta(days=7)) &
              (usage["Issue_Date"] > max_date - pd.Timedelta(days=14))].groupby("Blood_Group")["Units_Issued"].sum()
previous_usage = float(prev7.get(top_group, 0))
current_usage = float(last7.get(top_group, 0))
top_trend = (
    (current_usage - previous_usage) / previous_usage * 100
    if previous_usage > 0 else None
)
top_pending = int(pending_requests + partial_requests)  # all pending/partial requests across groups

risk_signal_count, ai_reasons = shortage_risk_signals(top_pct, top_trend, top_pending)

if top_pct >= 50:
    ai_headline = f"{top_group} inventory needs review: {top_pct:.1f}% of its current stock is marked Critical."
    ai_action = f"Review {top_group} stock, pending requests and replenishment options."
elif pd.notna(top_trend) and top_trend > 10:
    ai_headline = f"{top_group} usage increased by {top_trend:.1f}% compared with the previous 7-day period."
    ai_action = f"Review recent {top_group} demand and available stock before planning replenishment."
else:
    ai_headline = "No group currently meets the dashboard's critical-stock threshold."
    ai_action = "Continue monitoring stock levels, expiry dates and pending requests."

# ---------------------------------------------------------------------------
# TOP BAR
# ---------------------------------------------------------------------------
last_sync = datetime.now().strftime("%I:%M %p")
st.markdown(f"""
<div class="bp-topbar bp-anim">
    <div class="bp-topbar-left">
        <div class="bp-topbar-logo">🩸</div>
        <div>
            <p class="bp-topbar-title">SanguiCore</p>
            <p class="bp-topbar-sub">Blood Bank Decision Support &middot; viewed {last_sync}</p>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# AI INSIGHT OF THE DAY — structured card: headline, recommended action,
# observable risk signals. This is not a model confidence score.
# ---------------------------------------------------------------------------
st.markdown(f"""
<div class="bp-glass bp-ai-ribbon bp-anim" style="animation-delay:.05s;flex-direction:column;align-items:flex-start;gap:6px;">
    <div style="display:flex;align-items:center;gap:10px;">
        <div class="bp-ai-icon">🧠</div>
        <p style="font-weight:600;font-size:13px;color:var(--bp-muted);margin:0;text-transform:uppercase;letter-spacing:.03em;">Operational Insight</p>
    </div>
    <p style="margin:2px 0 0 42px;font-size:14px;color:var(--bp-ink);">{ai_headline}</p>
    <p style="margin:0 0 0 42px;font-size:13px;color:var(--bp-ink);"><strong>Recommended action:</strong> {ai_action}</p>
    <p style="margin:0 0 0 42px;font-size:12px;color:var(--bp-teal);font-weight:600;">Risk signals: {risk_signal_count} of 3</p>
    <p style="margin:0 0 0 42px;font-size:11px;color:var(--bp-muted);">Rule-based indicators, not a probability or AI confidence score.</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# KPI ROW — glass cards, dynamically colored
# ---------------------------------------------------------------------------
def kpi_card(label, value, sub_text, sub_class):
    render_html(f"""
    <div class="bp-glass bp-kpi-card bp-anim" style="animation-delay:.1s;">
        <p class="bp-kpi-label">{label}</p>
        <p class="bp-kpi-value">{value}</p>
        <p class="bp-kpi-sub {sub_class}">● {sub_text}</p>
    </div>
    """)

kpis = [
    ("Emergency Readiness", emergency_readiness, readiness_status, status_color(emergency_readiness >= 70)),
    ("Blood Health", blood_health_score, health_status, status_color(blood_health_score >= 70)),
    ("Total Units", f"{total_units:,}", f"{total_by_group.shape[0]} groups", "bp-teal"),
    ("Active Alerts", active_alerts, "Clear" if active_alerts == 0 else "Review", status_color(active_alerts == 0)),
]

for col, (label, value, sub, cls) in zip(st.columns(4), kpis):
    with col:
        kpi_card(label, value, sub, cls)

st.write("")

# ---------------------------------------------------------------------------
# INVENTORY SNAPSHOT — status-colored chips, real data
# ---------------------------------------------------------------------------
with st.container(key="glasscard_inventory_snapshot"):
    st.markdown('<p class="bp-section-title" style="margin-bottom:8px;">Inventory snapshot</p>', unsafe_allow_html=True)

    chip_colors = {
        "healthy": ("#eafaf0", "#16A34A"),
        "moderate": ("#fff6e0", "#B8860B"),
        "critical": ("#fdeaec", "#C41E3A"),
    }
    chips_html = ""
    for group in total_by_group.index:
        pct = critical_pct_by_group.get(group, 0)
        label = "critical" if pct >= 50 else ("moderate" if pct >= 25 else "healthy")
        bg, fg = chip_colors[label]
        chips_html += f'<span class="bp-chip" style="background:{bg};color:{fg};margin-right:6px;margin-bottom:6px;">{group} {int(total_by_group[group])}</span>'

    st.markdown(chips_html, unsafe_allow_html=True)

st.write("")

# ---------------------------------------------------------------------------
# USAGE TREND CHART
# ---------------------------------------------------------------------------
with st.container(key="glasscard_usage_trend"):
    st.markdown('<p class="bp-section-title">Usage trend, last 14 days</p>', unsafe_allow_html=True)

    recent_cutoff = usage["Issue_Date"].max() - pd.Timedelta(days=13)
    recent_usage = usage[usage["Issue_Date"] >= recent_cutoff]
    daily_usage = recent_usage.groupby("Issue_Date")["Units_Issued"].sum().sort_index()

    st.line_chart(daily_usage, color="#C41E3A", height=180)

st.write("")

# ---------------------------------------------------------------------------
# DECISION ENGINE TEASER — real top recommendation, distinct visual treatment
# ---------------------------------------------------------------------------
by_bank = inventory.groupby(["Blood_Group", "Blood_Bank"])["Quantity"].sum().unstack(fill_value=0)
TRANSFER_THRESHOLD = get_threshold("transfer_threshold")

best_transfer = None
best_gap = 0
for group in by_bank.index:
    row = by_bank.loc[group]
    gap = row.max() - row.min()
    if gap > best_gap:
        best_gap = gap
        best_transfer = (group, row.idxmax(), row.idxmin(), gap)

if best_transfer and best_gap >= TRANSFER_THRESHOLD:
    group, surplus_bank, deficit_bank, gap = best_transfer
    teaser_title = f"Transfer {int(gap // 2)} units of {group} to {deficit_bank}"
    teaser_sub = (
        f"{surplus_bank} holds {int(by_bank.loc[group, surplus_bank])} units, "
        f"{deficit_bank} holds {int(by_bank.loc[group, deficit_bank])}. "
        "Review compatibility, demand and local policy before any transfer."
    )
else:
    teaser_title = f"Organize {article_for(top_group)} {top_group} donation drive"
    teaser_sub = f"Based on stock distribution; review the underlying records before taking action."

st.markdown(f"""
<div class="bp-decision-teaser bp-anim" style="animation-delay:.25s;">
    <p class="bp-decision-label">Decision Engine</p>
    <p class="bp-decision-title">{teaser_title}</p>
    <p class="bp-decision-sub">{teaser_sub}</p>
    <svg class="bp-pulse-line" width="200" height="40" viewBox="0 0 220 40">
        <path d="M0,20 L35,20 L45,6 L55,34 L65,2 L75,38 L85,20 L120,20 L130,10 L140,30 L150,20 L220,20"
              fill="none" stroke="#C41E3A" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
</div>
""", unsafe_allow_html=True)

if st.button("Open Decision Engine →"):
    st.switch_page("pages/decision_engine.py")
