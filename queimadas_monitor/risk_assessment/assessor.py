# risk_assessment/assessor.py
# Módulo para avaliação de risco de focos de queimadas

import pandas as pd
import geopandas
from shapely.geometry import Point
import os # Added for path joining

# Tentativa de importar configurações.
try:
    from config import RISK_FRP_THRESHOLD, SENSITIVE_BIOMES, BIOMES_FILE_PATH
except ModuleNotFoundError:
    import sys
    # Adiciona o diretório pai ao sys.path para encontrar o módulo config
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_dir = os.path.dirname(current_file_dir)
    if project_root_dir not in sys.path:
        sys.path.append(project_root_dir)
    from config import RISK_FRP_THRESHOLD, SENSITIVE_BIOMES, BIOMES_FILE_PATH

# --- Global variable to hold loaded biomes data ---
# This will be loaded once when the module is first imported.
BIOMES_GDF = None
BIOME_NAME_COLUMN = 'nom_bioma' # IMPORTANT: Adjust this to the actual column name in your GeoJSON that contains the biome name

def load_biomes_data():
    """Loads the biomes GeoJSON into a GeoDataFrame."""
    global BIOMES_GDF
    if BIOMES_GDF is None:
        try:
            # Construct the full path relative to the project root or use an absolute path
            # Assuming BIOMES_FILE_PATH is relative to the project root
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            full_GeoJSON_path = os.path.join(project_root, BIOMES_FILE_PATH)
            
            if not os.path.exists(full_GeoJSON_path):
                print(f"ERROR: Biomes GeoJSON not found at {full_GeoJSON_path}")
                # In a Streamlit app, you might use st.error or logging
                # For now, we'll let it raise an error if critical, or handle gracefully
                BIOMES_GDF = geopandas.GeoDataFrame() # Empty GeoDataFrame
                return

            print(f"Loading biomes data from: {full_GeoJSON_path}")
            BIOMES_GDF = geopandas.read_file(full_GeoJSON_path)
            # Ensure the GeoDataFrame is using WGS84 (lat/lon) if your points are
            if BIOMES_GDF.crs is None:
                print("Warning: Biomes GeoDataFrame has no CRS defined. Assuming WGS84 (EPSG:4326).")
                BIOMES_GDF.set_crs("EPSG:4326", inplace=True)
            elif BIOMES_GDF.crs.to_epsg() != 4326:
                print(f"Converting biomes CRS from {BIOMES_GDF.crs} to WGS84 (EPSG:4326).")
                BIOMES_GDF = BIOMES_GDF.to_crs("EPSG:4326")
            
            # Validate that the BIOME_NAME_COLUMN exists
            if BIOME_NAME_COLUMN not in BIOMES_GDF.columns:
                print(f"ERROR: Column '{BIOME_NAME_COLUMN}' not found in biomes GeoJSON. Available columns: {BIOMES_GDF.columns.tolist()}")
                BIOMES_GDF = geopandas.GeoDataFrame() # Make it empty to prevent further errors
                return

            print("Biomes data loaded successfully.")
        except Exception as e:
            print(f"Error loading biomes GeoJSON: {e}")
            BIOMES_GDF = geopandas.GeoDataFrame() # Empty GeoDataFrame on error
# Load biomes data when the module is imported
load_biomes_data()


def get_biome_from_lat_lon(lat: float, lon: float) -> str | None:
    """
    Determines the biome for a given latitude and longitude.
    Returns the biome name or None if not found or an error occurs.
    """
    if BIOMES_GDF is None or BIOMES_GDF.empty:
        # print("Warning: Biomes data not loaded or empty. Cannot determine biome from lat/lon.")
        return None
    if pd.isna(lat) or pd.isna(lon):
        return None
        
    try:
        point = Point(lon, lat) # Shapely Point: (longitude, latitude)
        # Iterate through biomes and check if the point is within any
        for index, row in BIOMES_GDF.iterrows():
            if point.within(row['geometry']):
                return row[BIOME_NAME_COLUMN] # Use the configured biome name column
    except Exception as e:
        print(f"Error in get_biome_from_lat_lon for point ({lon}, {lat}): {e}")
    return None


