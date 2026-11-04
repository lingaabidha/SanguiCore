import os
import sys

import numpy as np
import pandas as pd
import streamlit as st
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

# Make the project root importable so this page can use utils.py.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from utils import status_color, load_usage, load_usable_inventory, get_threshold, get_reference_date, render_html


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

FEATURE_COLS = [
    "lag_1",
    "lag_7",
    "rolling_mean_7",
    "rolling_mean_14",
    "day_of_week",
    "month",
    "trend_idx",
]

MIN_NONZERO_DAYS = 15
TEST_FRACTION = 0.15
FORECAST_HORIZON = 7


# ---------------------------------------------------------------------------
# DATA LOADING — shared loaders from utils.py so this page always agrees
# with Mission Control, Inventory, and the Decision Engine on the same
# underlying data (same cleaning, same dtypes).
# ---------------------------------------------------------------------------

def load_data():
    usage = load_usage()
    inventory = load_usable_inventory()

    required_usage_cols = {"Issue_Date", "Blood_Group", "Units_Issued"}
    required_inventory_cols = {"Blood_Group", "Quantity", "Expiry_Date"}

    missing_usage = required_usage_cols - set(usage.columns)
    missing_inventory = required_inventory_cols - set(inventory.columns)

    if missing_usage:
        raise ValueError(
            f"blood_usage.csv is missing columns: {', '.join(sorted(missing_usage))}"
        )

    if missing_inventory:
        raise ValueError(
            "blood_inventory.csv is missing columns: "
            + ", ".join(sorted(missing_inventory))
        )

    usage = usage.dropna(subset=["Issue_Date", "Blood_Group", "Units_Issued"]).copy()
    inventory = inventory.dropna(subset=["Blood_Group", "Quantity"]).copy()

    return usage, inventory


try:
    usage, inventory = load_data()
except Exception as exc:
    st.error(f"Could not load the AI prediction data: {exc}")
    st.stop()

reference_date = get_reference_date()
st.markdown('<p class="bp-section-title" style="font-size:1.3rem;">AI Risk Analysis</p>', unsafe_allow_html=True)

blood_groups = sorted(usage["Blood_Group"].dropna().unique().tolist())

if not blood_groups:
    st.warning("No valid blood-group demand records were found in blood_usage.csv.")
    st.stop()

# Risk-classification thresholds are centralized in utils.py so the same
# defaults are used consistently across the forecasting logic.
RISK_HIGH_DAYS = get_threshold("risk_high_days")
RISK_MODERATE_DAYS = get_threshold("risk_moderate_days")


# ---------------------------------------------------------------------------
# FEATURE ENGINEERING
# ---------------------------------------------------------------------------

def build_daily_series(df, group):
    """
    Aggregate issuance into a continuous daily series for one blood group.
    Days with no recorded issuance are filled with zero.
    """
    start_date = df["Issue_Date"].min()
    end_date = df["Issue_Date"].max()

    if pd.isna(start_date) or pd.isna(end_date):
        return pd.Series(dtype=float, name="Units_Issued")

    full_range = pd.date_range(start_date, end_date, freq="D")

    group_data = df[df["Blood_Group"] == group]

    daily = (
        group_data.groupby("Issue_Date")["Units_Issued"]
        .sum()
        .reindex(full_range, fill_value=0)
        .astype(float)
    )

    daily.index.name = "Issue_Date"
    daily.name = "Units_Issued"

    return daily


def make_features(daily):
    feat = pd.DataFrame({"y": daily})

    feat["lag_1"] = feat["y"].shift(1)
    feat["lag_7"] = feat["y"].shift(7)

    # Shift first so today's target is not included in its rolling features.
    feat["rolling_mean_7"] = feat["y"].shift(1).rolling(7).mean()
    feat["rolling_mean_14"] = feat["y"].shift(1).rolling(14).mean()

    feat["day_of_week"] = feat.index.dayofweek
    feat["month"] = feat.index.month
    feat["trend_idx"] = np.arange(len(feat))

    return feat


