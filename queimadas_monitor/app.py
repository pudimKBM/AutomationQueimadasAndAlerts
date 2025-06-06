import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
import time # For last refresh time
import matplotlib.pyplot as plt
import os
import pydeck as pdk
import asyncio # Required for running async code if Streamlit doesn't auto-handle a context
import aiohttp # Required for creating a session for async collector functions

# Attempt to import project modules.
# This assumes app.py is run from the root of the 'queimadas_monitor' project.
try:
    from data_collection.collector import fetch_daily_fire_csv, fetch_10min_fire_csv, fetch_all_10min_slots_for_day
    from config import RAW_DATA_DIR, RISK_LEVELS # RISK_LEVELS pode ser usado para ordenação ou filtros
    from risk_assessment.assessor import aplica_avaliacao_risco_df
except ModuleNotFoundError:
    st.error("Error importing project modules. Ensure Streamlit is run from the 'queimadas_monitor' root folder.")
    st.stop() # Stop Streamlit script execution

@st.cache_data # Cache to avoid reloading/reprocessing data unnecessarily
def load_data(csv_path: str) -> pd.DataFrame | None:
    """Loads data from a CSV file into a Pandas DataFrame."""
    try:
        # INPE files often use 'latin1' or 'iso-8859-1' encoding
        # Try 'utf-8' first, then 'latin1' as a fallback
        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(csv_path, encoding='latin1')
        
        # Standardize and convert date/time columns
        date_col_found = False
        # Common date/time column names in INPE files
        possible_date_cols = {'datahora': 'event_datetime', 'data_hora_gmt': 'event_datetime', 'data': 'event_datetime'}
        df.rename(columns=possible_date_cols, inplace=True)

        if 'event_datetime' in df.columns:
            try:
                df['event_datetime'] = pd.to_datetime(df['event_datetime'])
                df['data_ocorrencia'] = df['event_datetime'].dt.date
                df['hora_ocorrencia'] = df['event_datetime'].dt.hour
                date_col_found = True
            except Exception as e:
                st.warning(f"Could not convert 'event_datetime' column to datetime: {e}")
        
        if not date_col_found:
            # Attempt to find any column that looks like a date if standard ones fail
            for col in df.columns:
                if 'date' in col.lower() or 'data' in col.lower() or 'time' in col.lower() or 'hora' in col.lower():
                    try:
                        # A more robust check or specific parsing might be needed here
                        df['event_datetime'] = pd.to_datetime(df[col])
                        df['data_ocorrencia'] = df['event_datetime'].dt.date
                        df['hora_ocorrencia'] = df['event_datetime'].dt.hour
                        st.info(f"Used column '{col}' as 'event_datetime'.")
                        date_col_found = True
                        break
                    except Exception:
                        continue # Try next potential date column
            if not date_col_found:
                 st.warning("No primary date/time column ('datahora', 'data_hora_gmt', 'data') found or processed as 'event_datetime'.")


        # Ensure lat/lon are numeric
        for col_coord in ['lat', 'latitude', 'lon', 'longitude']:
            if col_coord in df.columns:
                df[col_coord] = pd.to_numeric(df[col_coord], errors='coerce')
        
        # Standardize lat/lon column names
        df.rename(columns={'latitude': 'lat', 'longitude': 'lon'}, inplace=True)

        return df
    except FileNotFoundError:
        st.error(f"CSV file not found at: {csv_path}")
        return None
    except pd.errors.EmptyDataError:
        st.warning(f"The CSV file is empty: {csv_path}")
        return None
    except Exception as e:
        st.error(f"Error loading CSV ({csv_path}): {e}")
        return None