def assess_foco_criticidade(foco: pd.Series) -> tuple[str, list[str]]:
    """
    Avalia a criticidade de um único foco de queimada.
    Agora utiliza lat/lon para determinar o bioma se a coluna 'bioma' não estiver presente ou for NaN.

    Args:
        foco (pd.Series): Uma linha do DataFrame representando um foco de queimada.
                          Espera-se que contenha colunas como 'frp', 'lat', 'lon'.
                          A coluna 'bioma' é opcional.

    Returns:
        tuple[str, list[str]]: Nível de criticidade (ex: "Crítico", "Alto", "Médio", "Baixo")
                               e uma lista de razões para essa criticidade.
    """
    razoes = []
    nivel_criticidade_num = 0 # Começa com Baixo
    # Determinar o bioma
    determined_biome = None
    if 'bioma' in foco and pd.notna(foco['bioma']):
        determined_biome = foco['bioma']
    elif 'lat' in foco and 'lon' in foco and pd.notna(foco['lat']) and pd.notna(foco['lon']):
        determined_biome = get_biome_from_lat_lon(foco['lat'], foco['lon'])
        if determined_biome:
            razoes.append(f"Bioma determinado por geolocalização: {determined_biome}")
    
    # Critério 1: FRP
    if 'frp' in foco and pd.notna(foco['frp']):
        try:
            frp_valor = float(foco['frp'])
            if frp_valor >= RISK_FRP_THRESHOLD:
                razoes.append(f"FRP elevado ({frp_valor:.2f} MW >= {RISK_FRP_THRESHOLD} MW)")
                nivel_criticidade_num = max(nivel_criticidade_num, 2) # Define como Alto
            elif frp_valor >= RISK_FRP_THRESHOLD / 2: 
                nivel_criticidade_num = max(nivel_criticidade_num, 1) 
        except ValueError:
            pass 

    # Critério 2: Bioma Sensível (usando determined_biome)
    if determined_biome: # Check if a biome was determined
        if determined_biome in SENSITIVE_BIOMES:
            # Add reason only if not already added by geolocalization message
            if not any(f"Bioma determinado por geolocalização: {determined_biome}" in r for r in razoes):
                 razoes.append(f"Bioma sensível ({determined_biome})")

            if nivel_criticidade_num >= 2 and determined_biome in ["Amazônia", "Pantanal"]:
                 nivel_criticidade_num = max(nivel_criticidade_num, 3) 
            else:
                nivel_criticidade_num = max(nivel_criticidade_num, 1) 
    
    # Mapear número para rótulo de criticidade
    if nivel_criticidade_num == 3 :
        criticidade_label = "Crítico"
    elif nivel_criticidade_num == 2:
        criticidade_label = "Alto"
    elif nivel_criticidade_num == 1:
        criticidade_label = "Médio"
    else:
        criticidade_label = "Baixo"
    
    if not razoes and nivel_criticidade_num > 0 : 
        razoes.append("Critério de risco atingido (detalhe não especificado)")
    elif not razoes and nivel_criticidade_num == 0:
        razoes.append("Nenhum critério de risco específico atingido")

    return criticidade_label, razoes

def aplica_avaliacao_risco_df(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica a avaliação de risco a cada foco no DataFrame."""
    if BIOMES_GDF is None or BIOMES_GDF.empty:
        print("AVISO: GeoDataFrame de Biomas não carregado ou vazio. A avaliação de risco baseada em bioma por geolocalização será limitada.")
        # Proceed without biome determination from lat/lon if GDF is not available
        # but still try to use 'bioma' column if it exists.

    if df.empty:
        df_com_risco = df.copy()
        df_com_risco['criticidade'] = pd.Series(dtype='object')
        df_com_risco['razoes_criticidade'] = pd.Series(dtype='object')
        # Add determined_biome column if biomes data is available, even for empty df
        if BIOMES_GDF is not None and not BIOMES_GDF.empty:
            df_com_risco['determined_biome_geo'] = pd.Series(dtype='object')
            
        return df_com_risco

    # Ensure necessary columns exist for assessment
    if 'frp' not in df.columns: df['frp'] = pd.NA
    if 'lat' not in df.columns: df['lat'] = pd.NA
    if 'lon' not in df.columns: df['lon'] = pd.NA
    # 'bioma' column is optional, will be handled by assess_foco_criticidade

    # Apply assessment
    avaliacoes = df.apply(assess_foco_criticidade, axis=1, result_type='expand')
    df_com_risco = df.copy() 
    df_com_risco[['criticidade', 'razoes_criticidade']] = avaliacoes

    # Optionally, add a column with the biome determined by geolocation if it's different or new
    # This is more for debugging or explicit display if needed
    if BIOMES_GDF is not None and not BIOMES_GDF.empty:
        if 'lat' in df_com_risco.columns and 'lon' in df_com_risco.columns:
            df_com_risco['determined_biome_geo'] = df_com_risco.apply(
                lambda row: get_biome_from_lat_lon(row['lat'], row['lon']) 
                if pd.notna(row['lat']) and pd.notna(row['lon']) else None, 
                axis=1
            )
    return df_com_risco
