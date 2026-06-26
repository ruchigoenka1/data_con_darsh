import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
import numpy as np

# --- Page Config ---
st.set_page_config(page_title="Inventory & Backlog Simulator", layout="wide")

st.title("📊 Inventory & Backlog Simulator")

# --- Dynamic Data Generation Engine ---
def generate_dynamic_data(demand_avg, demand_std, rop, supply_qty, lead_time=14):
    """Simulates a continuous review system to generate 90 days of realistic data."""
    dates = pd.date_range(start="2026-04-01", periods=90)
    
    # Generate Customer Orders (Demand) with some natural variance
    order_qty = np.maximum(0, np.random.normal(demand_avg, demand_std, 90)).astype(int)
    
    qty_in = np.zeros(90, dtype=int)
    qty_out = np.zeros(90, dtype=int)
    
    # Initial state logic
    current_inv = int(rop * 1.25)
    pending_supply = []  # Tracks (arrival_day, quantity)
    
    # Assume dispatch capacity is slightly higher than average demand to process backlogs
    dispatch_capacity = int(demand_avg * 1.2)
    
    for day in range(90):
        # 1. Receive incoming supply if lead time has elapsed
        for arr_day, sq in pending_supply:
            if arr_day == day:
                qty_in[day] += sq
                current_inv += sq
                
        pending_supply = [ps for ps in pending_supply if ps[0] > day]
        
        # 2. Check Inventory Position against ROP
        virtual_inv = current_inv + sum(sq for _, sq in pending_supply)
        if virtual_inv <= rop:
            pending_supply.append((day + lead_time, supply_qty))
            
        # 3. Fulfill Orders (Qty. Out) bounded by physical inventory and plant capacity
        qty_out[day] = min(current_inv, dispatch_capacity)
        current_inv -= qty_out[day]

    return pd.DataFrame({
        "Date": dates,
        "Qty. In (Meter)": qty_in,
        "Qty. Out (Meter)": qty_out,
        "Order Qty": order_qty
    }), int(rop * 1.25)

# --- Sidebar Control Panel ---
st.sidebar.header("🛠️ Data Controls")

if 'data_source_radio' not in st.session_state:
    st.session_state.data_source_radio = "Upload File"
    
if 'sim_data' not in st.session_state:
    st.session_state.sim_data = None
    
if 'sim_opening_balance' not in st.session_state:
    st.session_state.sim_opening_balance = 0.0

def reset_app_state():
    st.session_state.data_source_radio = "Upload File"
    st.session_state.sim_data = None

st.sidebar.button("🔄 Reset Simulator", on_click=reset_app_state)

data_choice = st.sidebar.radio(
    "Choose Data Source:",
    ["Upload File", "Dynamic Simulation"],
    key="data_source_radio"
)

# Variables for main logic
df = None
active_opening_balance = 0.0

if data_choice == "Upload File":
    active_opening_balance = st.sidebar.number_input("Initial Opening Balance", min_value=0.0, value=150.0, step=1.0)
    uploaded_file = st.file_uploader("Upload your data (CSV or Excel)", type=['csv', 'xlsx'])
    
    if uploaded_file is not None:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        df['Date'] = pd.to_datetime(df['Date'])
        
elif data_choice == "Dynamic Simulation":
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Simulation Parameters")
    
    col_a, col_b = st.sidebar.columns(2)
    with col_a:
        demand_mean = st.number_input("Demand Avg", value=120, step=10)
        rop = st.number_input("Reorder Point", value=500, step=50)
    with col_b:
        demand_std = st.number_input("Demand Std Dev", value=15, step=5)
        supply_qty = st.number_input("Supply Qty", value=2000, step=100)
        
    calculated_opening = int(rop * 1.25)
    st.sidebar.info(f"Opening Balance is locked to **{calculated_opening}** (1.25 × ROP).")
    
    if st.sidebar.button("⚙️ Generate Data"):
        generated_df, initial_bal = generate_dynamic_data(demand_mean, demand_std, rop, supply_qty)
        st.session_state.sim_data = generated_df
        st.session_state.sim_opening_balance = initial_bal
        
    if st.session_state.sim_data is not None:
        df = st.session_state.sim_data
        active_opening_balance = st.session_state.sim_opening_balance
    else:
        st.info("👈 Please set your parameters and click **Generate Data** in the sidebar.")

