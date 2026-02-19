"""
API FLASK PARA POWER BI
Porta: 5000

O Power BI chama essa API, ela busca na API CISP e insere no PostgreSQL
"""

import os
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, jsonify, Response
from flask_cors import CORS
from datetime import datetime
from requests.auth import HTTPBasicAuth

app = Flask(__name__)
CORS(app)

# Configurações
API_BASE_URL = "https://servicos.cisp.com.br/v1/avaliacao-analitica/raiz"
API_USERNAME = os.environ.get('CISP_USERNAME')
API_PASSWORD = os.environ.get('CISP_PASSWORD')

DB_CONFIG = {
    'host': '127.0.0.1',
    'port': '5432',
    'database': 'dbDataLakePrd',
    'user': 'postgres',
    'password': os.environ.get('POSTGRES'),
    'options': '-c search_path=scsilverlayer'
}

def conectar_db():
    return psycopg2.connect(**DB_CONFIG)

def converter_data(data_str):
    if not data_str:
        return None
    try:
        return datetime.strptime(data_str, '%Y-%m-%d').date()
    except:
        return None

_cols_cache = {}

def obter_colunas(cursor, tabela):
    if tabela in _cols_cache:
        return _cols_cache[tabela]
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = (SELECT current_schema())
          AND table_name = %s
    """, (tabela,))
    cols = {r[0] for r in cursor.fetchall()}
    _cols_cache[tabela] = cols
    return cols

def tabela_tem_coluna(cursor, tabela, coluna):
    return coluna in obter_colunas(cursor, tabela)

def inserir_generico(cursor, tabela, dados, pk_cols=None):
    cols_disp = obter_colunas(cursor, tabela)
    cols = [c for c in dados.keys() if c in cols_disp]
    if not cols:
        return
    values = [dados[c] for c in cols]
    placeholders = ", ".join(["%s"] * len(cols))
    colnames = ", ".join(cols)
    if pk_cols and all(pk in cols_disp for pk in pk_cols):
        set_cols = [c for c in cols if c not in (pk_cols or [])]
        if set_cols:
            set_clause = ", ".join([f"{c} = EXCLUDED.{c}" for c in set_cols])
            sql = f"INSERT INTO {tabela} ({colnames}) VALUES ({placeholders}) ON CONFLICT ({', '.join(pk_cols)}) DO UPDATE SET {set_clause}"
        else:
            sql = f"INSERT INTO {tabela} ({colnames}) VALUES ({placeholders}) ON CONFLICT ({', '.join(pk_cols)}) DO NOTHING"
    else:
        sql = f"INSERT INTO {tabela} ({colnames}) VALUES ({placeholders})"
    cursor.execute(sql, values)

def buscar_api_cisp(raiz):
    """Busca dados da API CISP"""
    try:
        url = f"{API_BASE_URL}/{raiz}"
        response = requests.get(
            url,
            auth=HTTPBasicAuth(API_USERNAME, API_PASSWORD),
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"❌ Erro ao buscar API: {e}")
        return None

def inserir_no_postgres(raiz, dados):
    """Insere TODOS os dados no PostgreSQL"""
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        cliente = dados.get('cliente', {})
        info_sup = dados.get('informacaoSuporte', {})
        receita = dados.get('receitaFederal', {})
        ratings = dados.get('ratings', [])
        rating_atual = ratings[0] if ratings else {}
        dados_principal = {
            "raiz": raiz,
            "cnpj": cliente.get('identificacaoCliente'),
            "razao_social": cliente.get('razaoSocial'),
            "nome_fantasia": cliente.get('nomeFantasia'),
            "data_fundacao": converter_data(cliente.get('dataFundacao')),
            "endereco": cliente.get('endereco'),
            "bairro": cliente.get('bairro'),
            "cidade": cliente.get('cidade'),
            "uf": cliente.get('uf'),
            "cep": cliente.get('cep'),
            "telefone": cliente.get('telefone'),
            "email": cliente.get('email'),
            "capital_social": cliente.get('capitalSocial'),
            "cnae": cliente.get('cnae'),
            "descricao_atividade_fiscal": cliente.get('descricaoAtividadeFiscal'),
            "situacao_receita_federal": receita.get('situacaoCadastral'),
            "data_situacao_cadastral": converter_data(receita.get('dataSituacaoCadastral')),
            "rating_atual": rating_atual.get('classificacao'),
            "descricao_rating": rating_atual.get('descricaoClassificacao'),
            "total_debito_atual": info_sup.get('valorTotalDebitoAtual'),
            "total_debito_vencido_05_dias": info_sup.get('valorTotalDebitoVencidoMais05Dias'),
            "total_debito_vencido_15_dias": info_sup.get('valorTotalDebitoVencidoMais15Dias'),
            "total_debito_vencido_30_dias": info_sup.get('valorTotalDebitoVencidoMais30Dias'),
            "qtd_associadas_debito_atual": info_sup.get('quantidadeAssociadasDebitoAtual'),
            "qtd_associadas_vencido_05_dias": info_sup.get('quantidadeAssociadasDebitoVencidoMais05Dias'),
            "total_limite_credito": info_sup.get('valorTotalLimiteCredito'),
            "total_maior_acumulo": info_sup.get('valorTotalMaiorAcumulo'),
            "qtd_associadas_informacoes": info_sup.get('quantidadeAssociadasInformacoesNegociais'),
            "data_atualizacao": datetime.now(),
        }
        inserir_generico(cursor, "cisp_avaliacao_analitica", dados_principal, pk_cols=["raiz"])
        
        if tabela_tem_coluna(cursor, "cisp_restritivas", "raiz"):
            cursor.execute("DELETE FROM cisp_restritivas WHERE raiz = %s", (raiz,))
        for rest in dados.get('restritivas', []):
            data_ocorrencia = None
            if rest.get('dataOcorrencia'):
                data_ocorrencia = datetime.fromtimestamp(rest['dataOcorrencia'] / 1000).date()
            inserir_generico(cursor, "cisp_restritivas", {
                "raiz": raiz,
                "codigo_associada": rest.get('codigoAssociada'),
                "razao_social": rest.get('razaoSocial'),
                "codigo_primeira_restritiva": rest.get('codigoPrimeiraRestritiva'),
                "descricao_primeira_restritiva": rest.get('descricaoPrimeiraRestritiva'),
                "codigo_segunda_restritiva": rest.get('codigoSegundaRestritiva'),
                "descricao_segunda_restritiva": rest.get('descricaoSegundaRestritiva'),
                "data_ocorrencia": data_ocorrencia,
                "data_informacao": converter_data(rest.get('dataInformacao')),
            })
        
        if tabela_tem_coluna(cursor, "cisp_alertas", "raiz"):
            cursor.execute("DELETE FROM cisp_alertas WHERE raiz = %s", (raiz,))
        for alerta in dados.get('alertas', []):
            data_atualizacao = None
            if alerta.get('dataAtualizacao'):
                try:
                    data_atualizacao = datetime.strptime(alerta['dataAtualizacao'], '%Y-%m-%d %H:%M:%S')
                except:
                    pass
            inserir_generico(cursor, "cisp_alertas", {
                "raiz": raiz,
                "codigo_alerta": alerta.get('codigoAlerta'),
                "descricao_alerta": alerta.get('descricaoAlerta'),
                "associada_informante": alerta.get('associadaInformante'),
                "razao_social": alerta.get('razaoSocial'),
                "data_atualizacao": data_atualizacao,
            })
        
        if tabela_tem_coluna(cursor, "cisp_consultas_mensais", "raiz"):
            cursor.execute("DELETE FROM cisp_consultas_mensais WHERE raiz = %s", (raiz,))
        for consulta in dados.get('quantidadeConsultasUltimos12Meses', []):
            inserir_generico(cursor, "cisp_consultas_mensais", {
                "raiz": raiz,
                "mes_ano": consulta.get('data'),
                "quantidade_consultas": consulta.get('consultas'),
            })
        
        if tabela_tem_coluna(cursor, "cisp_associadas_consultaram", "raiz"):
            cursor.execute("DELETE FROM cisp_associadas_consultaram WHERE raiz = %s", (raiz,))
        for assoc in dados.get('associadaConsultaUltimos30Dias', []):
            inserir_generico(cursor, "cisp_associadas_consultaram", {
                "raiz": raiz,
                "codigo_associada": assoc.get('codigoAssociada'),
                "razao_social": assoc.get('razaoSocial'),
            })
        
        if tabela_tem_coluna(cursor, "cisp_associadas_nao_concederam_credito", "raiz"):
            cursor.execute("DELETE FROM cisp_associadas_nao_concederam_credito WHERE raiz = %s", (raiz,))
        for assoc in dados.get('associadaNaoConcederamCredito', []):
            inserir_generico(cursor, "cisp_associadas_nao_concederam_credito", {
                "raiz": raiz,
                "codigo_associada": assoc.get('codigoAssociada'),
                "razao_social": assoc.get('razaoSocial'),
            })
        
        conn.commit()
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro ao inserir: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

# =============================================================================
# ENDPOINT DE CONSULTA
# =============================================================================

@app.route('/api/cliente/<raiz>')
def obter_cliente(raiz):
    conn = None
    cursor = None
    try:
        conn = conectar_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("SELECT * FROM cisp_avaliacao_analitica WHERE raiz = %s LIMIT 1", (raiz,))
        principal_row = cursor.fetchone()

        principal = None
        if principal_row:
            principal = {
                "raiz": principal_row.get("raiz"),
                "cnpj": principal_row.get("cnpj"),
                "razao_social": principal_row.get("razao_social"),
                "nome_fantasia": principal_row.get("nome_fantasia"),
                "data_fundacao": principal_row.get("data_fundacao").isoformat() if principal_row.get("data_fundacao") else None,
                "endereco": principal_row.get("endereco"),
                "bairro": principal_row.get("bairro"),
                "cidade": principal_row.get("cidade"),
                "uf": principal_row.get("uf"),
                "cep": principal_row.get("cep"),
                "telefone": principal_row.get("telefone"),
                "email": principal_row.get("email"),
                "capital_social": principal_row.get("capital_social"),
                "cnae": principal_row.get("cnae"),
                "descricao_atividade_fiscal": principal_row.get("descricao_atividade_fiscal"),
                "situacao_receita_federal": principal_row.get("situacao_receita_federal"),
                "data_situacao_cadastral": principal_row.get("data_situacao_cadastral").isoformat() if principal_row.get("data_situacao_cadastral") else None,
                "rating_atual": principal_row.get("rating_atual"),
                "descricao_rating": principal_row.get("descricao_rating"),
                "total_debito_atual": principal_row.get("total_debito_atual"),
                "total_debito_vencido_05_dias": principal_row.get("total_debito_vencido_05_dias"),
                "total_debito_vencido_15_dias": principal_row.get("total_debito_vencido_15_dias"),
                "total_debito_vencido_30_dias": principal_row.get("total_debito_vencido_30_dias"),
                "qtd_associadas_debito_atual": principal_row.get("qtd_associadas_debito_atual"),
                "qtd_associadas_vencido_05_dias": principal_row.get("qtd_associadas_vencido_05_dias"),
                "total_limite_credito": principal_row.get("total_limite_credito"),
                "total_maior_acumulo": principal_row.get("total_maior_acumulo"),
                "qtd_associadas_informacoes": principal_row.get("qtd_associadas_informacoes"),
                "data_atualizacao": principal_row.get("data_atualizacao").isoformat() if principal_row.get("data_atualizacao") else None,
            }

        cursor.execute("SELECT * FROM cisp_restritivas WHERE raiz = %s", (raiz,))
        restritivas_rows = cursor.fetchall()
        restritivas = [
            {
                "codigo_associada": r.get("codigo_associada"),
                "razao_social": r.get("razao_social"),
                "codigo_primeira_restritiva": r.get("codigo_primeira_restritiva"),
                "descricao_primeira_restritiva": r.get("descricao_primeira_restritiva"),
                "codigo_segunda_restritiva": r.get("codigo_segunda_restritiva"),
                "descricao_segunda_restritiva": r.get("descricao_segunda_restritiva"),
                "data_ocorrencia": r.get("data_ocorrencia").isoformat() if r.get("data_ocorrencia") else None,
                "data_informacao": r.get("data_informacao").isoformat() if r.get("data_informacao") else None,
            }
            for r in restritivas_rows
        ]

        cursor.execute("SELECT * FROM cisp_alertas WHERE raiz = %s", (raiz,))
        alertas_rows = cursor.fetchall()
        alertas = [
            {
                "codigo_alerta": a.get("codigo_alerta"),
                "descricao_alerta": a.get("descricao_alerta"),
                "associada_informante": a.get("associada_informante"),
                "razao_social": a.get("razao_social"),
                "data_atualizacao": a.get("data_atualizacao").isoformat() if a.get("data_atualizacao") else None,
            }
            for a in alertas_rows
        ]

        cursor.execute("SELECT * FROM cisp_consultas_mensais WHERE raiz = %s", (raiz,))
        consultas_rows = cursor.fetchall()
        consultas_mensais = [
            {"mes_ano": c.get("mes_ano"), "quantidade_consultas": c.get("quantidade_consultas")}
            for c in consultas_rows
        ]

        cursor.execute("SELECT * FROM cisp_associadas_consultaram WHERE raiz = %s", (raiz,))
        assoc_cons_rows = cursor.fetchall()
        associadas_consultaram = [
            {"codigo_associada": s.get("codigo_associada"), "razao_social": s.get("razao_social")}
            for s in assoc_cons_rows
        ]

        cursor.execute("SELECT * FROM cisp_associadas_nao_concederam_credito WHERE raiz = %s", (raiz,))
        assoc_nao_rows = cursor.fetchall()
        associadas_nao_concederam = [
            {"codigo_associada": s.get("codigo_associada"), "razao_social": s.get("razao_social")}
            for s in assoc_nao_rows
        ]

        return jsonify({
            "success": True,
            "raiz": raiz,
            "principal": principal,
            "restritivas": restritivas,
            "alertas": alertas,
            "consultas_mensais": consultas_mensais,
            "associadas_consultaram": associadas_consultaram,
            "associadas_nao_concederam": associadas_nao_concederam,
        })
    except Exception as e:
        return jsonify({"success": False, "erro": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# =============================================================================
# ENDPOINT PRINCIPAL
# =============================================================================

@app.route('/api/sincronizar/<raiz>')
def sincronizar(raiz):
    """
    ENDPOINT PRINCIPAL - Power BI chama esse endpoint
    
    GET http://localhost:5000/api/sincronizar/45543915
    
    1. Busca dados na API CISP
    2. Insere no PostgreSQL
    3. Retorna sucesso/erro
    """
    print(f"\n{'='*60}")
    print(f"📡 REQUISIÇÃO RECEBIDA DO POWER BI")
    print(f"   Raiz: {raiz}")
    print(f"{'='*60}\n")
    
    try:
        # Passo 1: Buscar na API CISP
        print(f"1️⃣  Buscando raiz {raiz} na API CISP...")
        dados = buscar_api_cisp(raiz)
        
        if not dados:
            print(f"❌ Raiz {raiz} não encontrada na API CISP")
            return jsonify({
                'success': False,
                'raiz': raiz,
                'mensagem': 'Raiz não encontrada na API CISP'
            }), 404
        
        print(f"✅ Dados obtidos da API CISP")
        
        # Passo 2: Inserir no PostgreSQL
        print(f"2️⃣  Inserindo dados no PostgreSQL...")
        sucesso = inserir_no_postgres(raiz, dados)
        
        if sucesso:
            print(f"✅ Raiz {raiz} sincronizada com sucesso!")
            print(f"\n{'='*60}\n")
            return jsonify({
                'success': True,
                'raiz': raiz,
                'mensagem': 'Dados sincronizados com sucesso',
                'timestamp': str(datetime.now())
            })
        else:
            print(f"❌ Erro ao inserir no PostgreSQL")
            return jsonify({
                'success': False,
                'raiz': raiz,
                'mensagem': 'Erro ao inserir dados no PostgreSQL'
            }), 500
        
    except Exception as e:
        print(f"❌ ERRO: {e}")
        return jsonify({
            'success': False,
            'raiz': raiz,
            'mensagem': str(e)
        }), 500

@app.route('/api/health')
def health():
    """Verifica se está funcionando"""
    try:
        conn = conectar_db()
        conn.close()
        return jsonify({
            'status': 'ok',
            'database': 'conectado',
            'timestamp': str(datetime.now())
        })
    except Exception as e:
        return jsonify({
            'status': 'erro',
            'database': 'desconectado',
            'erro': str(e)
        }), 500

@app.route('/')
def pagina():
    html = """
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Avaliação de Crédito - CISP</title>
  <style>
    :root { color-scheme: light dark; }
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 0; padding: 24px; }
    header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
    h1 { font-size: 20px; margin: 0; }
    .row { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
    .card { border: 1px solid rgba(0,0,0,.15); border-radius: 8px; padding: 12px; background: rgba(255,255,255,.6); backdrop-filter: saturate(180%) blur(4px); }
    .card h2 { font-size: 16px; margin: 0 0 8px; }
    .input { display: flex; gap: 8px; margin-top: 8px; }
    input[type=text] { flex: 1; padding: 10px; border: 1px solid rgba(0,0,0,.2); border-radius: 6px; font-size: 14px; }
    button { padding: 10px 14px; border: 0; border-radius: 6px; background: #2563eb; color: #fff; font-weight: 600; cursor: pointer; }
    button:disabled { opacity: .6; cursor: default; }
    .grid2 { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 8px; }
    .list { display: grid; gap: 6px; }
    .item { padding: 8px; border: 1px solid rgba(0,0,0,.1); border-radius: 6px; }
    .muted { color: #666; font-size: 12px; }
    .metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
    .metric { border: 1px dashed rgba(0,0,0,.2); border-radius: 6px; padding: 8px; }
    .metric .label { font-size: 12px; color: #555; }
    .metric .value { font-size: 16px; font-weight: 700; }
    @media (max-width: 1000px) { .row, .metrics { grid-template-columns: repeat(2, minmax(0,1fr)); } }
    @media (max-width: 640px) { .row, .metrics { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <header>
    <h1>Avaliação de Crédito</h1>
  </header>

  <div class="card">
    <div class="grid2">
      <div>
        <div>Raiz do CNPJ</div>
        <div class="muted">Digite os 8 primeiros dígitos</div>
      </div>
      <div class="input">
        <input id="raiz" type="text" placeholder="Ex.: 45543915" maxlength="8" pattern="\\d{8}">
        <button id="buscar">Buscar</button>
      </div>
    </div>
    <div id="status" class="muted" style="margin-top:8px;"></div>
  </div>

  <div class="row" style="margin-top: 12px;">
    <div class="card">
      <h2>Dados do Cliente</h2>
      <div id="cliente"></div>
    </div>
    <div class="card">
      <h2>Rating e Débitos</h2>
      <div class="metrics" id="metrics"></div>
    </div>
    <div class="card">
      <h2>Restritivas</h2>
      <div class="list" id="restritivas"></div>
    </div>
    <div class="card">
      <h2>Alertas</h2>
      <div class="list" id="alertas"></div>
    </div>
  </div>

  <div class="row" style="margin-top: 12px;">
    <div class="card">
      <h2>Consultas (12 meses)</h2>
      <div class="list" id="consultas"></div>
    </div>
    <div class="card">
      <h2>Associadas que Consultaram (30 dias)</h2>
      <div class="list" id="assoc_cons"></div>
    </div>
    <div class="card">
      <h2>Associadas que Não Concederam Crédito</h2>
      <div class="list" id="assoc_nao"></div>
    </div>
    <div class="card">
      <h2>Atualização</h2>
      <div id="atualizacao" class="muted"></div>
    </div>
  </div>

  <script>
    const el = (id) => document.getElementById(id);
    const fmt = {
      moeda: (v) => v == null ? "-" : new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(v),
      numero: (v) => v == null ? "-" : new Intl.NumberFormat('pt-BR').format(v),
      data: (v) => v ? new Date(v).toLocaleDateString('pt-BR') : "-",
    };
    async function sincronizar(raiz) {
      const r = await fetch(`/api/sincronizar/${raiz}`);
      return r.ok;
    }
    async function obter(raiz) {
      const r = await fetch(`/api/cliente/${raiz}`);
      return await r.json();
    }
    function render(data) {
      const p = data.principal;
      el('cliente').innerHTML = p ? `
        <div class="list">
          <div class="item"><strong>${p.razao_social || '-'}</strong></div>
          <div class="item">${p.nome_fantasia || '-'}</div>
          <div class="item">${p.cnpj || '-'}</div>
          <div class="item">${[p.endereco,p.bairro,p.cidade,p.uf,p.cep].filter(Boolean).join(', ') || '-'}</div>
          <div class="item">Situação RF: ${p.situacao_receita_federal || '-'}</div>
          <div class="item">CNAE: ${p.cnae || '-'}</div>
        </div>
      ` : '<div class="muted">Nenhum dado encontrado</div>';

      el('metrics').innerHTML = p ? `
        <div class="metric"><div class="label">Rating</div><div class="value">${p.rating_atual || '-'}</div></div>
        <div class="metric"><div class="label">Débito Atual</div><div class="value">${fmt.moeda(p.total_debito_atual)}</div></div>
        <div class="metric"><div class="label">Limite de Crédito</div><div class="value">${fmt.moeda(p.total_limite_credito)}</div></div>
        <div class="metric"><div class="label">Maior Acúmulo</div><div class="value">${fmt.moeda(p.total_maior_acumulo)}</div></div>
      ` : '';

      el('restritivas').innerHTML = (data.restritivas||[]).length ? (data.restritivas||[]).slice(0,10).map(r => `
        <div class="item">
          <div><strong>${r.descricao_primeira_restritiva || '-'}</strong></div>
          <div class="muted">${fmt.data(r.data_ocorrencia)} • ${r.razao_social || '-'}</div>
        </div>
      `).join('') : '<div class="muted">Sem restritivas</div>';

      el('alertas').innerHTML = (data.alertas||[]).length ? (data.alertas||[]).slice(0,10).map(a => `
        <div class="item">
          <div><strong>${a.descricao_alerta || '-'}</strong></div>
          <div class="muted">${fmt.data(a.data_atualizacao)} • ${a.razao_social || '-'}</div>
        </div>
      `).join('') : '<div class="muted">Sem alertas</div>';

      el('consultas').innerHTML = (data.consultas_mensais||[]).length ? (data.consultas_mensais||[]).map(c => `
        <div class="item">${c.mes_ano || '-'}: ${fmt.numero(c.quantidade_consultas)}</div>
      `).join('') : '<div class="muted">Sem consultas</div>';

      el('assoc_cons').innerHTML = (data.associadas_consultaram||[]).length ? (data.associadas_consultaram||[]).map(s => `
        <div class="item">${s.razao_social || '-'}</div>
      `).join('') : '<div class="muted">Sem registros</div>';

      el('assoc_nao').innerHTML = (data.associadas_nao_concederam||[]).length ? (data.associadas_nao_concederam||[]).map(s => `
        <div class="item">${s.razao_social || '-'}</div>
      `).join('') : '<div class="muted">Sem registros</div>';

      el('atualizacao').textContent = p && p.data_atualizacao ? `Atualizado em ${fmt.data(p.data_atualizacao)}` : '';
    }
    async function buscar() {
      const raiz = el('raiz').value.trim();
      if (!/^[0-9]{8}$/.test(raiz)) {
        el('status').textContent = 'Informe a raiz (8 dígitos).';
        return;
      }
      el('status').textContent = 'Sincronizando...';
      el('buscar').disabled = true;
      try {
        await sincronizar(raiz);
        el('status').textContent = 'Carregando dados...';
        const data = await obter(raiz);
        if (data.success) {
          render(data);
          el('status').textContent = 'Pronto';
        } else {
          el('status').textContent = 'Erro ao obter dados';
        }
      } catch (e) {
        el('status').textContent = 'Erro de conexão';
      } finally {
        el('buscar').disabled = false;
      }
    }
    el('buscar').addEventListener('click', buscar);
    el('raiz').addEventListener('keydown', (e) => { if (e.key === 'Enter') buscar(); });
  </script>
</body>
</html>
    """
    return Response(html, mimetype='text/html')

# =============================================================================
# INICIAR API
# =============================================================================

if __name__ == '__main__':
    print("""
╔════════════════════════════════════════════════════════════════╗
║                  API CISP PARA POWER BI                        ║
║                    RODANDO NA PORTA 5000                       ║
╚════════════════════════════════════════════════════════════════╝

📡 ENDPOINT PRINCIPAL:

   http://localhost:5000/api/sincronizar/{raiz}
   
   Exemplo: http://localhost:5000/api/sincronizar/45543915

🔧 TESTAR:

   http://localhost:5000/api/health

💡 USE NO POWER BI:

   Web.Contents("http://localhost:5000/api/sincronizar/45543915")

    """)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