# @st.cache_data # Cache to avoid re-downloads if files already exist - REMOVED FOR NOW
async def fetch_data_for_range(start_date: date, end_date: date) -> pd.DataFrame | None:
    """Downloads and combines data for a date range using async collector."""
    all_dfs = []
    status_messages = []
    
    progress_bar = st.progress(0)
    num_days = (end_date - start_date).days + 1
    
    async with aiohttp.ClientSession() as session: # Create session for async calls
        tasks = []
        for i in range(num_days):
            current_date_iter = start_date + timedelta(days=i)
            tasks.append(fetch_daily_fire_csv(current_date_iter, session))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            current_date_iter = start_date + timedelta(days=i)
            status_messages.append(f"Processing data for {current_date_iter.strftime('%d/%m/%Y')}...")
            # st.text("\n".join(status_messages[-1:])) # Can be noisy, consider logging instead or a single status line

            if isinstance(result, str) and os.path.exists(result):
                df_day = load_data(result) # load_data is sync
                if df_day is not None and not df_day.empty:
                    all_dfs.append(df_day)
                elif df_day is not None and df_day.empty:
                    status_messages.append(f"  -> No fire spots registered for {current_date_iter.strftime('%d/%m/%Y')}.")
                    # st.text("\n".join(status_messages[-1:]))
            elif isinstance(result, Exception):
                st.warning(f"Failed to fetch data for {current_date_iter.strftime('%d/%m/%Y')}: {result}")
            
            progress_bar.progress((i + 1) / num_days)
    
    # Clear progress bar and status messages after completion
    # progress_bar.empty() # Or set to 1.0
    # st.empty() # To clear st.text messages if they were in a placeholder

    if not all_dfs:
        st.error("No data was loaded for the selected range.")
        return None
    
    combined_df = pd.concat(all_dfs, ignore_index=True)
    st.success(f"Data from {start_date.strftime('%d/%m/%Y')} to {end_date.strftime('%d/%m/%Y')} combined. Total of {len(combined_df)} fire spots.")
    return combined_df

# @st.cache_data(ttl=600) # Cache for 10 minutes for aggregated 10min data - REMOVED FOR NOW
async def load_and_combine_10min_data_for_days(days_list: list[date]) -> pd.DataFrame | None:
    """Loads and combines all 10-minute data for a list of days asynchronously."""
    all_10min_dfs = []
    total_files_with_data = 0
    
    progress_text_area = st.empty() # Placeholder for dynamic status messages
    messages = []

    async with aiohttp.ClientSession() as session: # Create session for async calls
        for target_day in days_list:
            messages.append(f"Fetching 10-min data for {target_day.strftime('%Y-%m-%d')}...")
            progress_text_area.info("\n".join(messages)) # Use st.info or st.status for better UI
            
            list_of_files = await fetch_all_10min_slots_for_day(target_day, session)
            
            day_dfs_count = 0
            if list_of_files: 
                for file_path in list_of_files:
                    df_slot = load_data(file_path) 
                    if df_slot is not None and not df_slot.empty:
                        all_10min_dfs.append(df_slot)
                        day_dfs_count +=1
            
            if day_dfs_count > 0:
                total_files_with_data += day_dfs_count
                messages.append(f"  -> {day_dfs_count} files with data processed for {target_day.strftime('%Y-%m-%d')}.")
            else:
                messages.append(f"  -> No 10-min data files with content found for {target_day.strftime('%Y-%m-%d')}.")
            progress_text_area.info("\n".join(messages))

    progress_text_area.empty() # Clear the status messages area

    if not all_10min_dfs:
        st.info("No 10-minute data found for the selected days.")
        return None

    combined_df = pd.concat(all_10min_dfs, ignore_index=True)
    if 'event_datetime' in combined_df.columns:
        combined_df = combined_df.sort_values(by='event_datetime', ascending=False)
    st.success(f"Total of {len(combined_df)} 10-minute fire spots loaded from {total_files_with_data} files.")
    return combined_df

# --- Main App ---
st.set_page_config(layout="wide", page_title="INPE Fire Spot Monitor")
st.title("🔥 INPE Fire Spot Monitor")

# Initialize session state for assessed data if not already present
if 'df_total_daily_assessed' not in st.session_state:
    st.session_state.df_total_daily_assessed = None
if 'df_10min_aggregated' not in st.session_state: # This already exists from previous logic
    st.session_state.df_10min_aggregated = None
if 'last_10min_refresh_time' not in st.session_state:
    st.session_state.last_10min_refresh_time = None


tab1, tab2, tab3 = st.tabs(["Periodic Report (Daily)", "10-Minute Monitoring", "🚨 Risk Alerts"])


