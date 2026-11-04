import os
import sys
import pandas as pd
import streamlit as st

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_usable_inventory, load_usage, load_requests, get_reference_date

st.markdown("""
<div class="bp-hero">
  <div class="bp-hero-left">
    <h1>Emergency <span>Response</span></h1>
    <p>A focused view of open hospital requests, stock risk and expiry concerns.</p>
  </div>
</div>
""", unsafe_allow_html=True)

try:
    inventory = load_usable_inventory()
    usage = load_usage()
    requests = load_requests()
except Exception as exc:
    st.error(f"Could not load project data: {exc}")
    st.stop()

today = get_reference_date()
total = inventory.groupby("Blood_Group")["Quantity"].sum()

recent = usage[usage["Issue_Date"] > usage["Issue_Date"].max() - pd.Timedelta(days=14)]
daily = recent.groupby("Blood_Group")["Units_Issued"].sum() / 14

risk_rows = []
for group in sorted(total.index):
    d = float(daily.get(group, 0))
    coverage = float(total[group]) / d if d > 0 else float("inf")
    risk = "HIGH" if coverage < 3 else ("MODERATE" if coverage < 7 else "LOW")
    risk_rows.append({
        "Blood Group": group,
        "Units": int(total[group]),
        "Daily Demand": round(d, 1),
        "Coverage": "—" if d == 0 else f"{coverage:.1f} days",
        "Risk": risk,
    })

open_requests = requests[requests["Status"].isin(["Pending","Partial"])].copy()
expiring = inventory[(inventory["Expiry_Date"] >= today) & (inventory["Expiry_Date"] <= today + pd.Timedelta(days=7))]

c1,c2,c3 = st.columns(3)
c1.metric("Open Hospital Requests", len(open_requests))
c2.metric("High-Risk Blood Groups", sum(r["Risk"]=="HIGH" for r in risk_rows))
c3.metric("Batches Expiring Soon", len(expiring))

st.markdown("### Blood-group risk")
st.dataframe(pd.DataFrame(risk_rows), hide_index=True, use_container_width=True)

st.markdown("### Open hospital requests")
if open_requests.empty:
    st.success("No pending or partially fulfilled hospital requests.")
else:
    cols = [c for c in ["Request_ID","Hospital_Name","Request_Date","Blood_Group","Units_Requested","Emergency_Level","Status"] if c in open_requests.columns]
    requests_display = open_requests[cols].sort_values("Request_Date", ascending=False).copy()
    # Show the date only (no 00:00:00 time part)
    requests_display["Request_Date"] = requests_display["Request_Date"].dt.strftime("%d %b %Y")
    st.dataframe(requests_display, hide_index=True, use_container_width=True)

st.markdown("### Emergency checklist")
st.markdown("""
1. Review **HIGH** blood-group risk.
2. Review open hospital requests and emergency levels.
3. Check inventory approaching expiry.
4. Recheck stock and requests before taking operational action.
""")
