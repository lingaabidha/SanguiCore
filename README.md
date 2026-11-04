# SanguiCore

### AI-Driven Blood Inventory Forecasting and Decision Support System

SanguiCore is a Python and Streamlit-based blood inventory decision-support prototype designed to help monitor blood availability, analyse historical usage and identify potential inventory risks.

## Key Features
- Blood group inventory monitoring
- Stock shortage and coverage analysis
- Blood batch expiry tracking
- Demand forecasting using Random Forest
- Donor and donation record management
- Hospital request monitoring
- Interactive analytics and visualisations
- Decision-support recommendations
- Snapshot View and Live Mode

## Technologies Used
- Python
- Streamlit
- Pandas
- NumPy
- Scikit-learn
- CSV datasets

## Project Structure
- `Code/` – Application source code and dashboard pages
- `Dataset/` – Sample inventory, usage, donation and hospital request datasets

## How to Run

1. Clone this repository:

```bash
git clone https://github.com/lingaabidha/SanguiCore.git
```

2. Navigate to the project folder:

```bash
cd SanguiCore
```

3. Navigate to the Code folder:

```bash
cd Code
```

4. Install the required dependencies:

```bash
pip install -r requirements.txt
```

5. Run the Streamlit application:

```bash
streamlit run app.py
```

## Dataset Information

This project uses synthetic/sample datasets for academic demonstration. It is not connected to live hospital inventory systems.

## Limitations

Forecasts are estimates, risk categories are rule-based indicators, and operational recommendations require human review. This prototype is not intended for clinical decision-making.

## Future Scope
- Real-time blood bank data integration
- Improved forecasting and validation
- Automated alerts

## Author

**Linga Abidha**

B.Sc. Data Science Student (2024–2027)  
SIES College of Arts, Science & Commerce, Sion, Mumbai
