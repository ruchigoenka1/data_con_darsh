import streamlit as st
import pandas as pd
from io import BytesIO

# -----------------------------
# Page Configuration
# -----------------------------
st.set_page_config(
    page_title="Inventory Ledger Generator",
    layout="wide"
)

st.title("Inventory Ledger Generator")
st.write(
    "Upload the inventory transactions file and enter the opening balance."
)

# -----------------------------
# User Inputs
# -----------------------------
opening_balance = st.number_input(
    "Opening Balance",
    min_value=0,
    value=0,
    step=1
)

uploaded_file = st.file_uploader(
    "Upload Excel or CSV File",
    type=["xlsx", "csv"]
)

# -----------------------------
# Process File
# -----------------------------
if uploaded_file is not None:

    # Read file
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    # Remove leading/trailing spaces from column names
    df.columns = df.columns.str.strip()

    required_columns = [
        "Date",
        "Qty. In (Meter)",
        "Qty. Out (Meter)"
    ]

    missing_columns = [
        col for col in required_columns if col not in df.columns
    ]

    if missing_columns:
        st.error(
            f"The following required columns are missing: {', '.join(missing_columns)}"
        )
        st.stop()

    # Keep only required columns
    df = df[required_columns].copy()

    # Convert date
    df["Date"] = pd.to_datetime(df["Date"])

    opening_list = []
    closing_list = []

    balance = opening_balance

    # Running inventory calculation
    for _, row in df.iterrows():

        opening_list.append(balance)

        balance = (
            balance
            + row["Qty. In (Meter)"]
            - row["Qty. Out (Meter)"]
        )

        closing_list.append(balance)

    # Final Output
    result = pd.DataFrame({
        "Date": df["Date"].dt.date,
        "Opening Balance": opening_list,
        "Demand/Sales": df["Qty. Out (Meter)"].astype(int),
        "Receiving": df["Qty. In (Meter)"].astype(int),
        "Closing Balance": closing_list
    })

    # Convert balances to integers if applicable
    result["Opening Balance"] = result["Opening Balance"].astype(int)
    result["Closing Balance"] = result["Closing Balance"].astype(int)

    st.success("Ledger generated successfully!")

    st.subheader("Preview")

    st.dataframe(
        result,
        use_container_width=True,
        hide_index=True
    )

    # -----------------------------
    # Download Excel
    # -----------------------------
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        result.to_excel(
            writer,
            index=False,
            sheet_name="Inventory Ledger"
        )

        worksheet = writer.sheets["Inventory Ledger"]

        # Auto-fit column widths
        for column_cells in worksheet.columns:
            length = max(len(str(cell.value)) if cell.value is not None else 0
                         for cell in column_cells)
            worksheet.column_dimensions[column_cells[0].column_letter].width = length + 3

    output.seek(0)

    st.download_button(
        label="📥 Download Inventory Ledger",
        data=output,
        file_name="Inventory_Ledger.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
