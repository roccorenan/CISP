import os
import json
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

print("Testando conexao com API CISP...\n")

# Configuracoes da API
url = "https://servicos.cisp.com.br/v1/avaliacao-analitica/raiz/45543915"
username = os.getenv("CISP_USERNAME")
password = os.getenv("CISP_PASSWORD")

if not username or not password:
    print("Erro: Credenciais nao encontradas no arquivo .env")
    exit(1)

try:
    print("Fazendo requisicao para API...")
    response = requests.get(
        url,
        auth=HTTPBasicAuth(username, password),
        timeout=30,
    )

    print(f"Status Code: {response.status_code}\n")

    if response.status_code == 200:
        dados = response.json()
        print("Dados recebidos:")
        print(json.dumps(dados, indent=2, ensure_ascii=False))
        print("\nConexao com API funcionando!")
    else:
        print(f"Erro: Status {response.status_code}")
        print(response.text)

except requests.exceptions.Timeout:
    print("Erro: Timeout ao conectar com a API.")
except requests.exceptions.ConnectionError:
    print("Erro: Nao foi possivel conectar com a API.")
except Exception as e:
    print(f"Erro ao conectar: {e}")