# ---------------------------------------------------------------------------
# MODEL TRAINING, EVALUATION, AND FORECASTING
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def analyze_group(group, usage_df):
    daily = build_daily_series(usage_df, group)

    if daily.empty:
        return {
            "daily": daily,
            "nonzero_days": 0,
            "total_records": 0,
            "reliable": False,
            "mae": None,
            "rmse": None,
            "forecast": pd.Series(dtype=float, name="Forecast"),
            "method": "No usable demand history",
        }

    nonzero_days = int((daily > 0).sum())
    total_records = int((usage_df["Blood_Group"] == group).sum())

    feat = make_features(daily).dropna()
    reliable = nonzero_days >= MIN_NONZERO_DAYS and len(feat) >= 2

    result = {
        "daily": daily,
        "nonzero_days": nonzero_days,
        "total_records": total_records,
        "reliable": reliable,
        "mae": None,
        "rmse": None,
        "forecast": None,
        "method": None,
        "feature_importance": None,
    }

    if reliable:
        X = feat[FEATURE_COLS]
        y = feat["y"]

        split = max(1, int(len(feat) * (1 - TEST_FRACTION)))
        split = min(split, len(feat) - 1)

        # Chronological holdout: no random shuffling.
        X_train = X.iloc[:split]
        X_test = X.iloc[split:]
        y_train = y.iloc[:split]
        y_test = y.iloc[split:]

        model = RandomForestRegressor(
            n_estimators=300,
            max_depth=8,
            random_state=42,
            n_jobs=-1,
        )
        model.fit(X_train, y_train)

        if not X_test.empty:
            predictions = model.predict(X_test)
            result["mae"] = float(mean_absolute_error(y_test, predictions))
            result["rmse"] = float(
                np.sqrt(mean_squared_error(y_test, predictions))
            )

        # Refit on all available feature rows for future forecasting.
        model_full = RandomForestRegressor(
            n_estimators=300,
            max_depth=8,
            random_state=42,
            n_jobs=-1,
        )
        model_full.fit(X, y)
        result["feature_importance"] = (
            pd.Series(model_full.feature_importances_, index=FEATURE_COLS)
            .sort_values(ascending=False)
            .rename("Importance")
        )

        history = daily.copy()
        last_date = history.index.max()
        forecast_rows = []

        for _ in range(FORECAST_HORIZON):
            next_date = last_date + pd.Timedelta(days=1)

            lag_1 = float(history.iloc[-1])
            lag_7 = (
                float(history.iloc[-7])
                if len(history) >= 7
                else float(history.mean())
            )
            rolling_7 = (
                float(history.iloc[-7:].mean())
                if len(history) >= 7
                else float(history.mean())
            )
            rolling_14 = (
                float(history.iloc[-14:].mean())
                if len(history) >= 14
                else float(history.mean())
            )

            next_row = pd.DataFrame(
                [
                    {
                        "lag_1": lag_1,
                        "lag_7": lag_7,
                        "rolling_mean_7": rolling_7,
                        "rolling_mean_14": rolling_14,
                        "day_of_week": next_date.dayofweek,
                        "month": next_date.month,
                        "trend_idx": len(history),
                    }
                ]
            )[FEATURE_COLS]

            predicted_value = max(
                0.0,
                float(model_full.predict(next_row)[0]),
            )

            forecast_rows.append((next_date, predicted_value))
            history.loc[next_date] = predicted_value
            last_date = next_date

        result["forecast"] = pd.Series(
            {date: value for date, value in forecast_rows},
            name="Forecast",
            dtype=float,
        )
        result["method"] = "Random Forest recursive 7-day forecast"

    else:
        # Sparse groups use a transparent historical-average fallback.
        lookback = daily.iloc[-30:] if len(daily) >= 30 else daily
        average_demand = float(lookback.mean())

        last_date = daily.index.max()
        forecast_dates = [
            last_date + pd.Timedelta(days=step)
            for step in range(1, FORECAST_HORIZON + 1)
        ]

        result["forecast"] = pd.Series(
            [average_demand] * FORECAST_HORIZON,
            index=forecast_dates,
            name="Forecast",
            dtype=float,
        )
        result["method"] = (
            "Historical average fallback "
            "(insufficient demand history to train a model)"
        )

    return result


