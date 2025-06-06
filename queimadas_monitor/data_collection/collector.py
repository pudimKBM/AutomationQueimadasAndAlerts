# Módulo para coleta de dados de focos de queimadas (arquivos CSV diários) do INPE

from datetime import date, timedelta, datetime
import os
import logging
import asyncio
import aiohttp # Para requisições HTTP assíncronas
import aiofiles # Para operações de arquivo assíncronas
import pandas as pd

# Configuração básica do logging.
# Idealmente, a configuração do logging seria mais centralizada para um projeto maior.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

# Tentativa de importar configurações.
try:
    from config import CSV_BASE_URL, RAW_DATA_DIR, CSV_10MIN_BASE_URL
except ModuleNotFoundError:
    # Adiciona o diretório pai ao sys.path para encontrar o módulo config
    # Isso é útil se o script for executado diretamente de dentro de data_collection/
    # ou se o PYTHONPATH não estiver configurado para incluir a raiz do projeto.
    import sys
    # Obtém o caminho absoluto do diretório do arquivo atual (collector.py)
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    # Obtém o caminho absoluto do diretório pai (queimadas_monitor)
    project_root_dir = os.path.dirname(current_file_dir)
    if project_root_dir not in sys.path:
        sys.path.append(project_root_dir)
    from config import CSV_BASE_URL, RAW_DATA_DIR, CSV_10MIN_BASE_URL

def ensure_dir(directory_path: str):
    """Garante que um diretório exista; se não, cria-o."""
    os.makedirs(directory_path, exist_ok=True)
    logging.debug(f"Diretório garantido: {directory_path}")

async def fetch_daily_fire_csv(target_date: date, session: aiohttp.ClientSession) -> str | None:
    """
    Baixa o arquivo CSV de focos de queimada para uma data específica do INPE.

    Args:
        target_date (date): A data para a qual o arquivo CSV será baixado.
        session (aiohttp.ClientSession): The aiohttp session to use for requests.

    Returns:
        str | None: O caminho para o arquivo CSV baixado, ou None em caso de erro.
    """
    date_str_url = target_date.strftime("%Y%m%d")
    file_name = f"focos_diario_br_{date_str_url}.csv"
    file_url = f"{CSV_BASE_URL}{file_name}"

    ensure_dir(RAW_DATA_DIR)
    local_file_path = os.path.join(RAW_DATA_DIR, file_name)

    logging.info(f"Tentando baixar dados de {target_date.strftime('%d/%m/%Y')} de: {file_url}")

    try:
        async with session.get(file_url, timeout=60) as response:
            response.raise_for_status()
            async with aiofiles.open(local_file_path, 'wb') as f:
                while True:
                    chunk = await response.content.read(8192) # 8KB chunks
                    if not chunk:
                        break
                    await f.write(chunk)

        logging.info(f"Arquivo baixado com sucesso e salvo em: {local_file_path}")
        return local_file_path

    except aiohttp.ClientResponseError as http_err:
        if http_err.status == 404:
            logging.warning(f"Arquivo não encontrado (404) para a data {target_date.strftime('%d/%m/%Y')}. URL: {file_url}")
        else:
            logging.error(f"Erro HTTP ao baixar o arquivo: {http_err} - URL: {file_url}")
        return None
    except aiohttp.ClientConnectionError as conn_err:
        logging.error(f"Erro de conexão ao tentar baixar o arquivo: {conn_err} - URL: {file_url}")
        return None
    except asyncio.TimeoutError as timeout_err: # Specific for asyncio timeouts
        logging.error(f"Timeout na requisição ao baixar o arquivo: {timeout_err} - URL: {file_url}")
        return None
    except aiohttp.ClientError as req_err: # General aiohttp client error
        logging.error(f"Erro geral na requisição ao baixar o arquivo: {req_err} - URL: {file_url}")
        return None
    except IOError as io_err:
        logging.error(f"Erro de I/O ao salvar o arquivo {local_file_path}: {io_err}")
        return None