with tab1:
    st.header("📊 Consolidated Periodic Report (Daily Data)")
    st.caption("This panel downloads, processes, and visualizes daily fire spot data from INPE for Brazil, aggregated over a date range.")

    st.sidebar.header("🗓️ Daily Report")
    today = date.today()
    min_selectable_date = date(2000,1,1) 

    default_start_date = today - timedelta(days=7) if today - timedelta(days=7) >= min_selectable_date else min_selectable_date
    default_end_date = today - timedelta(days=1) if today - timedelta(days=1) >= default_start_date else default_start_date

    start_date_daily = st.sidebar.date_input("Start Date (Daily):", 
                                    default_start_date, 
                                    min_value=min_selectable_date, 
                                    max_value=today,
                                    key="daily_start_date")
    end_date_daily = st.sidebar.date_input("End Date (Daily):", 
                                    default_end_date, 
                                    min_value=start_date_daily, 
                                    max_value=today,
                                    key="daily_end_date")

    # Helper async function to be called by asyncio.run()
    async def _get_daily_report_data(start_dt: date, end_dt: date):
        return await fetch_data_for_range(start_dt, end_dt)

    if st.sidebar.button("📊 Generate Daily Report", key="fetch_daily_button"):
        if start_date_daily > end_date_daily:
            st.sidebar.error("Start date cannot be after end date.")
        else:
            st.subheader(f"Report for period: {start_date_daily.strftime('%d/%m/%Y')} to {end_date_daily.strftime('%d/%m/%Y')}")
            df_total_daily = None # Initialize
            with st.spinner("Fetching and combining daily data... Please wait."):
                df_total_daily = asyncio.run(_get_daily_report_data(start_date_daily, end_date_daily))
            
            if df_total_daily is not None and not df_total_daily.empty:
                with st.spinner("Assessing risk for daily data..."):
                    df_total_daily = aplica_avaliacao_risco_df(df_total_daily)
                st.session_state.df_total_daily_assessed = df_total_daily # Store for alerts tab
            else:
                st.session_state.df_total_daily_assessed = None # Clear if no data
            
            # Use the locally scoped df_total_daily for immediate display
            if df_total_daily is not None and not df_total_daily.empty:
                st.markdown("#### Combined Data Preview (Sample)")
                display_limit = min(10, len(df_total_daily))
                st.dataframe(df_total_daily.head(display_limit)) 
                st.write(f"Total fire spots registered in the period: **{len(df_total_daily)}**")

                # Summary of risk levels
                if 'criticidade' in df_total_daily.columns:
                    st.markdown("##### Risk Level Summary (Daily Data)")
                    risk_counts_daily = df_total_daily['criticidade'].value_counts().reindex(list(RISK_LEVELS.keys()), fill_value=0)
                    st.bar_chart(risk_counts_daily)

                st.markdown("---")
                st.markdown("#### Period Analyses")
                
                analysis_cols = st.columns(2)
                with analysis_cols[0]:
                    if 'estado' in df_total_daily.columns:
                        st.markdown("##### Fire Spots by State")
                        focos_por_estado = df_total_daily['estado'].value_counts().sort_values(ascending=False)
                        st.bar_chart(focos_por_estado)
                    else:
                        st.warning("Column 'estado' not found.")

                    if 'bioma' in df_total_daily.columns:
                        st.markdown("##### Fire Spots by Biome")
                        focos_por_bioma = df_total_daily['bioma'].value_counts().sort_values(ascending=False)
                        st.bar_chart(focos_por_bioma)
                    else:
                        st.warning("Column 'bioma' not found.")
                
                with analysis_cols[1]:
                    if 'hora_ocorrencia' in df_total_daily.columns:
                        st.markdown("##### Fire Spots by Hour of Day (UTC)")
                        hora_data = df_total_daily['hora_ocorrencia'].dropna().astype(int)
                        if not hora_data.empty:
                            focos_por_hora = hora_data.value_counts().sort_index()
                            st.bar_chart(focos_por_hora)
                        else:
                            st.info("No valid hour of occurrence data.")
                    else:
                        st.warning("Column 'hora_ocorrencia' not found.")

                    if 'frp' in df_total_daily.columns:
                        st.markdown("##### FRP Distribution (Fire Radiative Power)")
                        frp_data = pd.to_numeric(df_total_daily['frp'], errors='coerce').dropna()
                        if not frp_data.empty:
                            fig, ax = plt.subplots()
                            upper_frp_limit = frp_data.quantile(0.99) if frp_data.quantile(0.99) > frp_data.min() else frp_data.max()
                            ax.hist(frp_data, bins=50, range=(frp_data.min(), upper_frp_limit)) 
                            ax.set_title('FRP Distribution (up to 99th percentile)')
                            ax.set_xlabel('FRP'); ax.set_ylabel('Frequency')
                            st.pyplot(fig)
                        else:
                            st.info("No valid FRP data for histogram.")
                    else:
                        st.info("Column 'frp' not found for severity analysis.")

                if 'data_ocorrencia' in df_total_daily.columns:
                    st.markdown("##### Fire Spots per Day")
                    df_total_daily['data_ocorrencia_dt'] = pd.to_datetime(df_total_daily['data_ocorrencia'])
                    focos_por_dia = df_total_daily.groupby(df_total_daily['data_ocorrencia_dt'].dt.date).size()
                    if not focos_por_dia.empty:
                        st.line_chart(focos_por_dia)
                        
                        st.markdown("##### Fire Spots per Week (Starts Monday)")
                        focos_por_dia_ts = pd.Series(focos_por_dia.values, index=pd.to_datetime(focos_por_dia.index))
                        focos_por_semana = focos_por_dia_ts.resample('W-MON').sum()
                        if not focos_por_semana.empty:
                            st.bar_chart(focos_por_semana)
                        else:
                            st.info("Not enough data to aggregate by week.")
                    else:
                        st.info("No fire spot data to display daily time series.")
                else:
                    st.warning("Column 'data_ocorrencia' not found for temporal analysis.")

                if 'lat' in df_total_daily.columns and 'lon' in df_total_daily.columns:
                    st.markdown("---")
                    st.markdown("#### 🗺️ Map of Fire Spots (Daily Report)")
                    map_data = df_total_daily[['lat', 'lon']].dropna()
                    if not map_data.empty:
                        MAX_POINTS_ON_MAP = 10000 
                        map_data_display = map_data.sample(min(len(map_data), MAX_POINTS_ON_MAP), random_state=42) if len(map_data) > MAX_POINTS_ON_MAP else map_data
                        if len(map_data) > MAX_POINTS_ON_MAP:
                             st.warning(f"Too many spots ({len(map_data)}) to display. Showing a sample of {MAX_POINTS_ON_MAP}.")
                        st.map(map_data_display)
                    else:
                        st.warning("No valid latitude/longitude data to display on map.")

            elif df_total_daily is not None and df_total_daily.empty:
                st.info(f"No fire spots registered for the period from {start_date_daily.strftime('%d/%m/%Y')} to {end_date_daily.strftime('%d/%m/%Y')}.")
            else: # df_total_daily is None
                st.error("Failed to load daily data.")


