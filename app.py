import streamlit as st
import pandas as pd
import plotly.express as px
import io
import numpy as np

# --- Page Config ---
st.set_page_config(page_title="Inventory & Backlog Simulator", layout="wide")

st.title("📊 Inventory & Backlog Simulator")

# --- Section 1: Data Upload & Inputs ---
st.markdown("### 1. Data Upload & Configuration")

col1, col2 = st.columns(2)
with col1:
    uploaded_file = st.file_uploader("Upload your data (CSV or Excel)", type=['csv', 'xlsx'])
with col2:
    initial_opening_balance = st.number_input("Enter Initial Opening Balance", min_value=0.0, value=150.0, step=1.0)
    age_windows_input = st.text_input("Age Windows for Graph (comma-separated days)", "7, 14, 30, 60")

if uploaded_file is not None:
    # Read data
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
        
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    
    st.success("File uploaded successfully!")

    # --- Section 2: Simulator 1 - Inventory Ledger ---
    st.markdown("---")
    st.markdown("### 2. Inventory Ledger (Format 1)")
    
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
        
        current_opening_balance = closing_balance
        
    df_ledger = pd.DataFrame(ledger_data)
    st.dataframe(df_ledger, use_container_width=True)
    
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
    st.markdown("### 3. Pending Order Analysis")
    
    pending_orders = [] 
    backlog_table = []
    aging_records = []
    
    current_pending_opening = 0.0
    
    for index, row in df.iterrows():
        current_date = row['Date']
        qty_out = row['Qty. Out (Meter)']
        order_qty = row['Order Qty']
        
        # 1. Add new orders to the queue
        if order_qty > 0:
            pending_orders.append({'date': current_date, 'remaining_qty': order_qty})
            
        # 2. Fulfill orders (FIFO Logic)
        qty_to_fulfill = qty_out
        while qty_to_fulfill > 0 and len(pending_orders) > 0:
            oldest_order = pending_orders[0]
            if oldest_order['remaining_qty'] <= qty_to_fulfill:
                qty_to_fulfill -= oldest_order['remaining_qty']
                pending_orders.pop(0)
            else:
                oldest_order['remaining_qty'] -= qty_to_fulfill
                qty_to_fulfill = 0
                
        # 3. Calculate closing balance
        total_pending = sum(order['remaining_qty'] for order in pending_orders)
        
        # Append to backlog table with Opening Balance included
        backlog_table.append({
            'Date': current_date.strftime('%Y-%m-%d'),
            'Pending Order Opening Balance': current_pending_opening,
            'New Orders Received': order_qty,
            'Orders Fulfilled': qty_out,
            'Pending Order Closing Balance': total_pending
        })
        
        # Update opening balance for the next iteration
        current_pending_opening = total_pending
        
        # 4. Calculate raw aging for the graph
        for order in pending_orders:
            age_days = (current_date - order['date']).days
            aging_records.append({
                'Date': current_date,
                'Age (Days)': age_days,
                'Pending Qty': order['remaining_qty']
            })

    df_backlog = pd.DataFrame(backlog_table)
    st.dataframe(df_backlog, use_container_width=True)
    
    buffer_backlog = io.BytesIO()
    with pd.ExcelWriter(buffer_backlog, engine='openpyxl') as writer:
        df_backlog.to_excel(writer, index=False, sheet_name='Backlog_Analysis')
    
    st.download_button(
        label="📥 Download Backlog Analysis (Excel)",
        data=buffer_backlog.getvalue(),
        file_name="backlog_analysis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # --- Section 4: Aging Graph with Custom Windows ---
    st.markdown("### Backlog Aging Tracking")
    
    if aging_records:
        df_aging = pd.DataFrame(aging_records)
        
        # Parse age windows from user input
        try:
            window_thresholds = [int(x.strip()) for x in age_windows_input.split(',')]
            bins = [-1] + window_thresholds + [float('inf')]
            
            labels = []
            for i in range(len(bins)-1):
                if bins[i+1] == float('inf'):
                    labels.append(f">{bins[i]} Days")
                else:
                    labels.append(f"{bins[i]+1}-{bins[i+1]} Days")
                    
            df_aging['Age Group'] = pd.cut(df_aging['Age (Days)'], bins=bins, labels=labels)
            
            # Aggregate data by Date and Age Group to optimize rendering
            df_grouped = df_aging.groupby(['Date', 'Age Group'], observed=True)['Pending Qty'].sum().reset_index()
            
            # Filter out empty groups for a cleaner legend
            df_grouped = df_grouped[df_grouped['Pending Qty'] > 0]
            
            fig = px.bar(
                df_grouped, 
                x='Date', 
                y='Pending Qty', 
                color='Age Group',
                title='Daily Pending Order Backlog (Segmented by Age Window)',
                labels={'Pending Qty': 'Pending Order Quantity', 'Date': 'Date'},
                color_discrete_sequence=px.colors.sequential.Blues_r 
            )
            
            # Black background styling
            fig.update_layout(
                plot_bgcolor='black',
                paper_bgcolor='black',
                font=dict(color='white'),
                xaxis=dict(showgrid=True, gridcolor='#333333'),
                yaxis=dict(showgrid=True, gridcolor='#333333'),
                legend_title_font_color="white",
                hovermode="x unified"
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
        except ValueError:
            st.error("Please enter valid, comma-separated numbers for the Age Windows (e.g., 7, 14, 30).")
    else:
        st.info("No backlog data available to graph.")
