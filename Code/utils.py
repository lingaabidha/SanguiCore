"""
Shared helpers used across every SanguiCore page.

Keeping these in one place means every page loads data the same way,
agrees on what "today" means, and reads the same configurable risk
thresholds — so the AI Insight on Mission Control, the Decision Engine,
Inventory and the AI Prediction page can never quietly disagree with
each other about the same numbers.
"""

import os

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------
# utils.py always lives in the project's Code/ folder, and the datasets
# always live in a sibling Dataset/ folder — regardless of the working
# directory Streamlit was launched from.
CODE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CODE_DIR)
DATASET_DIR = os.path.join(PROJECT_ROOT, "Dataset")

DATE_FORMAT = "%d-%m-%Y"

# The supplied CSVs are synthetic demonstration records. Their dates are
# shifted together at load time so the demo remains realistic whenever it is
# opened: the newest operational record is anchored 4 days before today.
# This keeps collection/issue/request/expiry intervals intact while ensuring
# the inventory contains a useful mix of expired, near-expiry and valid stock.
DATE_ANCHOR_DAYS_BEFORE_TODAY = 4


def get_date_shift_days():
    """Return one consistent date offset for all four demonstration datasets."""
    operational_max = None
    for filename in (
        "blood_inventory.csv",
        "blood_usage.csv",
        "blood_donations.csv",
        "hospital_requests.csv",
    ):
        path = os.path.join(DATASET_DIR, filename)
        if not os.path.exists(path):
            continue
        raw = pd.read_csv(path)
        for column in raw.columns:
            # Expiry is an outcome date, not an operational activity date.
            if "date" not in column.lower() or "expiry" in column.lower():
                continue
            values = pd.to_datetime(raw[column], format=DATE_FORMAT, errors="coerce")
            latest = values.max()
            if pd.notna(latest) and (operational_max is None or latest > operational_max):
                operational_max = latest

    if operational_max is None:
        return 0
    target_latest = pd.Timestamp.now().normalize() - pd.Timedelta(
        days=DATE_ANCHOR_DAYS_BEFORE_TODAY
    )
    return int((target_latest - operational_max.normalize()).days)


def _candidate_paths(filename):
    return [
        os.path.join(DATASET_DIR, filename),
        os.path.join("Dataset", filename),
        os.path.join("..", "Dataset", filename),
        filename,
    ]


def load_dataset(filename):
    """
    Read a CSV from the Dataset folder. Tries the absolute path next to
    the project first, then a couple of relative fallbacks, so pages work
    whether Streamlit was launched from the Code/ folder or elsewhere.
    """
    for path in _candidate_paths(filename):
        if os.path.exists(path):
            return pd.read_csv(path)

    raise FileNotFoundError(
        f"Could not find {filename}. Expected it in the project's Dataset folder "
        f"({DATASET_DIR})."
    )


def parse_dates(df, column, errors="raise"):
    """Parse a DD-MM-YYYY date column and shift it with the demo timeline."""
    df[column] = pd.to_datetime(df[column], format=DATE_FORMAT, errors=errors)
    shift_days = get_date_shift_days()
    if shift_days:
        df[column] = df[column] + pd.to_timedelta(shift_days, unit="D")
    return df


# ---------------------------------------------------------------------------
# CANONICAL DATA LOADERS (cached, shared by every page)
# ---------------------------------------------------------------------------
def _load_inventory_raw():
    df = load_dataset("blood_inventory.csv")
    df = parse_dates(df, "Collection_Date", errors="coerce")
    df = parse_dates(df, "Expiry_Date", errors="coerce")
    df["Blood_Group"] = df["Blood_Group"].astype(str).str.strip()
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
    return df


def load_inventory():
    """
    Usable inventory. In Data-snapshot mode this is every batch in the CSV.
    In Live mode, batches whose expiry date is before the real today are
    removed (they are written off, not usable stock) so every page --
    Mission Control, Inventory, Decision Engine, Emergency -- agrees.
    """
    df = _load_inventory_raw()
    if is_live_mode():
        today = get_reference_date()
        df = df[df["Expiry_Date"].isna() | (df["Expiry_Date"] >= today)]
    return df.copy()