# --- Main Simulator Engine ---
if df is not None:
    df = df.sort_values('Date').reset_index(drop=True)
    st.success("Data ready for simulation!")

    # --- Section 2: Simulator 1 - Inventory Ledger ---
    st.markdown("---")
    st.markdown("### 2. Inventory Ledger (Format 1)")
    
    ledger_data = []
    current_opening_balance = active_opening_balance
    
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

    # --- Section 3: Simulator 2 - Fixed Backlog Flow Engine ---
    st.markdown("---")
    st.markdown("### 3. Pending Order Analysis")
    
    pending_orders_queue = [] 
    order_history = []  
    backlog_table = []
    aging_records = []
    
    order_id_counter = 0
    
    for index, row in df.iterrows():
        current_date = row['Date']
        qty_out = row['Qty. Out (Meter)']
        order_qty = row['Order Qty']
        
        if order_qty > 0:
            order_node = {
                'id': order_id_counter,
                'placed_date': current_date,
                'total_qty': order_qty,
                'remaining_qty': order_qty,
                'fully_fulfilled_date': None
            }
            pending_orders_queue.append(order_node)
            order_history.append(order_node)
            order_id_counter += 1
            
        qty_to_fulfill = qty_out
        actual_fulfilled_today = 0
        
        while qty_to_fulfill > 0 and len(pending_orders_queue) > 0:
            oldest_order = pending_orders_queue[0]
            if oldest_order['remaining_qty'] <= qty_to_fulfill:
                qty_to_fulfill -= oldest_order['remaining_qty']
                actual_fulfilled_today += oldest_order['remaining_qty']
                oldest_order['remaining_qty'] = 0
                oldest_order['fully_fulfilled_date'] = current_date
                pending_orders_queue.pop(0)
            else:
                oldest_order['remaining_qty'] -= qty_to_fulfill
                actual_fulfilled_today += qty_to_fulfill
                qty_to_fulfill = 0
                
        total_pending = sum(item['remaining_qty'] for item in pending_orders_queue)
        
        backlog_table.append({
            'Date': current_date.strftime('%Y-%m-%d'),
            'New Orders Received': order_qty,
            'Orders Fulfilled': actual_fulfilled_today,
            'Pending Order Closing Balance': total_pending
        })
        
        for order in pending_orders_queue:
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

    # --- Combined Flow Chart (Line + Bar) ---
    st.markdown("### Daily Backlog Flow (In, Out & Closing Balance)")
    
    fig_flow = go.Figure()
    fig_flow.add_trace(go.Bar(
        x=df_backlog['Date'], y=df_backlog['New Orders Received'],
        name='New Orders (In)', marker_color='#4a90e2', opacity=0.7
    ))
    fig_flow.add_trace(go.Scatter(
        x=df_backlog['Date'], y=df_backlog['Orders Fulfilled'],
        mode='lines+markers', name='Orders Fulfilled (Out)', line=dict(color='#27ae60', width=2)
    ))
    fig_flow.add_trace(go.Scatter(
        x=df_backlog['Date'], y=df_backlog['Pending Order Closing Balance'],
        mode='lines', name='Closing Balance', line=dict(color='#e74c3c', width=4)
    ))
    
    fig_flow.update_layout(
        plot_bgcolor='black', paper_bgcolor='black', font=dict(color='white'),
        xaxis=dict(showgrid=True, gridcolor='#333333'), yaxis=dict(showgrid=True, gridcolor='#333333'),
        hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_flow, use_container_width=True)

    # --- Section 4: Advanced Fulfillment & Aging Analytics ---
    st.markdown("---")
    st.markdown("### 4. Backlog Aging & Lead-Time Analytics")
    
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
                df_grouped, x='Date', y='Pending Qty', color='Age Group',
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
            
    completed_orders_data = []
    for order in order_history:
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
        
        fig_bubble = px.scatter(
            df_orders, x='Order Date', y='Days to Fulfill',
            size='Order Size (Meters)', color='Days to Fulfill',
            color_continuous_scale=['blue', 'red'],
            title='Order Fulfillment Velocity (Bubble Size = Order Quantity)',
            labels={'Days to Fulfill': 'Days Taken to Clear'},
            hover_data=['Order Size (Meters)', 'Status']
        )
        fig_bubble.update_layout(
            plot_bgcolor='black', paper_bgcolor='black', font=dict(color='white'),
            xaxis=dict(showgrid=True, gridcolor='#333333'), yaxis=dict(showgrid=True, gridcolor='#333333')
        )
        fig_bubble.update_traces(marker=dict(sizemin=5))
        st.plotly_chart(fig_bubble, use_container_width=True)
            
        fig_hist = px.histogram(
            df_orders, x='Days to Fulfill',
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
