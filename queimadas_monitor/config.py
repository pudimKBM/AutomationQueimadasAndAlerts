# config.py
# Arquivo de configurações do projeto

# URL base para os arquivos CSV diários de focos de queimadas do INPE para o Brasil
CSV_BASE_URL = "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/diario/Brasil/"

# URL base para os arquivos CSV de 10 minutos de focos de queimadas do INPE
CSV_10MIN_BASE_URL = "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/10min/"

# Diretório para salvar os dados brutos (CSVs baixados)
RAW_DATA_DIR = "output_data/raw/"


# --- Critérios de Risco para Queimadas ---
RISK_FRP_THRESHOLD = 75.0  # Exemplo: FRP em MW acima do qual o foco é considerado de alto risco inicial
SENSITIVE_BIOMES = ["Amazônia", "Mata Atlântica", "Cerrado", "Pantanal"] # Biomas sensíveis

# Níveis de Risco (para referência, a lógica principal está no assessor.py)
RISK_LEVELS = {
    "Baixo": 0,
    "Médio": 1,
    "Alto": 2,
    "Crítico": 3
}


# --- Geospatial Data ---
BIOMES_FILE_PATH = "geodata/biomas_5000.json" # Path to your biomes GeoJSON file
# Ensure this shapefile has a column identifying the biome name, e.g., 'Bioma' or 'nome'