def load_usable_inventory():
    """Return inventory batches that are not expired as of the current reference date.

    Unlike load_inventory(), this excludes expired batches in both snapshot and
    live modes. Use it for stock totals, coverage calculations and risk logic.
    The Inventory page can still use load_inventory() to display expired rows.
    """
    df = _load_inventory_raw()
    today = get_reference_date()
    return df[df["Expiry_Date"].isna() | (df["Expiry_Date"] >= today)].copy()


def get_expired_summary():
    """(batches, units) already past expiry as of the current reference date."""
    df = _load_inventory_raw()
    expired = df[df["Expiry_Date"] < get_reference_date()]
    return len(expired), int(expired["Quantity"].sum())


def all_batches_expired_today():
    """True if, by the real clock, no batch in the sample data is still usable."""
    df = _load_inventory_raw()
    return bool(df["Expiry_Date"].max() < pd.Timestamp.now().normalize())


def load_usage():
    df = load_dataset("blood_usage.csv")
    df = parse_dates(df, "Issue_Date", errors="coerce")
    df["Blood_Group"] = df["Blood_Group"].astype(str).str.strip()
    df["Units_Issued"] = pd.to_numeric(df["Units_Issued"], errors="coerce")
    return df


def load_requests():
    df = load_dataset("hospital_requests.csv")
    df = parse_dates(df, "Request_Date", errors="coerce")
    df["Blood_Group"] = df["Blood_Group"].astype(str).str.strip()
    df["Units_Requested"] = pd.to_numeric(df["Units_Requested"], errors="coerce")
    return df


def load_donations():
    df = load_dataset("blood_donations.csv")
    df = parse_dates(df, "Donation_Date", errors="coerce")
    df["Blood_Group"] = df["Blood_Group"].astype(str).str.strip()
    df["Units_Donated"] = pd.to_numeric(df["Units_Donated"], errors="coerce")
    return df


def is_live_mode():
    """True when the sidebar 'Live mode' toggle is on."""
    return bool(st.session_state.get("live_mode", False))


def get_data_date():
    """
    Latest operational date in the supplied data (the 'data snapshot' date).
    Expiry_Date is deliberately excluded because it can be in the future.
    """
    candidates = []

    for loader, column in [
        (_load_inventory_raw, "Collection_Date"),
        (load_usage, "Issue_Date"),
        (load_requests, "Request_Date"),
        (load_donations, "Donation_Date"),
    ]:
        try:
            value = loader()[column].max()
            if pd.notna(value):
                candidates.append(value)
        except Exception:
            pass

    if candidates:
        return max(candidates)

    return pd.Timestamp.now().normalize()


def get_reference_date():
    """
    The date every page treats as "today".

    - Data-snapshot mode (default): the newest date in the datasets, so the
      demo stays consistent no matter when it is run.
    - Live mode: the real system date. Demand signals still come from the
      most recent recorded usage, but expiry math uses the real calendar.
    """
    if is_live_mode():
        return pd.Timestamp.now().normalize()
    return get_data_date()


# ---------------------------------------------------------------------------
# CONFIGURABLE THRESHOLDS
# Defaults live here so every page starts in agreement. The Settings page
# lets a user override them for the session; every other page reads the
# override through get_threshold() so a change takes effect everywhere.
# ---------------------------------------------------------------------------
DEFAULT_THRESHOLDS = {
    "risk_high_days": 3,        # AI Prediction: below this = HIGH RISK
    "risk_moderate_days": 7,    # AI Prediction: below this = MODERATE RISK
    "use_first_days": 3,        # Inventory / Decision Engine wastage tiers
    "prioritize_days": 7,
    "expiry_watch_days": 7,     # Home / Inventory "expiring soon" window
    "transfer_threshold": 100,  # Decision Engine redistribution trigger (units)
}

THRESHOLD_LABELS = {
    "risk_high_days": "High-risk coverage threshold (days)",
    "risk_moderate_days": "Moderate-risk coverage threshold (days)",
    "use_first_days": "\u201cUse first\u201d expiry window (days)",
    "prioritize_days": "\u201cPrioritize\u201d expiry window (days)",
    "expiry_watch_days": "\u201cExpiring soon\u201d window (days)",
    "transfer_threshold": "Redistribution trigger gap (units)",
}


