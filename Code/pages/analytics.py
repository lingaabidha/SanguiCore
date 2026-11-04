import os
import sys

import pandas as pd
import streamlit as st

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_usable_inventory, load_usage, load_donations, load_requests, get_reference_date

st.markdown('<p class="bp-section-title" style="font-size:1.3rem;">Analytics</p>', unsafe_allow_html=True)

try:
    inventory = load_usable_inventory()
    usage = load_usage()
    donations = load_donations()
    requests = load_requests()
except Exception as exc:
    st.error(f"Could not load one of the core datasets: {exc}")
    st.stop()

today = get_reference_date()

# ---------------------------------------------------------------------------
# ROW 1 — BLOOD DISTRIBUTION BY GROUP, REQUEST STATUS BREAKDOWN
# ---------------------------------------------------------------------------
col1, col2 = st.columns(2)

with col1:
    with st.container(key="glasscard_inventory_by_group"):
        st.markdown('<p class="bp-section-title">Current inventory by blood group</p>', unsafe_allow_html=True)
        if inventory.empty:
            st.info("No inventory data available.")
        else:
            by_group = inventory.groupby("Blood_Group")["Quantity"].sum().sort_index()
            st.bar_chart(by_group, color="#C41E3A", height=240)

with col2:
    with st.container(key="glasscard_request_outcomes"):
        st.markdown('<p class="bp-section-title">Hospital request outcomes</p>', unsafe_allow_html=True)
        if requests.empty:
            st.info("No hospital request data available.")
        else:
            status_counts = requests["Status"].value_counts()
            st.bar_chart(status_counts, color="#0B6E7F", height=240)

st.write("")

# ---------------------------------------------------------------------------
# ROW 2 — DONATION TRENDS OVER TIME, DEMAND (USAGE) OVER TIME
# ---------------------------------------------------------------------------
col3, col4 = st.columns(2)

with col3:
    with st.container(key="glasscard_donation_trend"):
        st.markdown('<p class="bp-section-title">Donation trend, by month</p>', unsafe_allow_html=True)
        if donations.empty:
            st.info("No donation data available.")
        else:
            monthly_donations = (
                donations.groupby(donations["Donation_Date"].dt.to_period("M"))["Units_Donated"].sum()
            )
            monthly_donations.index = monthly_donations.index.astype(str)
            st.line_chart(monthly_donations, color="#16A34A", height=240)

with col4:
    with st.container(key="glasscard_demand_trend"):
        st.markdown('<p class="bp-section-title">Demand trend, by month</p>', unsafe_allow_html=True)
        if usage.empty:
            st.info("No usage data available.")
        else:
            monthly_usage = (
                usage.groupby(usage["Issue_Date"].dt.to_period("M"))["Units_Issued"].sum()
            )
            monthly_usage.index = monthly_usage.index.astype(str)
            st.line_chart(monthly_usage, color="#C41E3A", height=240)

st.write("")

# ---------------------------------------------------------------------------
# ROW 3 — USAGE BY REQUESTING HOSPITAL
# ---------------------------------------------------------------------------
with st.container(key="glasscard_units_by_hospital"):
    st.markdown('<p class="bp-section-title">Units issued by hospital</p>', unsafe_allow_html=True)
    if usage.empty:
        st.info("No usage data available.")
    else:
        by_hospital = usage.groupby("Hospital_Name")["Units_Issued"].sum().sort_values(ascending=False)
        st.bar_chart(by_hospital, color="#8B0000", height=240)

# ---------------------------------------------------------------------------
# ROW 4 — DEMAND BY BLOOD GROUP AND DAY OF WEEK (SEASONAL / WEEKLY PATTERN)
# ---------------------------------------------------------------------------
with st.container(key="glasscard_dow_demand"):
    st.markdown('<p class="bp-section-title">Average daily demand by day of week</p>', unsafe_allow_html=True)
    if usage.empty:
        st.info("No usage data available.")
    else:
        daily_totals = usage.groupby("Issue_Date")["Units_Issued"].sum()
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        by_dow = daily_totals.groupby(daily_totals.index.dayofweek).mean()
        by_dow.index = [day_names[i] for i in by_dow.index]
        by_dow = by_dow.reindex(day_names)
        st.bar_chart(by_dow, color="#B8860B", height=220)

# ---------------------------------------------------------------------------
# ROW 5 — SUMMARY TABLE PER BLOOD GROUP
# ---------------------------------------------------------------------------
with st.container(key="glasscard_summary_by_group"):
    st.markdown('<p class="bp-section-title">Summary by blood group</p>', unsafe_allow_html=True)

    if inventory.empty:
        st.info("No inventory data available.")
    else:
        stock = inventory.groupby("Blood_Group")["Quantity"].sum()
        donated = donations.groupby("Blood_Group")["Units_Donated"].sum() if not donations.empty else pd.Series(dtype=float)
        issued = usage.groupby("Blood_Group")["Units_Issued"].sum() if not usage.empty else pd.Series(dtype=float)
        requested = requests.groupby("Blood_Group")["Units_Requested"].sum() if not requests.empty else pd.Series(dtype=float)

        summary = pd.DataFrame({
            "Current Stock": stock,
            "Total Donated (history)": donated,
            "Total Issued (history)": issued,
            "Total Requested (history)": requested,
        }).fillna(0).astype(int)
        summary = summary.sort_index()
        st.dataframe(summary, use_container_width=True)
