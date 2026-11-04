# SanguiCore

**SanguiCore — AI-Driven Blood Inventory Forecasting and Decision Support System** is a Streamlit prototype for reviewing blood-bank inventory, estimating short-term demand, identifying coverage risk, and supporting operational review.

## Project structure

```text
SanguiCore/
├── Code/
│   ├── app.py
│   ├── home.py
│   ├── utils.py
│   ├── requirements.txt
│   ├── .streamlit/config.toml
│   └── pages/
│       ├── inventory.py
│       ├── ai_prediction.py
│       ├── decision_engine.py
│       ├── emergency_mode.py
│       ├── donor_management.py
│       └── analytics.py
└── Dataset/
    ├── blood_inventory.csv
    ├── blood_usage.csv
    ├── blood_donations.csv
    └── hospital_requests.csv
```

Keep `Code/` and `Dataset/` as sibling folders. `utils.py` resolves the dataset folder relative to its own location.

## Setup and run

From the `Code/` folder:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Data files checked in this build

| Dataset | Rows | Columns |
|---|---:|---:|
| `blood_inventory.csv` | 500 | 7 |
| `blood_usage.csv` | 800 | 6 |
| `blood_donations.csv` | 700 | 6 |
| `hospital_requests.csv` | 1,000 | 7 |

The files contain all eight common ABO/Rh blood groups. The checked CSVs had no missing cells and no duplicate full rows. These are supplied demonstration datasets, not a live feed from a real blood bank.

## Main modules

- **Mission Control (`home.py`)** — high-level inventory/usage/request indicators and a recent historical usage trend.
- **Inventory (`pages/inventory.py`)** — batch records, filters, expiry priorities and stock summary.
- **AI Risk Analysis (`pages/ai_prediction.py`)** — blood-group-specific demand forecasting, evaluation metrics, seven-day forecast and days-of-coverage risk.
- **Decision Engine (`pages/decision_engine.py`)** — rule-based, explainable operational review recommendations and expiry review.
- **Emergency Response (`pages/emergency_mode.py`)** — open requests, stock coverage and expiry concerns in one view.
- **Donor Management (`pages/donor_management.py`)** — donation records and group/month summaries.
- **Analytics (`pages/analytics.py`)** — cross-dataset summaries and trends.

## Forecasting approach

For each blood group, usage is aggregated into a daily time series. The feature set includes previous-day demand (`lag_1`), demand seven days earlier (`lag_7`), prior 7- and 14-day rolling means, day of week, month and a trend index. A Random Forest regressor is used when there are at least 15 non-zero demand days and enough feature rows. Evaluation uses a chronological holdout with MAE and RMSE; future demand is forecast recursively for seven days.

When the history is too sparse, the app uses a clearly labeled historical-average fallback instead of forcing a model. The risk calculation is a rule-based days-of-coverage estimate, not a calibrated probability of shortage. Current defaults are High below 3 days, Moderate from 3 to under 7 days, and Low at 7 days or more. The Mission Control page displays observable risk signals rather than a fabricated confidence percentage. For trained Random Forest models, the AI Risk Analysis page also displays global feature importance; this is not a causal explanation and is not a substitute for local XAI methods such as SHAP or LIME.

## Stock dates and Live Mode

The sidebar toggle switches between two date references:

- **Data Snapshot (default):** uses the newest operational date in the demonstration datasets for expiry calculations.
- **Live Mode:** uses the computer's current date for expiry calculations, excludes expired batches from usable-stock calculations, and shows a clock strip that updates every second.

To prevent the sample inventory from becoming entirely expired as calendar time passes, all date columns in the four synthetic datasets are shifted together at load time. The newest operational record is anchored 25 days before the computer's current date. The same offset is applied to collection, issue, request, donation and expiry dates, preserving the original time gaps and producing a mix of expired, near-expiry and valid inventory batches. The CSV files themselves are not modified.

The clock is live, but the datasets are still synthetic demonstration data, not a live feed from a real blood bank. Forecasts use the shifted historical sample records; Live Mode does not fetch new real-world hospital data. The Inventory page can display expired batch records for review, while stock totals and risk calculations use batches that have not expired as of the selected reference date.

## Code map

- `app.py`: navigation, shared styling, Live Mode toggle and ticking clock.
- `utils.py`: shared data loaders, reference-date logic, usable-stock filtering, thresholds and HTML rendering.
- `home.py`: Mission Control calculations and historical usage chart.
- `pages/ai_prediction.py`: feature engineering, Random Forest training, MAE/RMSE, recursive forecast and risk classification.
- `pages/decision_engine.py`: transparent rules for operational recommendations.

## Limitations and responsible use

This is an academic prototype. Forecasts are estimates, thresholds are project-defined rules, and the donor re-eligibility indicator is illustrative—not medical clearance. The system does not decide which patient receives blood and should not be used for clinical or operational decisions without validation by authorized professionals. Production use would require data validation, security, audit logging, real-time integration and workflow testing.


## Review corrections in this version

- Removed heuristic percentages previously labelled as model confidence.
- Reworded the home-page insight so inventory risk is not incorrectly described as a forecasted demand increase.
- Replaced unsupported automatic transfer quantities with a stock-distribution review prompt. A suggested transfer must be checked against compatibility, demand, policy and human judgement.
- Added Random Forest feature-importance visualisation for blood groups with a trained model, with a clear note that feature importance is not causal.
- Clarified that the donor module analyses donation records; it does not verify donor medical eligibility or provide real-time donor contact/matching.
- Kept the research paper's conceptual XAI framework separate from implemented project features. This prototype does not currently implement SHAP or LIME.
