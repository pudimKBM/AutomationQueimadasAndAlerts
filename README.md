# 🔥 Monitor de Focos de Queimada do INPE

## 📖 Descrição

Este projeto consiste em uma aplicação web para coletar, processar, analisar e visualizar dados de focos de ueimadas no Brasil, fornecidos pelo Instituto Nacional de Pesquisas Espaciais (INPE). A aplicação oferece tanto elatórios diários consolidados quanto um monitoramento quase em tempo real com atualizações a cada 10 minutos. nclui um sistema de avaliação de risco para os focos de queimada, auxiliando na identificação de áreas críticas.

## 🎯 Objetivo

O principal objetivo deste projeto é fornecer uma ferramenta para:
*   Monitorar e analisar a ocorrência de queimadas em território brasileiro.
*   Realizar uma avaliação de risco dos focos de queimada detectados, com base em critérios como Potência adiativa do Fogo (FRP) e sensibilidade do bioma.
*   Apresentar os dados e alertas de forma interativa e visual, facilitando a tomada de decisão e a resposta a ventos críticos.
*   Oferecer uma interface amigável para explorar padrões e tendências de queimadas.

## ✨ Funcionalidades

*   **Coleta de Dados Automatizada**:
    *   Download assíncrono de arquivos CSV diários de focos de queimada do INPE.
    *   Download assíncrono de arquivos CSV de focos de queimada a cada 10 minutos do INPE.
*   **Processamento de Dados**:
    *   Carregamento e combinação de dados de múltiplos arquivos CSV.
    *   Padronização de colunas de data/hora e coordenadas geográficas.
    *   Tratamento de diferentes codificações de arquivos CSV.
*   **Avaliação de Risco**:
    *   Classificação dos focos de queimada em níveis de risco: Baixo, Médio, Alto e Crítico.
    *   Utilização de critérios como FRP (Fire Radiative Power) e a sensibilidade do bioma atingido.
    *   Geolocalização de focos para determinar o bioma, caso essa informação não esteja presente nos dados riginais.
*   **Aplicação Web Interativa (Streamlit)**:
    *   **Painel de Relatório Periódico (Diário)**:
        *   Seleção de intervalo de datas para agregação de dados diários.
        *   Visualização de dados combinados, resumos de níveis de risco.
        *   Análises por estado, bioma, hora do dia, distribuição de FRP e tendências temporais.
        *   Mapa de focos de queimada.
    *   **Painel de Monitoramento (10 Minutos)**:
        *   Carregamento e atualização de dados dos últimos 2 dias e slots recentes.
        *   Exibição dos focos de queimada mais recentes e resumos de risco.
        *   Mapa interativo (PyDeck) com coloração baseada no risco e tooltips informativos (FRP, bioma, riticidade).
        *   Análise geográfica básica (extensões, regiões aproximadas).
    *   **Painel de Alertas de Risco**:
        *   Filtragem e exibição de focos de queimada de alto risco, com níveis de risco selecionáveis.
        *   Seções separadas para alertas de relatórios diários e de monitoramento de 10 minutos.
*   **Configuração Centralizada**:
    *   Arquivo `config.py` para gerenciar URLs de dados, caminhos de diretórios e critérios de avaliação de risco.
*   **Análise Geoespacial**:
    *   Utilização de dados GeoJSON de biomas para avaliação de risco e contextualização nas visualizações.

## 🛠️ Tecnologias Utilizadas

*   **Linguagem Principal**: Python 3.x
*   **Análise e Manipulação de Dados**: Pandas, GeoPandas
*   **Interface Web**: Streamlit
*   **Coleta de Dados Assíncrona**: Aiohttp, Asyncio, Aiofiles
*   **Visualização de Mapas**: PyDeck (para mapas 3D interativos), Streamlit (mapas básicos)
*   **Geração de Gráficos**: Matplotlib
*   **Logging**: Módulo `logging` do Python
*   **Formatos de Dados**: CSV (dados do INPE), GeoJSON (dados de biomas)

## 📂 Estrutura do Projeto