async def fetch_10min_fire_csv(target_datetime: datetime, session: aiohttp.ClientSession) -> str | None:
    """
    Baixa o arquivo CSV de focos de queimada para uma data e hora (intervalo de 10 min) específica do INPE.

    Args:
        target_datetime (datetime): A data e hora para a qual o arquivo CSV será baixado (minuto múltiplo de 10).
        session (aiohttp.ClientSession): The aiohttp session to use for requests.

    Returns:
        str | None: O caminho para o arquivo CSV baixado, ou None em caso de erro.
    """
    if target_datetime.minute % 10 != 0:
        logging.error(f"Minuto inválido para busca de 10min: {target_datetime.minute}. Deve ser múltiplo de 10.")
        return None

    date_str_url = target_datetime.strftime("%Y%m%d")
    time_str_url = target_datetime.strftime("%H%M")
    
    file_name = f"focos_10min_{date_str_url}_{time_str_url}.csv"
    file_url = f"{CSV_10MIN_BASE_URL}{file_name}"

    ensure_dir(RAW_DATA_DIR) 
    local_file_path = os.path.join(RAW_DATA_DIR, file_name)

    logging.info(f"Tentando baixar dados de 10min de {target_datetime.strftime('%d/%m/%Y %H:%M')} de: {file_url}")

    try:
        async with session.get(file_url, timeout=60) as response:
            response.raise_for_status()
            async with aiofiles.open(local_file_path, 'wb') as f:
                while True:
                    chunk = await response.content.read(8192)
                    if not chunk:
                        break
                    await f.write(chunk)

        logging.info(f"Arquivo de 10min baixado com sucesso e salvo em: {local_file_path}")
        return local_file_path

    except aiohttp.ClientResponseError as http_err:
        if http_err.status == 404:
            logging.warning(f"Arquivo de 10min não encontrado (404) para {target_datetime.strftime('%d/%m/%Y %H:%M')}. URL: {file_url}")
        else:
            logging.error(f"Erro HTTP ao baixar o arquivo de 10min: {http_err} - URL: {file_url}")
        return None
    except aiohttp.ClientConnectionError as conn_err:
        logging.error(f"Erro de conexão ao tentar baixar o arquivo de 10min: {conn_err} - URL: {file_url}")
        return None
    except asyncio.TimeoutError as timeout_err:
        logging.error(f"Timeout na requisição ao baixar o arquivo de 10min: {timeout_err} - URL: {file_url}")
        return None
    except aiohttp.ClientError as req_err:
        logging.error(f"Erro geral na requisição ao baixar o arquivo de 10min: {req_err} - URL: {file_url}")
        return None
    except IOError as io_err:
        logging.error(f"Erro de I/O ao salvar o arquivo de 10min {local_file_path}: {io_err}")
        return None