def get_threshold(key):
    """Session-overridden threshold, falling back to the documented default."""
    return st.session_state.get(f"threshold_{key}", DEFAULT_THRESHOLDS[key])


def set_threshold(key, value):
    st.session_state[f"threshold_{key}"] = value


def reset_thresholds():
    for key in DEFAULT_THRESHOLDS:
        st.session_state.pop(f"threshold_{key}", None)


# ---------------------------------------------------------------------------
# SAFE HTML RENDERING
# ---------------------------------------------------------------------------
def render_html(html):
    """
    st.markdown(..., unsafe_allow_html=True) for a multi-line HTML string,
    built to be called from anywhere -- including inside a function, loop,
    `with`, or `if` block.

    Why this exists: Streamlit's Markdown renderer treats 4+ leading spaces
    on a line as an "indented code block" (CommonMark's rule), which shows
    the raw HTML tags as literal text instead of rendering them. A
    multi-line triple-quoted string written inside an indented Python block
    inherits that same indentation on every line, which silently trips this
    rule -- the bug this function exists to prevent. It strips leading
    whitespace from every line before handing the string to st.markdown, so
    HTML card blocks always render correctly regardless of how deeply
    they're nested in the calling code.
    """
    lines = html.strip("\n").splitlines()
    st.markdown("\n".join(line.strip() for line in lines), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# SHARED READINESS / STATUS CALCULATIONS
# Used by both Mission Control and Emergency Mode so the two pages can
# never show a different Emergency Readiness score for the same data.
# ---------------------------------------------------------------------------
def compute_readiness(inventory_df):
    """
    Returns a dict with blood_health_score, emergency_readiness, and their
    status labels, derived from the inventory's own Status column.
    """
    total_units = inventory_df["Quantity"].sum()

    safe_qty = inventory_df.loc[inventory_df["Status"] == "Safe", "Quantity"].sum()
    warning_qty = inventory_df.loc[inventory_df["Status"] == "Warning", "Quantity"].sum()
    critical_qty = inventory_df.loc[inventory_df["Status"] == "Critical", "Quantity"].sum()

    if total_units <= 0:
        return {
            "blood_health_score": 0,
            "emergency_readiness": 0,
            "health_status": "Unknown",
            "readiness_status": "Unknown",
        }

    blood_health_score = round((safe_qty * 100 + warning_qty * 60 + critical_qty * 20) / total_units)
    emergency_readiness = round((safe_qty * 100 + warning_qty * 50 + critical_qty * 10) / total_units)

    return {
        "blood_health_score": blood_health_score,
        "emergency_readiness": emergency_readiness,
        "health_status": "Stable" if blood_health_score >= 70 else "At risk",
        "readiness_status": "Healthy" if emergency_readiness >= 70 else "Needs attention",
    }


# ---------------------------------------------------------------------------
# EXISTING HELPERS (unchanged)
# ---------------------------------------------------------------------------
def status_color(status):
    """
    Returns the correct dashboard color based on status.
    """

    status = str(status).lower()

    if status in ["healthy", "safe", "stable", "true"]:
        return "bp-green"

    if status in ["warning", "attention"]:
        return "bp-amber"

    return "bp-red"


def article_for(word):
    if not word:
        return "a"

    return "an" if word[0].upper() in "AEIOU" else "a"


def shortage_risk_signals(critical_pct, trend_pct, pending_count):
    """
    Return observable shortage-risk signals and their count.

    This is a transparent rule-based indicator, NOT a probability,
    calibrated confidence score, or machine-learning prediction.
    """
    reasons = []
    if pd.notna(critical_pct) and critical_pct >= 50:
        reasons.append(f"{critical_pct:.1f}% of this group's current stock is flagged Critical")
    if pd.notna(trend_pct) and trend_pct > 10:
        reasons.append(f"Usage increased by {trend_pct:.0f}% versus the previous week")
    if pending_count > 0:
        reasons.append(f"{int(pending_count)} pending hospital requests across all blood groups")
    return len(reasons), reasons
