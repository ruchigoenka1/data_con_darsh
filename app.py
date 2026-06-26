import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Inventory Ledger Generator", layout="wide")

st.title("Inventory Ledger Generator")

st.write("Upload your inventory transaction file.")

opening_balance = st.number_input(
    "Opening Balance (Meter)",
    min_value=0.0,
    value=0.0,
    step=1.0
)

uploaded_file = st.file_uploader(
    "Upload Excel or CSV",
    type=["xlsx", "csv"]
)

if uploaded_file is not None:

    # Read file
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    # Remove extra spaces from column names
    df.columns = df.columns.str.strip()

    required_columns = [
        "Date",
        "Qty. In (Meter)",
        "Qty. Out (Meter)"
    ]

    missing = [col for col in required_columns if col not in df.columns]

    if missing:
        st.error(f"Missing columns: {missing}")
        st.stop()

    # Keep only required columns
    df = df[required_columns].copy()

    df["Date"] = pd.to_datetime(df["Date"])

    opening_list = []
    closing_list = []

    current_balance = opening_balance

    for _, row in df.iterrows():

        opening_list.append(current_balance)

        closing = (
            current_balance
            + row["Qty. In (Meter)"]
            - row["Qty. Out (Meter)"]
        )

        closing_list.append(closing)

        current_balance = closing

    # Output matching your template
    result = pd.DataFrame({
        "Date": df["Date"].dt.date,
        "Demand": df["Qty. Out (Meter)"],
        "Stock Received": df["Qty. In (Meter)"],
        "Opening Balance": opening_list,
        "Closing Balance": closing_list
    })

    st.success("Ledger generated successfully.")

    st.dataframe(result, use_container_width=True)

    # Create Excel in memory
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        result.to_excel(writer, index=False, sheet_name="Ledger")

    output.seek(0)

    st.download_button(
        label="📥 Download Ledger",
        data=output,
        file_name="Inventory_Ledger.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
