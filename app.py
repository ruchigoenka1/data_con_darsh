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

    # --- Section 3: Simulator 2 - Backlog & Fulfillment Tracking ---
    st.markdown("---")
    st.markdown("### 3. Pending Order Analysis")
    
    pending_orders = [] # Queue for daily unfulfilled tracking
    order_history = []  # Tracks exact life cycle of each distinct order row
    backlog_table = []
    aging_records = []
    
    current_pending_opening = 0.0
    order_id_counter = 0
    
    for index, row in df.iterrows():
        current_date = row['Date']
        qty_out = row['Qty. Out (Meter)']
        order_qty = row['Order Qty']
        
        # 1. Register new order if present
        if order_qty > 0:
            order_node = {
                'id': order_id_counter,
                'placed_date': current_date,
                'total_qty': order_qty,
                'remaining_qty': order_qty,
                'fully_fulfilled_date': None
            }
            pending_orders.append(order_node)
            order_history.append(order_node)
            order_id_counter += 1
            
        # 2. Fulfill orders via FIFO using Qty. Out
        qty_to_fulfill = qty_out
        while qty_to_fulfill > 0 and len(pending_orders) > 0:
            oldest_order = pending_orders[0]
            if oldest_order['remaining_qty'] <= qty_to_fulfill:
                qty_to_fulfill -= oldest_order['remaining_qty']
                oldest_order['remaining_qty'] = 0
                oldest_order['fully_fulfilled_date'] = current_date
                pending_orders.pop(0)
            else:
                oldest_order['remaining_qty'] -= qty_to_fulfill
                qty_to_fulfill = 0
                
        # 3. Calculate metrics for the summary table
        total_pending = sum(order['remaining_qty'] for order in pending_orders)
        
        backlog_table.append({
            'Date': current_date.strftime('%Y-%m-%d'),
            'Pending Order Opening Balance': current_pending_opening,
            'New Orders Received': order_qty,
            'Orders Fulfilled': qty_out,
            'Pending Order Closing Balance': total_pending
        })
        
        current_pending_opening = total_pending
        
        # 4. Snapshot current queue state for the daily aging graph
        for order in pending_orders:
            age_days = (current_date - order['placed_date']).days
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

    # --- Section 4: Advanced Fulfillment & Aging Analytics ---
    st.markdown("---")
    st.markdown("### 4. Backlog Aging & Lead-Time Analytics")
    
    # 1. Running Backlog Graph Controls
    age_windows_input = st.text_input("Age Windows for Backlog Graph (comma-separated days)", "7, 14, 30, 60")
    
    if aging_records:
        df_aging = pd.DataFrame(aging_records)
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
            df_grouped = df_aging.groupby(['Date', 'Age Group'], observed=True)['Pending Qty'].sum().reset_index()
            df_grouped = df_grouped[df_grouped['Pending Qty'] > 0]
            
            fig_backlog = px.bar(
                df_grouped, 
                x='Date', 
                y='Pending Qty', 
                color='Age Group',
                title='Daily Pending Order Backlog (Segmented by Age Window)',
                labels={'Pending Qty': 'Pending Order Quantity'},
                color_discrete_sequence=px.colors.sequential.Blues_r 
            )
            fig_backlog.update_layout(
                plot_bgcolor='black', paper_bgcolor='black', font=dict(color='white'),
                xaxis=dict(showgrid=True, gridcolor='#333333'), yaxis=dict(showgrid=True, gridcolor='#333333')
            )
            st.plotly_chart(fig_backlog, use_container_width=True)
        except ValueError:
            st.error("Please check your age window formatting.")
            
    # Compile analytical data for completed/tracked orders
    completed_orders_data = []
    for order in order_history:
        # If still unfulfilled at the end of the timeline, compute days relative to final date
        end_date = order['fully_fulfilled_date'] if order['fully_fulfilled_date'] else df['Date'].max()
        days_to_fulfill = (end_date - order['placed_date']).days
        
        completed_orders_data.append({
            'Order Date': order['placed_date'],
            'Order Size (Meters)': order['total_qty'],
            'Days to Fulfill': days_to_fulfill,
            'Status': 'Fully Fulfilled' if order['fully_fulfilled_date'] else 'Still Pending'
        })
        
    if completed_orders_data:
        df_orders = pd.DataFrame(completed_orders_data)
        
        st.markdown("---")
        st.markdown("### 5. Order Size vs. Fulfillment Speed Diagnostics")
        
        graph_col1, graph_col2 = st.columns(2)
        
        with graph_col1:
            # Bubble Scatter Plot
            fig_bubble = px.scatter(
                df_orders,
                x='Order Date',
                y='Days to Fulfill',
                size='Order Size (Meters)',
                color='Days to Fulfill',
                color_continuous_scale='Blues',
                title='Order Fulfillment Velocity (Bubble Size = Order Quantity)',
                labels={'Days to Fulfill': 'Days Taken to Clear'},
                hover_data=['Order Size (Meters)', 'Status']
            )
            fig_bubble.update_layout(
                plot_bgcolor='black', paper_bgcolor='black', font=dict(color='white'),
                xaxis=dict(showgrid=True, gridcolor='#333333'), yaxis=dict(showgrid=True, gridcolor='#333333')
            )
            # Ensure bubble markers are noticeable
            fig_bubble.update_traces(marker=dict(sizemin=5))
            st.plotly_chart(fig_bubble, use_container_width=True)
            
        with graph_col2:
            # Distribution Histogram
            fig_hist = px.histogram(
                df_orders,
                x='Days to Fulfill',
                color_discrete_sequence=['#2b5c8f'],
                title='Fulfillment Lead Time Frequency Distribution',
                labels={'Days to Fulfill': 'Days Taken to Fulfill Order', 'count': 'Number of Orders'},
                nbins=15
            )
            fig_hist.update_layout(
                plot_bgcolor='black', paper_bgcolor='black', font=dict(color='white'),
                xaxis=dict(showgrid=True, gridcolor='#333333'), yaxis=dict(showgrid=True, gridcolor='#333333'),
                bargap=0.1
            )
            st.plotly_chart(fig_hist, use_container_width=True)
            
else:
    st.info("Please upload a file to run the simulators.")
