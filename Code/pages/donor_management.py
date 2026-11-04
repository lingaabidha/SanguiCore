import os
import sys
import pandas as pd
import streamlit as st

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_donations, get_reference_date, render_html

st.markdown('<p class="bp-section-title" style="font-size:1.3rem;">Donor Management</p>', unsafe_allow_html=True)

try:
    donations = load_donations()
except Exception as exc:
    st.error(f"Could not load blood_donations.csv: {exc}")
    st.stop()

if donations.empty:
    st.warning("blood_donations.csv has no usable rows.")
    st.stop()

today = get_reference_date()
total_donors = donations["Donor_ID"].nunique() if "Donor_ID" in donations.columns else len(donations)
total_units = int(donations["Units_Donated"].sum())
avg_units = donations["Units_Donated"].mean()

def kpi_card(label, value, sub_text=None, sub_class=""):
    sub_html = f'<p class="bp-kpi-sub {sub_class}">● {sub_text}</p>' if sub_text else ""
    render_html(f"""
    <div class="bp-glass bp-kpi-card">
        <p class="bp-kpi-label">{label}</p>
        <p class="bp-kpi-value">{value}</p>
        {sub_html}
    </div>
    """)

for col, item in zip(st.columns(3), [
    ("Total Donors", f"{total_donors:,}", "on record", ""),
    ("Units Donated", f"{total_units:,}", "recorded units", "bp-teal"),
    ("Avg Units / Donation", f"{avg_units:.1f}", "per donation", ""),
]):
    with col:
        kpi_card(*item)

st.write("")
c1, c2 = st.columns(2)

with c1:
    with st.container(key="glasscard_donations_by_group"):
        st.markdown('<p class="bp-section-title">Donations by blood group</p>', unsafe_allow_html=True)
        st.bar_chart(donations.groupby("Blood_Group")["Units_Donated"].sum().sort_index(), height=230)

with c2:
    with st.container(key="glasscard_donation_trend"):
        st.markdown('<p class="bp-section-title">Donation trend</p>', unsafe_allow_html=True)
        monthly = donations.groupby(donations["Donation_Date"].dt.to_period("M"))["Units_Donated"].sum()
        monthly.index = monthly.index.astype(str)
        st.line_chart(monthly, height=230)

st.write("")
with st.container(key="glasscard_donation_records"):
    st.markdown('<p class="bp-section-title">Donation records</p>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        groups = st.multiselect("Blood group", sorted(donations["Blood_Group"].unique()), default=[])
    with c2:
        banks = st.multiselect("Blood bank", sorted(donations["Blood_Bank"].unique()), default=[])

    filtered = donations.copy()
    if groups:
        filtered = filtered[filtered["Blood_Group"].isin(groups)]
    if banks:
        filtered = filtered[filtered["Blood_Bank"].isin(banks)]

    display_cols = [c for c in ["Donor_ID","Blood_Group","Units_Donated","Blood_Bank","Donation_Date"] if c in filtered.columns]
    display_df = filtered[display_cols].sort_values("Donation_Date", ascending=False).copy()
    if "Donation_Date" in display_df:
        display_df["Donation_Date"] = display_df["Donation_Date"].dt.strftime("%d %b %Y")
    display_df = display_df.rename(columns={
        "Donor_ID":"Donor", "Blood_Group":"Group", "Units_Donated":"Units",
        "Blood_Bank":"Blood Bank", "Donation_Date":"Donation Date"
    })
    st.dataframe(display_df, hide_index=True, use_container_width=True)
