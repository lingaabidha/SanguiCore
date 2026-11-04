import os
import sys
import pandas as pd
import streamlit as st

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_usable_inventory, load_usage, load_requests, get_reference_date, get_threshold

st.markdown("""
<div class="bp-hero">
  <div class="bp-hero-left">
    <h1>Decision <span>Engine</span></h1>
    <p>Explainable operational recommendations based on inventory, recent usage and hospital demand.</p>
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
inventory["Days_to_Expiry"] = (inventory["Expiry_Date"] - today).dt.days

# Simple, explainable signals
total_by_group = inventory.groupby("Blood_Group")["Quantity"].sum()
critical_by_group = inventory[inventory["Status"] == "Critical"].groupby("Blood_Group")["Quantity"].sum()
critical_pct = (critical_by_group.reindex(total_by_group.index, fill_value=0) / total_by_group * 100).round(1)

max_date = usage["Issue_Date"].max()
recent = usage[usage["Issue_Date"] > max_date - pd.Timedelta(days=14)]
recent_daily = recent.groupby("Blood_Group")["Units_Issued"].sum() / 14

open_requests = requests[requests["Status"].isin(["Pending", "Partial"])]
open_counts = open_requests.groupby("Blood_Group").size()

st.markdown("### Current recommendations")

recommendations = []
for group in sorted(total_by_group.index):
    stock = float(total_by_group[group])
    daily = float(recent_daily.get(group, 0))
    coverage = stock / daily if daily > 0 else float("inf")
    critical = float(critical_pct.get(group, 0))
    open_count = int(open_counts.get(group, 0))

    if coverage < 3:
        risk = "HIGH"
        reason = f"about {coverage:.1f} days of coverage based on recent usage"
    elif coverage < 7:
        risk = "MODERATE"
        reason = f"about {coverage:.1f} days of coverage based on recent usage"
    else:
        risk = "LOW"
        reason = f"about {coverage:.1f} days of coverage based on recent usage"

    if risk == "HIGH" or open_count > 0 or critical >= 50:
        actions = []
        if risk == "HIGH":
            actions.append("monitor stock closely")
        if open_count > 0:
            actions.append(f"review {open_count} open hospital request(s)")
        if critical >= 50:
            actions.append("review critical inventory")
        recommendations.append({
            "Blood Group": group,
            "Risk": risk,
            "Current Units": int(stock),
            "Coverage": "—" if daily == 0 else f"{coverage:.1f} days",
            "Reason": "; ".join(actions),
        })

if recommendations:
    st.dataframe(pd.DataFrame(recommendations), hide_index=True, use_container_width=True)
else:
    st.success("No groups currently require an additional operational review from these signals.")

st.markdown("### Expiry review")
expiry_window = get_threshold("prioritize_days")
expiring = inventory[(inventory["Days_to_Expiry"] >= 0) & (inventory["Days_to_Expiry"] <= expiry_window)].copy()
if expiring.empty:
    st.info(f"No inventory batches expire within the next {expiry_window} days based on the available inventory records.")
else:
    expiring_display = (
        expiring[["Batch_ID","Blood_Group","Quantity","Blood_Bank","Expiry_Date","Days_to_Expiry"]]
        .rename(columns={"Batch_ID":"Batch","Blood_Group":"Group","Quantity":"Units","Blood_Bank":"Blood Bank","Expiry_Date":"Expiry Date","Days_to_Expiry":"Days Left"})
        .sort_values("Days Left")
    )
    # Show the date only (no 00:00:00 time part)
    expiring_display["Expiry Date"] = expiring_display["Expiry Date"].dt.strftime("%d %b %Y")
    st.dataframe(expiring_display, hide_index=True, use_container_width=True)