with tab2:
    st.header("⏱️ 10-Minute Fire Spot Monitoring")
    st.caption("This panel allows fetching and visualizing fire spot data in 10-minute intervals for recent days.")

    st.sidebar.header("⏱️ 10-Min Monitoring")

    # Helper async function to be called by asyncio.run()
    async def _get_10min_aggregated_data(days_to_fetch_list: list[date]):
        return await load_and_combine_10min_data_for_days(days_to_fetch_list)

    if st.sidebar.button("📡 Load/Refresh 10-Min Data (Last 2 Days + Recent)", key="refresh_10min_data"):
        days_to_fetch = [date.today() - timedelta(days=2), date.today() - timedelta(days=1)]
        if date.today() not in days_to_fetch:
            days_to_fetch.append(date.today())
        
        df_10min_temp = None # Initialize
        with st.spinner("Fetching all 10-minute data... This may take a while."):
            df_10min_temp = asyncio.run(_get_10min_aggregated_data(days_to_fetch))
        
        if df_10min_temp is not None and not df_10min_temp.empty:
            with st.spinner("Assessing risk for 10-minute data..."):
                st.session_state.df_10min_aggregated = aplica_avaliacao_risco_df(df_10min_temp)
        else:
            st.session_state.df_10min_aggregated = df_10min_temp # Store None or empty DF

        st.session_state.last_10min_refresh_time = datetime.now()
        st.rerun()

    if st.session_state.last_10min_refresh_time:
        st.sidebar.caption(f"Last update: {st.session_state.last_10min_refresh_time.strftime('%d/%m/%Y %H:%M:%S')}")

    df_10min_display = st.session_state.get('df_10min_aggregated')

    if df_10min_display is not None and not df_10min_display.empty:
        st.subheader(f"Displaying {len(df_10min_display)} Fire Spots (Last 2 Days + Today's Slots)")
        st.dataframe(df_10min_display.head(20)) # Show the 20 most recent occurrences

        # Summary of risk levels for 10-min data
        if 'criticidade' in df_10min_display.columns:
            st.markdown("##### Risk Level Summary (10-Min Data)")
            risk_counts_10min = df_10min_display['criticidade'].value_counts().reindex(list(RISK_LEVELS.keys()), fill_value=0)
            st.bar_chart(risk_counts_10min)

        st.markdown("---")
        st.markdown("#### 🗺️ Overall Map of 10-Min Fire Spots")
        if 'lat' in df_10min_display.columns and 'lon' in df_10min_display.columns:
            map_data_10min_agg = df_10min_display[['lat', 'lon']].dropna()
            if not map_data_10min_agg.empty:
                st.map(map_data_10min_agg)
            else:
                st.info("No latitude/longitude data for the map.")
        else:
            st.warning("Latitude/Longitude columns ('lat', 'lon') not found in the 10-min data.")


        st.markdown("#### 🔥 PyDeck Map with Risk Coloring (10 min)")
        print(df_10min_display.columns)
        if 'lat' in df_10min_display.columns and 'lon' in df_10min_display.columns and 'criticidade' in df_10min_display.columns:
            pydeck_data = df_10min_display[['lat', 'lon', 'criticidade', 'frp', 'determined_biome_geo']].dropna(subset=['lat', 'lon'])
            print(pydeck_data.head())
            
            if not pydeck_data.empty:
                def get_pydeck_color(criticidade_level):
                    if criticidade_level == "Crítico": return [255, 0, 0, 200]  # Red
                    elif criticidade_level == "Alto": return [255, 165, 0, 180] # Orange
                    elif criticidade_level == "Médio": return [255, 255, 0, 160] # Yellow
                    else: return [0, 255, 0, 100]   # Green (Low)
                
                pydeck_data_colored = pydeck_data.copy()
                pydeck_data_colored['color'] = pydeck_data_colored['criticidade'].apply(get_pydeck_color)

                try:
                    view_state = pdk.ViewState(
                        latitude=pydeck_data_colored['lat'].mean(),
                        longitude=pydeck_data_colored['lon'].mean(),
                        zoom=3, 
                        pitch=50,
                    )
                    
                    scatterplot_layer = pdk.Layer(
                        "ScatterplotLayer",
                        data=pydeck_data_colored,
                        get_position=['lon', 'lat'],
                        get_fill_color="color",
                        get_radius=7000, # Adjust radius as needed (meters)
                        pickable=True,
                        radius_min_pixels=3,
                        radius_max_pixels=30,
                    )

                    st.pydeck_chart(pdk.Deck(
                        layers=[scatterplot_layer], 
                        initial_view_state=view_state, 
                        tooltip={
                            "html": "<b>Lat:</b> {lat}<br/><b>Lon:</b> {lon}<br/>"
                                    "<b>FRP:</b> {frp}<br/><b>Biome:</b> {determined_biome_geo}<br/>"
                                    "<b>Criticidade:</b> {criticidade}",
                            "style": {"color": "white"}
                        }
                    ))
                except Exception as e:
                    st.error(f"Error generating PyDeck map: {e}")
                    st.write("Ensure 'lat', 'lon', and 'criticidade' columns exist and are valid.")
            else:
                st.info("No data for PyDeck map after dropping NaNs from lat/lon.")
        else:
            st.warning("Required columns ('lat', 'lon', 'criticidade') not found for PyDeck map.")
        
        st.markdown("---")
        st.markdown("#### 🌍 Geographic Analysis (10 min)")
        if 'lat' in df_10min_display.columns and 'lon' in df_10min_display.columns:
            st.write(f"**Geographic Extents of Fire Spots:**")
            st.write(f"  Min Latitude: {df_10min_display['lat'].min():.4f}, Max Latitude: {df_10min_display['lat'].max():.4f}")
            st.write(f"  Min Longitude: {df_10min_display['lon'].min():.4f}, Max Longitude: {df_10min_display['lon'].max():.4f}")

            equator_approx = -10 
            df_10min_display['simple_region'] = df_10min_display['lat'].apply(
                lambda x: 'North/Midwest (approx.)' if x > equator_approx else 'South/Southeast/Northeast (approx.)'
            )
            spots_by_simple_region = df_10min_display['simple_region'].value_counts()
            st.markdown("##### Fire Spots by Approximate Region")
            st.bar_chart(spots_by_simple_region)
            st.caption(f"Division based on latitude > {equator_approx}° for 'North/Midwest (approx.)'. This is a very rough estimation.")
        else:
            st.warning("Latitude/Longitude columns ('lat', 'lon') not found for geographic analysis.")


    elif st.session_state.last_10min_refresh_time:
        st.info("No 10-minute data found for the requested period after update.")
    else:
        st.info("Click the 'Load/Refresh 10-Min Data' button in the sidebar to fetch data.")