```
queimadas_monitor/
├── app.py                    # Arquivo principal da aplicação Streamlit
├── config.py                 # Configurações do projeto
├── data_collection/
│   └── collector.py          # Módulo para coleta de dados do INPE
├── risk_assessment/
│   └── assessor.py           # Módulo para lógica de avaliação de risco
├── geodata/
│   └── biomas_5000.json      # Arquivo GeoJSON com dados dos biomas brasileiros
├── output_data/
│   └── raw/                  # Diretório para CSVs brutos baixados
├── requirements.txt          # Dependências do projeto
└── README.md                 # Documentação do projeto (este arquivo)
```

## ⚙️ Configuração e Instalação

1.  **Clone o Repositório**:
    ```bash
    git clone https://github.com/seu-usuario/AutomationQueimadasAndAlerts.git
    cd AutomationQueimadasAndAlerts/queimadas_monitor
    ```

2.  **Crie um Ambiente Virtual** (recomendado):
    ```bash
    python -m venv venv
    # No Windows
    venv\Scripts\activate
    # No macOS/Linux
    source venv/bin/activate
    ```

3.  **Instale as Dependências**:
    Certifique-se de ter um arquivo `requirements.txt` com as seguintes bibliotecas (ou instale-as manualmente):
    ```
    streamlit
    pandas
    geopandas
    pydeck
    matplotlib
    aiohttp
    aiofiles
    ```
    Execute:
    ```bash
    pip install -r requirements.txt
    ```
    *Nota: A instalação do GeoPandas pode ter dependências de sistema como GDAL. Consulte a documentação do eoPandas para instruções detalhadas de instalação.*

4.  **Estrutura de Diretórios**:
    *   Certifique-se de que o arquivo `geodata/biomas_5000.json` está presente no local correto.
    *   Crie o diretório `output_data/raw/` se ele não existir:
        ```bash
        mkdir -p output_data/raw
        # No Windows (PowerShell): mkdir -Force output_data\raw
        ```

## 🚀 Uso

1.  **Execute a Aplicação Streamlit**:
    A partir do diretório raiz do projeto (`queimadas_monitor/`), execute:
    ```bash
    streamlit run app.py
    ```

2.  **Interaja com a Aplicação**:
    *   Abra o navegador no endereço fornecido (geralmente `http://localhost:8501`).
    *   Navegue pelas abas: "Relatório Periódico (Diário)", "Monitoramento (10 Minutos)" e "Alertas de Risco".
    *   Utilize os controles na barra lateral para:
        *   Selecionar intervalos de datas para os relatórios diários.
        *   Gerar/atualizar os dados de monitoramento de 10 minutos.
        *   Filtrar os alertas por nível de criticidade.

## 🔧 Configuração Adicional

As principais configurações do projeto podem ser ajustadas no arquivo `config.py`:
*   `CSV_BASE_URL`, `CSV_10MIN_BASE_URL`: URLs base para os dados do INPE. Modifique se as fontes de dados mudarem.
*   `RAW_DATA_DIR`, `REPORTS_DIR`, `CHARTS_DIR`: Caminhos para armazenamento de dados.
*   `RISK_FRP_THRESHOLD`, `SENSITIVE_BIOMES`: Critérios para a avaliação de risco dos focos de queimada.
*   `BIOMES_FILE_PATH`: Caminho para o arquivo GeoJSON dos biomas.

## 📊 Fontes de Dados

*   **INPE - Instituto Nacional de Pesquisas Espaciais (Brasil)**:
    *   Dados diários de focos de queimada.
    *   Dados de focos de queimada em intervalos de 10 minutos.

## 🔮 Melhorias Futuras (Sugestões)

*   Geração automatizada de relatórios (ex: resumos diários em PDF).
*   Sistema de notificação por e-mail/SMS para alertas críticos.
*   Análises estatísticas mais avançadas e modelagem preditiva.
*   Autenticação de usuários e dashboards personalizados.
*   Integração com outros conjuntos de dados relevantes (ex: dados meteorológicos, uso do solo).
*   Deployment da aplicação em uma plataforma de nuvem (ex: Streamlit Sharing, Heroku, AWS).


## 👤 Contato

* Antônio Libarato RM558014
* Renan de França Gonçalves RM558413
* Thiago Almança RM558108




