import streamlit as st
import pandas as pd
import plotly.express as px
import io

# --- Page Config ---
st.set_page_config(page_title="Inventory & Backlog Simulator", layout="wide")

st.title("📊 Inventory & Backlog Simulator")

# --- Section 1: Data Upload & Inputs ---
st.markdown("### 1. Data Upload & Configuration")
uploaded_file = st.file_uploader("Upload your data (CSV or Excel)", type=['csv', 'xlsx'])
initial_opening_balance = st.number_input("Enter Initial Opening Balance", min_value=0.0, value=150.0, step=1.0)

if uploaded_file is not None:
    # Read data
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
        
    # Ensure date is datetime
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    
    st.success("File uploaded successfully!")

    # --- Section 2: Simulator 1 - Inventory Ledger ---
    st.markdown("---")
    st.markdown("### 2. Inventory Ledger (Format 1)")
    
    # Initialize the target dataframe
    ledger_data = []
    current_opening_balance = initial_opening_balance
    
    for index, row in df.iterrows():
        date = row['Date']
        receiving = row['Qty. In (Meter)']
        demand = row['Qty. Out (Meter)']
        
        closing_balance = current_opening_balance - demand + receiving
        
        ledger_data.append({
            'Date': date.strftime('%Y-%m-%d'),
            'Opening Balance': current_opening_balance,
            'Demand/Sales': demand,
            'Receiving': receiving,
            'Closing Balance': closing_balance
        })
        
        # Next day's opening balance is today's closing balance
        current_opening_balance = closing_balance
        
    df_ledger = pd.DataFrame(ledger_data)
    st.dataframe(df_ledger, use_container_width=True)
    
    # Download Button for First Excel
    buffer_ledger = io.BytesIO()
    with pd.ExcelWriter(buffer_ledger, engine='openpyxl') as writer:
        df_ledger.to_excel(writer, index=False, sheet_name='Inventory_Ledger')
    
    st.download_button(
        label="📥 Download Inventory Ledger (Excel)",
        data=buffer_ledger.getvalue(),
        file_name="inventory_ledger.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # --- Section 3: Simulator 2 - Backlog & Aging Analysis ---
    st.markdown("---")
    st.markdown("### 3. Pending Order Closing Balance & Backlog Aging")
    
    pending_orders = [] # Will store dicts: {'date': date, 'remaining_qty': qty}
    backlog_table = []
    aging_records = []
    
    for index, row in df.iterrows():
        current_date = row['Date']
        qty_out = row['Qty. Out (Meter)']
        order_qty = row['Order Qty']
        
        # 1. Add new orders to the queue
        if order_qty > 0:
            pending_orders.append({'date': current_date, 'remaining_qty': order_qty})
            
        # 2. Fulfill orders (FIFO Logic) using Qty. Out
        qty_to_fulfill = qty_out
        while qty_to_fulfill > 0 and len(pending_orders) > 0:
            oldest_order = pending_orders[0]
            if oldest_order['remaining_qty'] <= qty_to_fulfill:
                # Fulfill entirely and remove from queue
                qty_to_fulfill -= oldest_order['remaining_qty']
                pending_orders.pop(0)
            else:
                # Fulfill partially
                oldest_order['remaining_qty'] -= qty_to_fulfill
                qty_to_fulfill = 0
                
        # 3. Calculate closing balance of pending orders
        total_pending = sum(order['remaining_qty'] for order in pending_orders)
        
        # Append to backlog table
        backlog_table.append({
            'Date': current_date.strftime('%Y-%m-%d'),
            'New Orders Received': order_qty,
            'Orders Fulfilled': qty_out,
            'Pending Order Closing Balance': total_pending
        })
        
        # 4. Calculate aging for the current day's remaining queue
        for order in pending_orders:
            age_days = (current_date - order['date']).days
            aging_records.append({
                'Date': current_date,
                'Age (Days)': age_days,
                'Pending Qty': order['remaining_qty']
            })

    # Render Table
    df_backlog = pd.DataFrame(backlog_table)
    st.dataframe(df_backlog, use_container_width=True)
    
    # Download Button for Second Excel
    buffer_backlog = io.BytesIO()
    with pd.ExcelWriter(buffer_backlog, engine='openpyxl') as writer:
        df_backlog.to_excel(writer, index=False, sheet_name='Backlog_Analysis')
    
    st.download_button(
        label="📥 Download Backlog Analysis (Excel)",
        data=buffer_backlog.getvalue(),
        file_name="backlog_analysis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # --- Section 4: Aging Graph ---
    st.markdown("### Backlog Aging Tracking")
    
    if aging_records:
        df_aging = pd.DataFrame(aging_records)
        
        # Create a stacked bar chart using Plotly
        fig = px.bar(
            df_aging, 
            x='Date', 
            y='Pending Qty', 
            color='Age (Days)',
            title='Daily Pending Order Backlog (Segmented by Age)',
            labels={'Pending Qty': 'Pending Order Quantity', 'Date': 'Date'},
            color_continuous_scale='Blues'
        )
        
        # Apply minimalist styling
        fig.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            xaxis=dict(showgrid=True, gridcolor='#e5e5e5'),
            yaxis=dict(showgrid=True, gridcolor='#e5e5e5'),
            font=dict(color='#333333'),
            hovermode="x unified"
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No backlog data available to graph.")
else:
    st.info("Please upload a file to run the simulators.")
