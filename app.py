import streamlit as st
import pandas as pd

st.title("Inventory Ledger Generator")

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

if uploaded_file:

    # Read file
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    # Keep required columns
    df = df[
        ["Date", "Qty. In (Meter)", "Qty. Out (Meter)"]
    ].copy()

    df["Date"] = pd.to_datetime(df["Date"])

    # Calculate balances
    opening = opening_balance

    opening_list = []
    closing_list = []

    for _, row in df.iterrows():

        opening_list.append(opening)

        closing = (
            opening
            + row["Qty. In (Meter)"]
            - row["Qty. Out (Meter)"]
        )

        closing_list.append(closing)

        opening = closing

    result = pd.DataFrame({
        "Date": df["Date"].dt.date,
        "Opening Balance": opening_list,
        "Qty In": df["Qty. In (Meter)"],
        "Qty Out": df["Qty. Out (Meter)"],
        "Closing Balance": closing_list
    })

    st.subheader("Ledger")

    st.dataframe(result, use_container_width=True)

    excel_name = "Inventory_Ledger.xlsx"

    with pd.ExcelWriter(excel_name, engine="openpyxl") as writer:
        result.to_excel(writer, index=False)

    with open(excel_name, "rb") as f:
        st.download_button(
            "Download Ledger",
            f,
            file_name=excel_name
        )
