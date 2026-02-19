# Portal Web (UI) - Consulta CISP (Raiz CNPJ)

## Rodar
1) Configure variáveis de ambiente:
- CISP_USERNAME
- CISP_PASSWORD
- POSTGRES

2) Instale dependências:
pip install flask flask-cors requests psycopg2-binary

3) Execute:
python app.py

Acesse:
http://localhost:5000

## Observação importante (Bootstrap)
O layout usa Bootstrap via CDN:
https://cdn.jsdelivr.net

Se seu ambiente for offline/bloqueado, baixe os arquivos do Bootstrap e sirva local em /static,
e troque os links no templates/base.html.


## Dica (.env)
Se você usa um arquivo `.env`, instale:
`pip install python-dotenv`

O `app.py` já tenta carregar automaticamente.