# ---------------------------------------------------------------------------
# RISK CLASSIFICATION
# ---------------------------------------------------------------------------

def classify_risk(current_stock, avg_predicted_daily_demand):
    """
    Classify stock coverage using predicted daily demand.
    This is a rule-based risk category, not a probability.
    """
    if avg_predicted_daily_demand <= 0.01:
        return "LOW RISK", None, "healthy"

    days_of_coverage = current_stock / avg_predicted_daily_demand

    if days_of_coverage < RISK_HIGH_DAYS:
        return "HIGH RISK", days_of_coverage, "critical"

    if days_of_coverage < RISK_MODERATE_DAYS:
        return "MODERATE RISK", days_of_coverage, "warning"

    return "LOW RISK", days_of_coverage, "healthy"


# ---------------------------------------------------------------------------
# PAGE HEADER AND SELECTION
# ---------------------------------------------------------------------------

default_index = blood_groups.index("O+") if "O+" in blood_groups else 0

group = st.selectbox(
    "Blood group",
    blood_groups,
    index=default_index,
)

result = analyze_group(group, usage)

daily = result["daily"]
forecast = result["forecast"]

current_stock = int(
    inventory.loc[
        inventory["Blood_Group"] == group,
        "Quantity",
    ].sum()
)

recent_avg_demand = (
    float(daily.iloc[-7:].mean())
    if len(daily) >= 7
    else float(daily.mean())
)

predicted_total_7d = float(forecast.sum())
predicted_avg_daily = float(forecast.mean())

risk_label, days_of_coverage, risk_key = classify_risk(
    current_stock,
    predicted_avg_daily,
)


# ---------------------------------------------------------------------------
# RELIABILITY NOTICE
# ---------------------------------------------------------------------------

if not result["reliable"]:
    st.warning(
        f"**{group} has limited historical demand.** "
        f"There are only {result['nonzero_days']} days with recorded "
        "issuance in the dataset. A trained forecasting model may not "
        "be reliable, so this page uses a historical-average estimate "
        f"({predicted_avg_daily:.1f} units/day). Treat the forecast and "
        "risk classification as indicative only."
    )


# ---------------------------------------------------------------------------
# KPI CARDS
# ---------------------------------------------------------------------------

def kpi_card(label, value, sub_text=None, sub_class=""):
    sub_html = (
        f'<p class="bp-kpi-sub {sub_class}">● {sub_text}</p>'
        if sub_text
        else ""
    )

    render_html(
        f"""
        <div class="bp-glass bp-kpi-card">
            <p class="bp-kpi-label">{label}</p>
            <p class="bp-kpi-value">{value}</p>
            {sub_html}
        </div>
        """
    )


coverage_display = (
    f"{days_of_coverage:.1f} days"
    if days_of_coverage is not None
    else "N/A"
)

coverage_color = status_color(
    "healthy"
    if risk_key == "healthy"
    else "warning"
    if risk_key == "warning"
    else "critical"
)

kpis = [
    ("Current Stock", f"{current_stock:,} units", group, "bp-teal"),
    (
        "Recent Avg Demand",
        f"{recent_avg_demand:.1f} units/day",
        "last 7 days actual",
        "",
    ),
    (
        "Predicted 7-Day Demand",
        f"{predicted_total_7d:.0f} units",
        f"≈{predicted_avg_daily:.1f} units/day forecast",
        "",
    ),
    (
        "Days of Coverage",
        coverage_display,
        risk_label,
        coverage_color,
    ),
]

for col, (label, value, sub_text, sub_class) in zip(st.columns(4), kpis):
    with col:
        kpi_card(label, value, sub_text, sub_class)

st.write("")


# ---------------------------------------------------------------------------
# HISTORICAL + FORECAST CHART
# ---------------------------------------------------------------------------