with tab3:
    st.header("🚨 Alertas e Focos de Risco Elevado")
    st.caption("Esta seção destaca os focos de queimada com base nos níveis de risco selecionados.")

    # Risk level selection
    available_risk_levels = list(RISK_LEVELS.keys())
    selected_risk_levels = st.multiselect(
        "Selecione os níveis de risco para exibir:",
        options=available_risk_levels,
        default=["Crítico", "Alto"] # Default to showing Critical and High risks
    )

    if not selected_risk_levels:
        st.warning("Por favor, selecione pelo menos um nível de risco para exibir os alertas.")
        st.stop()

    # --- Daily Report Alerts Section ---
    st.markdown("---")
    st.subheader("Alertas do Relatório Diário")
    df_daily_assessed = st.session_state.get('df_total_daily_assessed')
    if df_daily_assessed is not None and not df_daily_assessed.empty:
        if 'criticidade' in df_daily_assessed.columns:
            alerts_daily_df = df_daily_assessed[df_daily_assessed['criticidade'].isin(selected_risk_levels)].copy()
            if not alerts_daily_df.empty:
                st.metric(label="Focos de Risco (Diário)", value=len(alerts_daily_df))
                st.markdown("##### Detalhes dos Focos de Risco (Relatório Diário):")
                cols_to_show_daily = ['event_datetime', 'lat', 'lon', 'municipio', 'estado', 'bioma', 'frp', 'criticidade', 'razoes_criticidade']
                cols_present_daily = [col for col in cols_to_show_daily if col in alerts_daily_df.columns]
                st.dataframe(alerts_daily_df[cols_present_daily])
            else:
                st.info(f"Nenhum foco com os níveis de risco selecionados ({', '.join(selected_risk_levels)}) encontrado nos dados do Relatório Diário.")
        else:
            st.warning("Coluna 'criticidade' não encontrada nos dados do Relatório Diário. Não é possível filtrar alertas.")
    else:
        st.info("Nenhum dado do Relatório Diário carregado ou os dados estão vazios. Gere um relatório na aba 'Periodic Report (Daily)'.")

    # --- 10-Min Monitoring Alerts Section ---
    st.markdown("---")
    st.subheader("Alertas do Monitoramento de 10 Minutos")
    df_10min_assessed = st.session_state.get('df_10min_aggregated')
    if df_10min_assessed is not None and not df_10min_assessed.empty:
        if 'criticidade' in df_10min_assessed.columns:
            alerts_10min_df = df_10min_assessed[df_10min_assessed['criticidade'].isin(selected_risk_levels)].copy()
            if not alerts_10min_df.empty:
                st.metric(label="Focos de Risco (10 Min)", value=len(alerts_10min_df))
                st.markdown("##### Detalhes dos Focos de Risco (Monitoramento 10 Min):")
                cols_to_show_10min = ['event_datetime', 'lat', 'lon', 'municipio', 'estado', 'bioma', 'frp', 'criticidade', 'razoes_criticidade']
                cols_present_10min = [col for col in cols_to_show_10min if col in alerts_10min_df.columns]
                st.dataframe(alerts_10min_df[cols_present_10min])
            else:
                st.info(f"Nenhum foco com os níveis de risco selecionados ({', '.join(selected_risk_levels)}) encontrado nos dados de Monitoramento de 10 Minutos.")
        else:
            st.warning("Coluna 'criticidade' não encontrada nos dados de Monitoramento de 10 Minutos. Não é possível filtrar alertas.")
    else:
        st.info("Nenhum dado de Monitoramento de 10 Minutos carregado ou os dados estão vazios. Carregue/Atualize os dados na aba '10-Minute Monitoring'.")


st.sidebar.markdown("---")
