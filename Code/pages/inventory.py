import os
import sys

import streamlit as st

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_inventory, get_reference_date, get_threshold, render_html, is_live_mode, get_expired_summary

st.markdown('<p class="bp-section-title" style="font-size:1.3rem;">Inventory</p>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# LOAD REAL DATA
# ---------------------------------------------------------------------------
try:
    inventory = load_inventory()
except Exception as exc:
    st.error(f"Could not load blood_inventory.csv: {exc}")
    st.stop()

if inventory.empty:
    st.warning("blood_inventory.csv has no usable rows.")
    st.stop()

today = get_reference_date()
inventory["Days_to_Expiry"] = (inventory["Expiry_Date"] - today).dt.days

if is_live_mode():
    _exp_batches, _exp_units = get_expired_summary()
    if _exp_batches:
        st.warning(
            f"Live mode: {_exp_batches} batches ({_exp_units:,} units) are past expiry as of "
            f"{today:%d %b %Y} and are excluded from usable stock below (write-off)."
        )

USE_FIRST_DAYS = get_threshold("use_first_days")
PRIORITIZE_DAYS = get_threshold("prioritize_days")
EXPIRY_WATCH_DAYS = get_threshold("expiry_watch_days")

def priority_for(days_left):
    if days_left < 0:
        return "Expired"
    elif days_left == 0:
        return "Expires today"
    elif days_left <= USE_FIRST_DAYS:
        return "Use first"
    elif days_left <= PRIORITIZE_DAYS:
        return "Prioritize"
    return "Monitor"

inventory["Priority"] = inventory["Days_to_Expiry"].apply(priority_for)

# ---------------------------------------------------------------------------
# SUMMARY GLASS CARDS
# ---------------------------------------------------------------------------
total_batches = len(inventory)
total_units = int(inventory.loc[inventory["Expiry_Date"].isna() | (inventory["Expiry_Date"] >= today), "Quantity"].sum())
critical_batches = int(((inventory["Status"] == "Critical") & (inventory["Expiry_Date"].isna() | (inventory["Expiry_Date"] >= today))).sum())
expiring_soon = int((inventory["Days_to_Expiry"].between(0, EXPIRY_WATCH_DAYS)).sum())

def kpi_card(label, value, sub_text=None, sub_class=""):
    sub_html = f'<p class="bp-kpi-sub {sub_class}">● {sub_text}</p>' if sub_text else ""
    render_html(f"""
    <div class="bp-glass bp-kpi-card">
        <p class="bp-kpi-label">{label}</p>
        <p class="bp-kpi-value">{value}</p>
        {sub_html}
    </div>
    """)

kpis = [
    ("Total Batches", total_batches, None, ""),
    ("Total Units", f"{total_units:,}", None, ""),
    ("Critical Batches", critical_batches, "Review", "bp-red"),
    (f"Expiring in {EXPIRY_WATCH_DAYS} Days", expiring_soon, "Watch", "bp-amber"),
]

for col, (label, value, sub, cls) in zip(st.columns(4), kpis):
    with col:
        kpi_card(label, value, sub, cls)

st.write("")

# ---------------------------------------------------------------------------
# FILTERS
# ---------------------------------------------------------------------------
with st.container(key="glasscard_inv_filters"):
    st.markdown('<p class="bp-section-title" style="margin-bottom:8px;">Filters</p>', unsafe_allow_html=True)

    fcol1, fcol2, fcol3, fcol4 = st.columns(4)
    with fcol1:
        group_filter = st.multiselect("Blood group", sorted(inventory["Blood_Group"].unique()), default=[])
    with fcol2:
        bank_filter = st.multiselect("Blood bank", sorted(inventory["Blood_Bank"].unique()), default=[])
    with fcol3:
        status_filter = st.multiselect("Status", sorted(inventory["Status"].unique()), default=[])
    with fcol4:
        search_id = st.text_input("Search Batch ID", "")

# ---------------------------------------------------------------------------
# APPLY FILTERS
# ---------------------------------------------------------------------------
filtered = inventory.copy()
if group_filter:
    filtered = filtered[filtered["Blood_Group"].isin(group_filter)]
if bank_filter:
    filtered = filtered[filtered["Blood_Bank"].isin(bank_filter)]
if status_filter:
    filtered = filtered[filtered["Status"].isin(status_filter)]
if search_id:
    filtered = filtered[filtered["Batch_ID"].str.contains(search_id, case=False, na=False)]

filtered = filtered.sort_values("Days_to_Expiry")

# ---------------------------------------------------------------------------
# TABLE
# ---------------------------------------------------------------------------
with st.container(key="glasscard_inv_batches"):
    st.markdown(f'<p class="bp-section-title">Batches ({len(filtered)} of {total_batches})</p>', unsafe_allow_html=True)

    if filtered.empty:
        st.info("No batches match the current filters.")
    else:
        display_df = filtered[[
            "Batch_ID", "Blood_Group", "Quantity", "Blood_Bank",
            "Expiry_Date", "Days_to_Expiry", "Status", "Priority"
        ]].rename(columns={
            "Batch_ID": "Batch",
            "Blood_Group": "Group",
            "Quantity": "Units",
            "Blood_Bank": "Bank",
            "Expiry_Date": "Expiry Date",
            "Days_to_Expiry": "Days Left",
        })
        display_df["Expiry Date"] = display_df["Expiry Date"].dt.strftime("%d %b %Y")

        st.dataframe(
            display_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Days Left": st.column_config.NumberColumn(format="%d days"),
            },
        )