async def fetch_all_10min_slots_for_day(target_date: date, session: aiohttp.ClientSession) -> list[str]:
    """
    Tenta baixar todos os 144 arquivos CSV de 10 minutos para um dia específico de forma assíncrona.
    Retorna uma lista de caminhos para os arquivos baixados com sucesso que contêm dados.
    """
    tasks = []
    logging.info(f"Iniciando download assíncrono de todos os slots de 10min para {target_date.strftime('%Y-%m-%d')}")
    for hour in range(24):
        for minute in range(0, 60, 10):
            current_dt = datetime(target_date.year, target_date.month, target_date.day, hour, minute)
            tasks.append(fetch_10min_fire_csv(current_dt, session))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    downloaded_files_with_data = []
    for result in results:
        if isinstance(result, str) and os.path.exists(result): # Check if it's a valid path string
            try:
                # Asynchronously check file size
                # Use synchronous os.stat in a thread to avoid blocking
                file_stat = await asyncio.to_thread(os.stat, result)
                if file_stat.st_size > 0: # Basic check for non-empty file
                    # For checking content, pandas is sync. We can run it in a thread
                    # or read a small chunk async. For simplicity, keeping pandas sync here.
                    # This is a small, quick operation.
                    # Using asyncio.to_thread to run synchronous pandas code in a separate thread
                    df_temp = await asyncio.to_thread(pd.read_csv, result, nrows=1)
                    if not df_temp.empty:
                        downloaded_files_with_data.append(result)
                    else:
                        logging.info(f"Arquivo {result} parece vazio (sem dados após cabeçalho), ignorando.")
                else:
                    logging.info(f"Arquivo {result} está vazio (0 bytes), ignorando.")
            except Exception as e:
                logging.error(f"Erro ao verificar o arquivo {result}: {e}")
        elif isinstance(result, Exception):
            logging.error(f"Erro durante o download de um slot de 10min: {result}")
            # Depending on the exception, you might want to handle it differently or re-raise
        # else:
            # logging.debug(f"Slot não resultou em arquivo válido ou foi None: {result}")


    logging.info(f"Concluído download para {target_date.strftime('%Y-%m-%d')}. {len(downloaded_files_with_data)} arquivos com dados baixados.")
    return downloaded_files_with_data

async def main_test_runner(): # Wrapper async function for test execution
    """Runs test functions for the collector module."""
    logging.info("Executando o coletor de dados CSV como script principal (para teste).")

    async with aiohttp.ClientSession() as session:
        # Test fetch_daily_fire_csv
        target_report_date = date.today() - timedelta(days=1)
        logging.info(f"Tentando buscar dados para o relatório referente a: {target_report_date.strftime('%d/%m/%Y')}")
        downloaded_csv_path = await fetch_daily_fire_csv(target_report_date, session)
        if downloaded_csv_path:
            logging.info(f"Caminho do arquivo CSV diário baixado: {downloaded_csv_path}")
            try:
                # Use synchronous os.stat in a thread
                stat_info = await asyncio.to_thread(os.stat, downloaded_csv_path)
                logging.info(f"Tamanho do arquivo: {stat_info.st_size / 1024:.2f} KB")
            except Exception as e:
                logging.error(f"Não foi possível obter o tamanho do arquivo {downloaded_csv_path}: {e}")

        else:
            logging.warning("Falha ao baixar o arquivo CSV diário.")

        # Test fetch_10min_fire_csv
        logging.info("\nTestando fetch_10min_fire_csv individual:")
        # Use uma data/hora que você espera que tenha dados, ou uma recente para teste.
        # Ex: duas horas atrás, no minuto 00, 10, 20, 30, 40, ou 50.
        test_datetime_10min = (datetime.now() - timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
        downloaded_10min_path = await fetch_10min_fire_csv(test_datetime_10min, session)
        if downloaded_10min_path:
            logging.info(f"Caminho do arquivo de 10min baixado: {downloaded_10min_path}")
        else:
            logging.warning(f"Falha ao baixar arquivo de 10min para {test_datetime_10min.strftime('%d/%m/%Y %H:%M')}.")

        # Test fetch_all_10min_slots_for_day
        logging.info("\nTestando fetch_all_10min_slots_for_day:")
        # Fetch for a date that is likely to have data, e.g., 2 days ago
        target_date_for_10min_slots = date.today() - timedelta(days=2)
        downloaded_slot_files = await fetch_all_10min_slots_for_day(target_date_for_10min_slots, session)
        logging.info(f"Total de {len(downloaded_slot_files)} arquivos de slots de 10min baixados com dados para {target_date_for_10min_slots}.")
        # for f_path in downloaded_slot_files:
        #     logging.debug(f" - {f_path}")

if __name__ == "__main__":
    # Para executar o script de teste:
    # python -m data_collection.collector (se estiver na raiz do projeto)
    # ou python collector.py (se estiver dentro da pasta data_collection)
    # asyncio.run(main_test_runner())
    pass
