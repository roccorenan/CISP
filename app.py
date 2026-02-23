"""
API FLASK PARA POWER BI + PORTAL WEB (UI) PARA CONSULTA DE RAIZ CNPJ
Porta: 5000

- /api/sincronizar/<raiz>  -> busca na API CISP e grava no Postgres
- /api/cliente/<raiz>      -> retorna dados do Postgres
- /                         -> página web profissional para consulta
"""

import os
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, jsonify, render_template
from flask_cors import CORS
from datetime import datetime
from requests.auth import HTTPBasicAuth

# Carrega .env automaticamente (opcional) 
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

# Configurações
API_BASE_URL = "https://servicos.cisp.com.br/v1/avaliacao-analitica/raiz"
API_USERNAME = os.environ.get('CISP_USERNAME')
API_PASSWORD = os.environ.get('CISP_PASSWORD')

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', '127.0.0.1'),
    'port': os.environ.get('DB_PORT', '5432'),
    'database': os.environ.get('DB_NAME', 'dbDataLakePrd'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('POSTGRES'),
    'options': f"-c search_path={os.environ.get('DB_SCHEMA', 'scsilverlayer')}"
}

def conectar_db():
    return psycopg2.connect(**DB_CONFIG)

def converter_data(data_str):
    if not data_str:
        return None
    try:
        return datetime.strptime(data_str, '%Y-%m-%d').date()
    except Exception:
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
          ORDER BY ordinal_position
    """, (tabela,))
    rows = cursor.fetchall()
    cols = [(r.get('column_name') if isinstance(r, dict) else r[0]) for r in rows]
    _cols_cache[tabela] = cols
    return cols


def tabela_tem_coluna(cursor, tabela, coluna):
    return coluna in obter_colunas(cursor, tabela)

def escolher_col(cursor, tabela, opcoes):
    cols = obter_colunas(cursor, tabela)
    for c in opcoes:
        if c in cols:
            return c
    return None

def tabela_existe(cursor, tabela):
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = (SELECT current_schema())
              AND table_name = %s
        )
    """, (tabela,))
    row = cursor.fetchone()
    if isinstance(row, dict):
        return bool(row.get('exists')) if row else False
    return bool(row[0]) if row else False

def montar_dict(cursor, tabela, spec):
    out = {}
    for value, opcoes in spec:
        col = escolher_col(cursor, tabela, opcoes)
        if col is not None:
            out[col] = value
    return out

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
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"❌ Erro ao buscar API: {e}")
        return None