with st.container(key="glasscard_forecast_chart"):
    st.markdown(
        f'<p class="bp-section-title">{group} — actual demand '
        "(last 30 days) and 7-day forecast</p>",
        unsafe_allow_html=True,
    )

    recent_actual = daily.iloc[-30:].rename("Actual")
    chart_df = pd.concat([recent_actual, forecast], axis=1)

    st.line_chart(chart_df, height=220)

st.write("")

# ---------------------------------------------------------------------------
# MODEL EXPLANATION — global feature importance for the selected group
# ---------------------------------------------------------------------------

if result.get("feature_importance") is not None:
    with st.container(key="glasscard_feature_importance"):
        st.markdown(
            '<p class="bp-section-title">Model feature importance</p>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Relative feature importance reported by the fitted Random Forest. "
            "These values describe model reliance, not causal effects."
        )
        importance_df = result["feature_importance"].rename_axis("Feature").reset_index()
        st.bar_chart(importance_df.set_index("Feature")["Importance"], height=220)
else:
    st.info(
        "Feature importance is unavailable because this blood group uses "
        "the historical-average fallback rather than a trained Random Forest."
    )

st.write("")


# ---------------------------------------------------------------------------
# SHORTAGE RISK EXPLANATION
# ---------------------------------------------------------------------------

with st.container(key="glasscard_shortage_risk"):
    st.markdown(
        '<p class="bp-section-title">Shortage risk</p>',
        unsafe_allow_html=True,
    )

    chip_colors = {
        "healthy": ("#eafaf0", "#16A34A"),
        "warning": ("#fff6e0", "#B8860B"),
        "critical": ("#fdeaec", "#C41E3A"),
    }

    background_color, foreground_color = chip_colors[risk_key]

    st.markdown(
        f'<span class="bp-chip" '
        f'style="background:{background_color};color:{foreground_color};'
        f'font-weight:600;">{risk_label}</span>',
        unsafe_allow_html=True,
    )

    st.write("")

    if days_of_coverage is None:
        explanation = (
            f"{group} has no meaningful predicted demand over the next "
            f"7 days. Current stock is {current_stock} units, so days of "
            "coverage is not meaningful at this demand level."
        )

    elif risk_label == "HIGH RISK":
        explanation = (
            f"**High risk:** current stock ({current_stock} units) covers "
            f"only **{days_of_coverage:.1f} days** at the predicted demand "
            f"of {predicted_avg_daily:.1f} units/day. This is below the "
            f"{RISK_HIGH_DAYS}-day threshold. Recent actual demand averaged "
            f"{recent_avg_demand:.1f} units/day over the last 7 days."
        )

    elif risk_label == "MODERATE RISK":
        explanation = (
            f"**Moderate risk:** current stock ({current_stock} units) "
            f"covers **{days_of_coverage:.1f} days** at the predicted "
            f"demand of {predicted_avg_daily:.1f} units/day. This is inside "
            f"the {RISK_HIGH_DAYS}- to {RISK_MODERATE_DAYS}-day watch band. "
            f"Recent actual demand averaged {recent_avg_demand:.1f} units/day."
        )

    else:
        explanation = (
            f"**Low risk:** current stock ({current_stock} units) covers "
            f"**{days_of_coverage:.1f} days** at the predicted demand of "
            f"{predicted_avg_daily:.1f} units/day, above the "
            f"{RISK_MODERATE_DAYS}-day threshold."
        )

    st.markdown(explanation)


# ---------------------------------------------------------------------------
# SHARE RESULTS WITH OTHER PAGES THROUGH SESSION STATE
# ---------------------------------------------------------------------------

if "ai_prediction_results" not in st.session_state:
    st.session_state["ai_prediction_results"] = {}

st.session_state["ai_prediction_results"][group] = {
    "current_stock": current_stock,
    "recent_avg_demand": recent_avg_demand,
    "predicted_avg_daily_demand": predicted_avg_daily,
    "predicted_total_7d": predicted_total_7d,
    "days_of_coverage": days_of_coverage,
    "risk_label": risk_label,
    "mae": result["mae"],
    "reliable": result["reliable"],
}