def inserir_no_postgres(raiz, dados):
    """Insere dados no PostgreSQL"""
    conn = conectar_db()
    cursor = conn.cursor()

    try:
        cliente = dados.get('cliente', {})
        info_sup = dados.get('informacaoSuporte', {})
        receita = dados.get('receitaFederal', {})
        segmentos = dados.get('positivaSegmentos', []) or []
        ratings = dados.get('ratings', [])
        rating_atual = ratings[0] if ratings else {}

        melhor_maior_valor = None
        melhor_maior_data = None
        melhor_maior_codigo = None
        ultima_compra_data = None
        ultima_compra_codigo = None
        try:
            for seg in segmentos:
                for pos in seg.get('positivas', []) or []:
                    v = pos.get('valorMaiorAcumulo')
                    d_maior = converter_data(pos.get('dataMaiorAcumulo'))
                    cod = pos.get('codigoAssociada')
                    if v is not None:
                        if (melhor_maior_valor is None) or (float(v) > float(melhor_maior_valor)):
                            melhor_maior_valor = v
                            melhor_maior_data = d_maior
                            melhor_maior_codigo = cod
                    d_ult = converter_data(pos.get('dataUltimaCompra'))
                    if d_ult:
                        if (ultima_compra_data is None) or (d_ult > ultima_compra_data):
                            ultima_compra_data = d_ult
                            ultima_compra_codigo = cod
        except Exception:
            pass

        dados_principal = {
            "raiz": raiz,
            "cnpj": cliente.get('identificacaoCliente'),
            "razao_social": cliente.get('razaoSocial'),
            "nome_fantasia": cliente.get('nomeFantasia'),
            "data_fundacao": converter_data(cliente.get('dataFundacao')),
            "data_inclusao_cisp": converter_data(cliente.get('dataCadastramento')),
            "endereco": cliente.get('endereco'),
            "bairro": cliente.get('bairro'),
            "cidade": cliente.get('cidade'),
            "uf": cliente.get('uf'),
            "cep": cliente.get('cep'),
            "telefone": cliente.get('telefone'),
            "email": cliente.get('email'),
            "capital_social": cliente.get('capitalSocial'),
            "cnae": cliente.get('cnae'),
            "descricao_atividade_fiscal": cliente.get('descricaoAtividadeFiscal') or receita.get('descricaoAtividadeFiscal'),
            "situacao_receita_federal": receita.get('situacaoCadastral'),
            "data_situacao_cadastral": converter_data(receita.get('dataSituacaoCadastral')),
            "rating_atual": rating_atual.get('classificacao'),
            "descricao_rating": rating_atual.get('descricaoClassificacao'),
            "data_maior_acumulo": melhor_maior_data,
            "data_ultima_compra": ultima_compra_data,
            "codigo_associada_ultima_compra": ultima_compra_codigo,
            "ultima_atualizacao": datetime.now(),
            "data_atualizacao": datetime.now(),
        }
        dados_principal.update(montar_dict(cursor, "cisp_avaliacao_analitica", [
            (info_sup.get('valorTotalDebitoAtual'), ["valor_total_debito_atual", "total_debito_atual"]),
            (info_sup.get('valorTotalDebitoVencidoMais05Dias'), ["valor_total_debito_vencido_05dias", "valor_total_debito_vencido_5dias"]),
            (info_sup.get('valorTotalDebitoVencidoMais15Dias'), ["valor_total_debito_vencido_15dias"]),
            (info_sup.get('valorTotalDebitoVencidoMais30Dias'), ["valor_total_debito_vencido_30dias"]),
            (info_sup.get('quantidadeAssociadasDebitoAtual'), ["qtd_associadas_debito_atual"]),
            (info_sup.get('quantidadeAssociadasDebitoVencidoMais05Dias'), ["qtd_associadas_debito_vencido_05dias", "qtd_associadas_debito_vencido_5dias"]),
            (info_sup.get('quantidadeAssociadasDebitoVencidoMais15Dias'), ["qtd_associadas_debito_vencido_15dias"]),
            (info_sup.get('quantidadeAssociadasDebitoVencidoMais30Dias'), ["qtd_associadas_debito_vencido_30dias"]),
            (info_sup.get('valorTotalLimiteCredito'), ["valor_total_limite_credito", "total_limite_credito"]),
            (info_sup.get('valorTotalMaiorAcumulo'), ["valor_total_maior_acumulo", "total_maior_acumulo"]),
            (info_sup.get('quantidadeAssociadasInformacoesNegociais'), ["qtd_associadas_informacoes_negociais", "qtd_associadas_informacoes"]),
            (info_sup.get('quantidadeAssociadasLimiteCredito'), ["qtd_associadas_limite_credito"]),
            (info_sup.get('quantidadeAssociadasMaiorAcumulo'), ["qtd_associadas_maior_acumulo"]),
            (info_sup.get('quantidadeAssociadasVendasUltimos2Meses'), ["qtd_associadas_vendas_ultimos_2meses"]),
            (melhor_maior_data, ["data_maior_acumulo"]),
            (ultima_compra_data, ["data_ultima_compra"]),
            (ultima_compra_codigo, ["codigo_associada_ultima_compra"]),
        ]))
        root_main = escolher_col(cursor, "cisp_avaliacao_analitica", ["raiz", "raizcnpj", "raiz_cnpj", "raizCnpj"])
        if root_main:
            dados_principal[root_main] = raiz
        inserir_generico(cursor, "cisp_avaliacao_analitica", dados_principal, pk_cols=[root_main] if root_main else None)

        root_rest = escolher_col(cursor, "cisp_restritivas", ["raiz", "raizcnpj", "raiz_cnpj", "raizCnpj"])
        if root_rest:
            cursor.execute(f"DELETE FROM cisp_restritivas WHERE {root_rest} = %s", (raiz,))
        for rest in dados.get('restritivas', []):
            data_ocorrencia = None
            if rest.get('dataOcorrencia'):
                try:
                    data_ocorrencia = datetime.fromtimestamp(rest['dataOcorrencia'] / 1000).date()
                except Exception:
                    data_ocorrencia = None

            inserir_generico(
                cursor,
                "cisp_restritivas",
                montar_dict(
                    cursor,
                    "cisp_restritivas",
                    [
                        (raiz, ["raiz", "raizcnpj", "raiz_cnpj", "raizCnpj"]),
                        (rest.get('codigoAssociada'), ["codigo_associada", "codigoAssociada"]),
                        (rest.get('razaoSocial'), ["razao_social", "razaoSocial"]),
                        (rest.get('codigoPrimeiraRestritiva'), ["codigo_primeira_restritiva"]),
                        (rest.get('descricaoPrimeiraRestritiva'), ["descricao_primeira_restritiva"]),
                        (rest.get('codigoSegundaRestritiva'), ["codigo_segunda_restritiva"]),
                        (rest.get('descricaoSegundaRestritiva'), ["descricao_segunda_restritiva"]),
                        (data_ocorrencia, ["data_ocorrencia"]),
                        (converter_data(rest.get('dataInformacao')), ["data_informacao"]),
                    ],
                ),
            )

        root_alert = escolher_col(cursor, "cisp_alertas", ["raiz", "raizcnpj", "raiz_cnpj", "raizCnpj"])
        if root_alert:
            cursor.execute(f"DELETE FROM cisp_alertas WHERE {root_alert} = %s", (raiz,))
        for alerta in dados.get('alertas', []):
            data_atualizacao = None
            if alerta.get('dataAtualizacao'):
                try:
                    data_atualizacao = datetime.strptime(alerta['dataAtualizacao'], '%Y-%m-%d %H:%M:%S')
                except Exception:
                    data_atualizacao = None

            inserir_generico(
                cursor,
                "cisp_alertas",
                montar_dict(
                    cursor,
                    "cisp_alertas",
                    [
                        (raiz, ["raiz", "raizcnpj", "raiz_cnpj", "raizCnpj"]),
                        (alerta.get('codigoAlerta'), ["codigo_alerta", "codigo", "cod_alerta"]),
                        (alerta.get('descricaoAlerta'), ["descricao_alerta", "descricao", "desc_alerta"]),
                        (alerta.get('associadaInformante'), ["associada_informante", "associada", "informante"]),
                        (alerta.get('razaoSocial'), ["razao_social", "razaoSocial"]),
                        (data_atualizacao, ["data_atualizacao", "atualizacao", "data"]),
                    ],
                ),
            )

        root_cons = escolher_col(cursor, "cisp_consultas_mensais", ["raiz", "raizcnpj", "raiz_cnpj", "raizCnpj"])
        if root_cons:
            cursor.execute(f"DELETE FROM cisp_consultas_mensais WHERE {root_cons} = %s", (raiz,))
        for consulta in dados.get('quantidadeConsultasUltimos12Meses', []):
            inserir_generico(
                cursor,
                "cisp_consultas_mensais",
                montar_dict(
                    cursor,
                    "cisp_consultas_mensais",
                    [
                        (raiz, ["raiz", "raizcnpj", "raiz_cnpj", "raizCnpj"]),
                        (consulta.get('data'), ["mes_ano", "mes", "data"]),
                        (consulta.get('consultas'), ["quantidade_consultas", "qtd_consultas"]),
                    ],
                ),
            )

        root_assoc_cons = escolher_col(cursor, "cisp_associadas_consultaram", ["raiz", "raizcnpj", "raiz_cnpj", "raizCnpj"])
        if root_assoc_cons:
            cursor.execute(f"DELETE FROM cisp_associadas_consultaram WHERE {root_assoc_cons} = %s", (raiz,))
        for assoc in dados.get('associadaConsultaUltimos30Dias', []):
            inserir_generico(
                cursor,
                "cisp_associadas_consultaram",
                montar_dict(
                    cursor,
                    "cisp_associadas_consultaram",
                    [
                        (raiz, ["raiz", "raizcnpj", "raiz_cnpj", "raizCnpj"]),
                        (assoc.get('codigoAssociada'), ["codigo_associada", "codigoAssociada", "cod_associada"]),
                        (assoc.get('razaoSocial'), ["razao_social", "razaoSocial"]),
                    ],
                ),
            )

        root_assoc_nao = escolher_col(cursor, "cisp_associadas_nao_concederam_credito", ["raiz", "raizcnpj", "raiz_cnpj", "raizCnpj"])
        if root_assoc_nao:
            cursor.execute(f"DELETE FROM cisp_associadas_nao_concederam_credito WHERE {root_assoc_nao} = %s", (raiz,))
        for assoc in dados.get('associadaNaoConcederamCredito', []):
            inserir_generico(
                cursor,
                "cisp_associadas_nao_concederam_credito",
                montar_dict(
                    cursor,
                    "cisp_associadas_nao_concederam_credito",
                    [
                        (raiz, ["raiz", "raizcnpj", "raiz_cnpj", "raizCnpj"]),
                        (assoc.get('codigoAssociada'), ["codigo_associada", "codigoAssociada", "cod_associada"]),
                        (assoc.get('razaoSocial'), ["razao_social", "razaoSocial"]),
                    ],
                ),
            )

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
# API
# =============================================================================

@app.route('/api/cliente/<raiz>')
def obter_cliente(raiz):
    conn = None
    cursor = None
    try:
        # =====================================================================
        # 1. SEMPRE busca na CISP primeiro e atualiza o banco
        # =====================================================================
        payload_cisp = buscar_api_cisp(raiz)
        if payload_cisp:
            inserir_no_postgres(raiz, payload_cisp)

        # =====================================================================
        # 2. Lê do banco (já atualizado)
        # =====================================================================
        conn = conectar_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        root_col = escolher_col(cursor, "cisp_avaliacao_analitica", ["raiz", "raizcnpj", "raiz_cnpj", "raizCnpj"]) or "raiz"
        cursor.execute(f"SELECT * FROM cisp_avaliacao_analitica WHERE {root_col} = %s LIMIT 1", (raiz,))
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
                "cidade": principal_row.get("cidade") or principal_row.get("municipio"),
                "uf": principal_row.get("uf"),
                "cep": principal_row.get("cep"),
                "telefone": principal_row.get("telefone"),
                "email": principal_row.get("email"),
                "capital_social": principal_row.get("capital_social"),
                "cnae": principal_row.get("cnae"),
                "descricao_atividade_fiscal": principal_row.get("descricao_atividade_fiscal"),
                "situacao_receita_federal": principal_row.get("situacao_receita_federal"),
                "data_situacao_cadastral": principal_row.get("data_situacao_cadastral").isoformat() if principal_row.get("data_situacao_cadastral") else None,
                "rating_atual": principal_row.get("rating_atual") or principal_row.get("classificacao_atual_cisp") or principal_row.get("classificacao_cisp_atual") or principal_row.get("classificacao"),
                "descricao_rating": principal_row.get("descricao_rating") or principal_row.get("descricao_classificacao") or principal_row.get("descricao_classificacao_atual"),
                "total_debito_atual": principal_row.get("total_debito_atual") or principal_row.get("valor_total_debito_atual"),
                "total_debito_vencido_05_dias": principal_row.get("total_debito_vencido_05_dias") or principal_row.get("valor_total_debito_vencido_05dias") or principal_row.get("valor_total_debito_vencido_5dias"),
                "total_debito_vencido_15_dias": principal_row.get("total_debito_vencido_15_dias") or principal_row.get("valor_total_debito_vencido_15dias"),
                "total_debito_vencido_30_dias": principal_row.get("total_debito_vencido_30_dias") or principal_row.get("valor_total_debito_vencido_30dias"),
                "qtd_associadas_debito_atual": principal_row.get("qtd_associadas_debito_atual"),
                "qtd_associadas_vencido_05_dias": principal_row.get("qtd_associadas_vencido_05_dias") or principal_row.get("qtd_associadas_debito_vencido_05dias") or principal_row.get("qtd_associadas_debito_vencido_5dias"),
                "total_limite_credito": principal_row.get("total_limite_credito") or principal_row.get("valor_total_limite_credito"),
                "total_maior_acumulo": principal_row.get("total_maior_acumulo") or principal_row.get("valor_total_maior_acumulo"),
                "qtd_associadas_informacoes": principal_row.get("qtd_associadas_informacoes") or principal_row.get("qtd_associadas_informacoes_negociais"),
                "qtd_associadas_limite_credito": principal_row.get("qtd_associadas_limite_credito"),
                "qtd_associadas_maior_acumulo": principal_row.get("qtd_associadas_maior_acumulo"),
                "qtd_associadas_vendas_ultimos_2meses": principal_row.get("qtd_associadas_vendas_ultimos_2meses"),
                "data_maior_acumulo": principal_row.get("data_maior_acumulo").isoformat() if principal_row.get("data_maior_acumulo") else None,
                "data_ultima_compra": principal_row.get("data_ultima_compra").isoformat() if principal_row.get("data_ultima_compra") else None,
                "codigo_associada_ultima_compra": principal_row.get("codigo_associada_ultima_compra"),
                "data_inclusao_cisp": principal_row.get("data_inclusao_cisp").isoformat() if principal_row.get("data_inclusao_cisp") else None,
                "hora_modificacao": principal_row.get("hora_modificacao"),
                "usuario_modificacao": principal_row.get("usuario_modificacao"),
                "situacao_sintegra": principal_row.get("situacao_sintegra"),
                "data_atualizacao": principal_row.get("data_atualizacao").isoformat() if principal_row.get("data_atualizacao") else None,
            }

        # Fallback: se não salvou no banco, monta principal direto do payload da CISP
        if not principal and payload_cisp:
            principal = {}
            try:
                cli = payload_cisp.get("cliente") or {}
                rf = payload_cisp.get("receitaFederal") or {}
                principal.update({
                    "raiz": cli.get("raizCnpj") or raiz,
                    "cnpj": cli.get("identificacaoCliente"),
                    "razao_social": cli.get("razaoSocial") or rf.get("razaoSocial"),
                    "nome_fantasia": cli.get("nomeFantasia"),
                    "data_fundacao": cli.get("dataFundacao"),
                    "endereco": cli.get("endereco"),
                    "bairro": cli.get("bairro"),
                    "cidade": cli.get("cidade"),
                    "uf": cli.get("uf") or rf.get("uf"),
                    "cep": cli.get("cep"),
                    "telefone": cli.get("telefone"),
                    "email": cli.get("email"),
                    "cnae": cli.get("cnae") or rf.get("cnae"),
                    "descricao_atividade_fiscal": cli.get("descricaoAtividadeFiscal") or rf.get("descricaoAtividadeFiscal"),
                    "situacao_receita_federal": rf.get("situacaoCadastral"),
                    "data_situacao_cadastral": rf.get("dataSituacaoCadastral"),
                })
            except Exception:
                pass

        # Complementa campos de datas e rating direto do payload_cisp já obtido
        if payload_cisp and principal is not None:
            try:
                info_sup = payload_cisp.get("informacaoSuporte", {}) or {}
                ratings = payload_cisp.get("ratings") or []
                segmentos = payload_cisp.get("positivaSegmentos") or []
                melhor_maior_data = None
                ultima_compra_data = None
                ultima_compra_codigo = None
                melhor_maior_valor = None
                for seg in segmentos:
                    for pos in seg.get("positivas", []) or []:
                        v = pos.get("valorMaiorAcumulo")
                        d_maior = converter_data(pos.get("dataMaiorAcumulo"))
                        d_ult = converter_data(pos.get("dataUltimaCompra"))
                        cod = pos.get("codigoAssociada")
                        if v is not None and d_maior:
                            if (melhor_maior_valor is None) or (float(v) > float(melhor_maior_valor)):
                                melhor_maior_valor = v
                                melhor_maior_data = d_maior
                        if d_ult:
                            if (ultima_compra_data is None) or (d_ult > ultima_compra_data):
                                ultima_compra_data = d_ult
                                ultima_compra_codigo = cod
                if melhor_maior_data and not principal.get("data_maior_acumulo"):
                    principal["data_maior_acumulo"] = melhor_maior_data.isoformat()
                if ultima_compra_data and not principal.get("data_ultima_compra"):
                    principal["data_ultima_compra"] = ultima_compra_data.isoformat()
                    principal["codigo_associada_ultima_compra"] = ultima_compra_codigo
                if (not principal.get("rating_atual")) and ratings:
                    r0 = ratings[0]
                    principal["rating_atual"] = r0.get("classificacao")
                    principal["descricao_rating"] = r0.get("descricaoClassificacao")
                principal.setdefault("total_limite_credito", info_sup.get("valorTotalLimiteCredito"))
                principal.setdefault("total_maior_acumulo", info_sup.get("valorTotalMaiorAcumulo"))
                principal.setdefault("total_debito_atual", info_sup.get("valorTotalDebitoAtual"))
                principal.setdefault("total_debito_vencido_05_dias", info_sup.get("valorTotalDebitoVencidoMais05Dias"))
                principal.setdefault("total_debito_vencido_15_dias", info_sup.get("valorTotalDebitoVencidoMais15Dias"))
                principal.setdefault("total_debito_vencido_30_dias", info_sup.get("valorTotalDebitoVencidoMais30Dias"))
                try:
                    comp = payload_cisp.get("informacoesComportamentaisSegmentos") or []
                    if isinstance(comp, list) and comp:
                        ultimo = comp[0]
                        total_ultimo = ultimo.get("total")
                        if total_ultimo is not None:
                            principal["total_debito_atual"] = total_ultimo
                except Exception:
                    pass
            except Exception:
                pass

        root_rest = escolher_col(cursor, "cisp_restritivas", ["raiz", "raizcnpj", "raiz_cnpj", "raizCnpj"]) or "raiz"
        cursor.execute(f"SELECT * FROM cisp_restritivas WHERE {root_rest} = %s", (raiz,))
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

        root_alert = escolher_col(cursor, "cisp_alertas", ["raiz", "raizcnpj", "raiz_cnpj", "raizCnpj"]) or "raiz"
        cursor.execute(f"SELECT * FROM cisp_alertas WHERE {root_alert} = %s", (raiz,))
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

        root_cons = escolher_col(cursor, "cisp_consultas_mensais", ["raiz", "raizcnpj", "raiz_cnpj", "raizCnpj"]) or "raiz"
        cursor.execute(f"SELECT * FROM cisp_consultas_mensais WHERE {root_cons} = %s", (raiz,))
        consultas_rows = cursor.fetchall()
        consultas_mensais = [
            {"mes_ano": c.get("mes_ano"), "quantidade_consultas": c.get("quantidade_consultas")}
            for c in consultas_rows
        ]

        root_assoc_cons = escolher_col(cursor, "cisp_associadas_consultaram", ["raiz", "raizcnpj", "raiz_cnpj", "raizCnpj"]) or "raiz"
        cursor.execute(f"SELECT * FROM cisp_associadas_consultaram WHERE {root_assoc_cons} = %s", (raiz,))
        assoc_cons_rows = cursor.fetchall()
        associadas_consultaram = [
            {"codigo_associada": s.get("codigo_associada"), "razao_social": s.get("razao_social")}
            for s in assoc_cons_rows
        ]

        root_assoc_nao = escolher_col(cursor, "cisp_associadas_nao_concederam_credito", ["raiz", "raizcnpj", "raiz_cnpj", "raizCnpj"]) or "raiz"
        cursor.execute(f"SELECT * FROM cisp_associadas_nao_concederam_credito WHERE {root_assoc_nao} = %s", (raiz,))
        assoc_nao_rows = cursor.fetchall()
        associadas_nao_concederam = [
            {"codigo_associada": s.get("codigo_associada"), "razao_social": s.get("razao_social")}
            for s in assoc_nao_rows
        ]

        extras = {}
        try:
            if tabela_existe(cursor, "cisp_cheques_sem_fundo"):
                cursor.execute("SELECT COUNT(*) AS total FROM cisp_cheques_sem_fundo WHERE raiz = %s", (raiz,))
                r = cursor.fetchone()
                extras["tot_cheques_sem_fundo"] = r.get("total") if isinstance(r, dict) else (r[0] if r else None)
        except Exception:
            extras["tot_cheques_sem_fundo"] = None
        try:
            if tabela_existe(cursor, "cisp_titulos_protesto"):
                cursor.execute("SELECT COUNT(*) AS total FROM cisp_titulos_protesto WHERE raiz = %s", (raiz,))
                r = cursor.fetchone()
                extras["tot_titulos_protesto"] = r.get("total") if isinstance(r, dict) else (r[0] if r else None)
        except Exception:
            extras["tot_titulos_protesto"] = None

        # Ratings e segmentos positivos direto do payload já obtido
        ratings_list = []
        positiva_segmentos = []
        if payload_cisp:
            if isinstance(payload_cisp.get("ratings"), list):
                ratings_list = payload_cisp.get("ratings") or []
            if isinstance(payload_cisp.get("positivaSegmentos"), list):
                positiva_segmentos = payload_cisp.get("positivaSegmentos") or []

        return jsonify({
            "success": True,
            "raiz": raiz,
            "principal": principal,
            "restritivas": restritivas,
            "alertas": alertas,
            "consultas_mensais": consultas_mensais,
            "associadas_consultaram": associadas_consultaram,
            "associadas_nao_concederam": associadas_nao_concederam,
            "ratings": ratings_list,
            "positivaSegmentos": positiva_segmentos,
            "extras": extras,
        })
    except Exception as e:
        return jsonify({"success": False, "erro": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/api/debug/<raiz>')
def debug_raiz(raiz):
    conn = None
    cur = None
    try:
        conn = conectar_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM cisp_avaliacao_analitica WHERE raiz = %s LIMIT 1", (raiz,))
        row = cur.fetchone()
        cols = obter_colunas(cur, "cisp_avaliacao_analitica")
        res = {
            "schema": "scsilverlayer",
            "tabela": "cisp_avaliacao_analitica",
            "existe_registro": bool(row),
            "chaves": list(row.keys()) if row else [],
            "colunas": cols,
        }
        return jsonify(res)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/api/debug-data')
def debug_data():
    try:
        import json
        with open(os.path.join(os.path.dirname(__file__), "data.json"), "r", encoding="utf-8") as f:
            payload = json.load(f)
        def keys(d):
            return sorted(list(d.keys())) if isinstance(d, dict) else None
        out = {
            "top": keys(payload),
            "cliente": keys(payload.get("cliente", {})),
            "informacaoSuporte": keys(payload.get("informacaoSuporte", {})),
            "receitaFederal": keys(payload.get("receitaFederal", {})),
            "ratings0": keys((payload.get("ratings") or [{}])[0]),
            "restritivas0": keys((payload.get("restritivas") or [{}])[0]),
            "alertas0": keys((payload.get("alertas") or [{}])[0]),
            "associadaConsultaUltimos30Dias0": keys((payload.get("associadaConsultaUltimos30Dias") or [{}])[0]),
            "associadaNaoConcederamCredito0": keys((payload.get("associadaNaoConcederamCredito") or [{}])[0]),
            "quantidadeConsultasUltimos12Meses0": keys((payload.get("quantidadeConsultasUltimos12Meses") or [{}])[0]),
            "chequeSemfundo0": keys((payload.get("chequeSemfundo") or [{}])[0]),
            "sintegras0": keys((payload.get("sintegras") or [{}])[0]),
            "indicadores0": keys((payload.get("indicadores") or [{}])[0]),
        }
        return jsonify(out)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/sincronizar/<raiz>')
def sincronizar(raiz):
    """
    1. Busca dados na API CISP
    2. Insere no PostgreSQL
    3. Retorna sucesso/erro
    """
    try:
        dados = buscar_api_cisp(raiz)
        if not dados:
            return jsonify({'success': False, 'raiz': raiz, 'mensagem': 'Raiz não encontrada na API CISP'}), 404

        sucesso = inserir_no_postgres(raiz, dados)
        if sucesso:
            return jsonify({'success': True, 'raiz': raiz, 'mensagem': 'Dados sincronizados com sucesso', 'timestamp': str(datetime.now())})
        return jsonify({'success': False, 'raiz': raiz, 'mensagem': 'Erro ao inserir dados no PostgreSQL'}), 500
    except Exception as e:
        return jsonify({'success': False, 'raiz': raiz, 'mensagem': str(e)}), 500


@app.route('/api/health')
def health():
    try:
        conn = conectar_db()
        conn.close()
        return jsonify({'status': 'ok', 'database': 'conectado', 'timestamp': str(datetime.now())})
    except Exception as e:
        return jsonify({'status': 'erro', 'database': 'desconectado', 'erro': str(e)}), 500


# =============================================================================
# UI
# =============================================================================
@app.route('/')
def pagina():
    return render_template("index.html")


if __name__ == '__main__':
    print("🚀 Portal CISP rodando em: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)