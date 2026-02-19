import os
import requests
import psycopg2
from datetime import datetime
from requests.auth import HTTPBasicAuth

class CISPIntegration:
    def __init__(self):
        # Configuração da API
        self.api_base_url = "https://servicos.cisp.com.br/v1/avaliacao-analitica/raiz"
        self.api_username = os.environ.get('CISP_USERNAME')
        self.api_password = os.environ.get('CISP_PASSWORD')
        
        # Configuração do banco
        self.db_config = {
            'host': '127.0.0.1',
            'port': '5432',
            'database': 'dbDataLakePrd',
            'user': 'postgres',
            'password': os.environ.get('POSTGRES'),
            'options': '-c search_path=scsilverlayer'
        }
        
        self.conn = None
        self.cursor = None
    
    def conectar_db(self):
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.cursor = self.conn.cursor()
            print("✓ Conectado ao PostgreSQL (schema: scsilverlayer)")
            return True
        except Exception as e:
            print(f"✗ Erro ao conectar: {e}")
            return False
    
    def desconectar_db(self):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        print("✓ Desconectado do PostgreSQL")
    
    def obter_dados_api(self, raiz):
        try:
            url = f"{self.api_base_url}/{raiz}"
            print(f"📡 Buscando dados da API: {url}")
            
            response = requests.get(
                url,
                auth=HTTPBasicAuth(self.api_username, self.api_password),
                timeout=120
            )
            
            if response.status_code == 200:
                print("✓ Dados obtidos com sucesso!")
                return response.json()
            else:
                print(f"✗ Erro na API: Status {response.status_code}")
                return None
                
        except Exception as e:
            print(f"✗ Erro ao buscar dados: {e}")
            return None
    
    def converter_data(self, data_str):
        if not data_str or data_str == '':
            return None
        try:
            return datetime.strptime(data_str, '%Y-%m-%d').date()
        except:
            return None
    
    def inserir_avaliacao_analitica(self, raiz, dados):
        try:
            cliente = dados.get('cliente', {})
            info_sup = dados.get('informacaoSuporte', {})
            receita = dados.get('receitaFederal', {})

            sql = """
                INSERT INTO cisp_avaliacao_analitica (
                    raiz, cnpj, razao_social, nome_fantasia,
                    situacao_receita_federal,
                    tipo_logradouro, logradouro, numero, complemento,
                    bairro, municipio, uf, cep, telefone, email,
                    valor_total_debito_atual, qtd_associadas_debito_atual,
                    valor_total_debito_vencido_5dias, percentual_debito_vencido_5dias,
                    qtd_associadas_debito_vencido_5dias,
                    valor_total_debito_vencido_15dias, percentual_debito_vencido_15dias,
                    qtd_associadas_debito_vencido_15dias,
                    valor_total_debito_vencido_30dias, percentual_debito_vencido_30dias,
                    qtd_associadas_debito_vencido_30dias,
                    valor_total_limite_credito, qtd_associadas_limite_credito,
                    valor_total_maior_acumulo, qtd_associadas_maior_acumulo,
                    qtd_associadas_informacoes_negociais,
                    qtd_associadas_vendas_ultimos_2meses,
                    ultima_atualizacao
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s
                )
                ON CONFLICT (raiz) DO UPDATE SET
                    cnpj = EXCLUDED.cnpj,
                    razao_social = EXCLUDED.razao_social,
                    nome_fantasia = EXCLUDED.nome_fantasia,
                    situacao_receita_federal = EXCLUDED.situacao_receita_federal,
                    tipo_logradouro = EXCLUDED.tipo_logradouro,
                    logradouro = EXCLUDED.logradouro,
                    numero = EXCLUDED.numero,
                    complemento = EXCLUDED.complemento,
                    bairro = EXCLUDED.bairro,
                    municipio = EXCLUDED.municipio,
                    uf = EXCLUDED.uf,
                    cep = EXCLUDED.cep,
                    telefone = EXCLUDED.telefone,
                    email = EXCLUDED.email,
                    valor_total_debito_atual = EXCLUDED.valor_total_debito_atual,
                    qtd_associadas_debito_atual = EXCLUDED.qtd_associadas_debito_atual,
                    valor_total_debito_vencido_5dias = EXCLUDED.valor_total_debito_vencido_5dias,
                    percentual_debito_vencido_5dias = EXCLUDED.percentual_debito_vencido_5dias,
                    qtd_associadas_debito_vencido_5dias = EXCLUDED.qtd_associadas_debito_vencido_5dias,
                    valor_total_debito_vencido_15dias = EXCLUDED.valor_total_debito_vencido_15dias,
                    percentual_debito_vencido_15dias = EXCLUDED.percentual_debito_vencido_15dias,
                    qtd_associadas_debito_vencido_15dias = EXCLUDED.qtd_associadas_debito_vencido_15dias,
                    valor_total_debito_vencido_30dias = EXCLUDED.valor_total_debito_vencido_30dias,
                    percentual_debito_vencido_30dias = EXCLUDED.percentual_debito_vencido_30dias,
                    qtd_associadas_debito_vencido_30dias = EXCLUDED.qtd_associadas_debito_vencido_30dias,
                    valor_total_limite_credito = EXCLUDED.valor_total_limite_credito,
                    qtd_associadas_limite_credito = EXCLUDED.qtd_associadas_limite_credito,
                    valor_total_maior_acumulo = EXCLUDED.valor_total_maior_acumulo,
                    qtd_associadas_maior_acumulo = EXCLUDED.qtd_associadas_maior_acumulo,
                    qtd_associadas_informacoes_negociais = EXCLUDED.qtd_associadas_informacoes_negociais,
                    qtd_associadas_vendas_ultimos_2meses = EXCLUDED.qtd_associadas_vendas_ultimos_2meses,
                    ultima_atualizacao = EXCLUDED.ultima_atualizacao
            """

            self.cursor.execute(sql, (
                raiz,
                cliente.get('identificacaoCliente'),
                cliente.get('razaoSocial'),
                cliente.get('nomeFantasia'),
                receita.get('situacaoCadastral'),
                cliente.get('tipoLogradouro'),
                cliente.get('logradouro'),
                cliente.get('numero'),
                cliente.get('complemento'),
                cliente.get('bairro'),
                cliente.get('municipio'),
                cliente.get('uf'),
                cliente.get('cep'),
                cliente.get('telefone'),
                cliente.get('email'),
                info_sup.get('valorTotalDebitoAtual'),
                info_sup.get('quantidadeAssociadasDebitoAtual'),
                info_sup.get('valorTotalDebitoVencidoMais05Dias'),
                info_sup.get('percentualDebitoVencidoMais05Dias'),
                info_sup.get('quantidadeAssociadasDebitoVencidoMais05Dias'),
                info_sup.get('valorTotalDebitoVencidoMais15Dias'),
                info_sup.get('percentualDebitoVencidoMais15Dias'),
                info_sup.get('quantidadeAssociadasDebitoVencidoMais15Dias'),
                info_sup.get('valorTotalDebitoVencidoMais30Dias'),
                info_sup.get('percentualDebitoVencidoMais30Dias'),
                info_sup.get('quantidadeAssociadasDebitoVencidoMais30Dias'),
                info_sup.get('valorTotalLimiteCredito'),
                info_sup.get('quantidadeAssociadasLimiteCredito'),
                info_sup.get('valorTotalMaiorAcumulo'),
                info_sup.get('quantidadeAssociadasMaiorAcumulo'),
                info_sup.get('quantidadeAssociadasInformacoesNegociais'),
                info_sup.get('quantidadeAssociadasVendasUltimos2Meses'),
                datetime.now()
            ))
            
            self.conn.commit()
            print("✓ Tabela cisp_avaliacao_analitica atualizada")
            return True
            
        except Exception as e:
            print(f"✗ Erro ao inserir avaliacao_analitica: {e}")
            self.conn.rollback()
            return False
    
    def inserir_restritivas(self, raiz, dados):
        try:
            restritivas = dados.get('restritivas', [])
            
            if not restritivas:
                print("⚠ Nenhuma restritiva encontrada")
                return True
            
            # Deleta restritivas antigas
            self.cursor.execute("DELETE FROM cisp_restritivas WHERE raiz = %s", (raiz,))
            
            sql = """
                INSERT INTO cisp_restritivas (
                    raiz, codigo_associada, razao_social, codigo_primeira_restritiva,
                    descricao_primeira_restritiva, codigo_segunda_restritiva,
                    descricao_segunda_restritiva, data_ocorrencia, data_informacao
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            count = 0
            for rest in restritivas:
                # Manter timestamp em milissegundos (bigint)
                data_ocorrencia = rest.get('dataOcorrencia')

                self.cursor.execute(sql, (
                    raiz,
                    rest.get('codigoAssociada'),
                    rest.get('razaoSocial'),
                    rest.get('codigoPrimeiraRestritiva'),
                    rest.get('descricaoPrimeiraRestritiva'),
                    rest.get('codigoSegundaRestritiva'),
                    rest.get('descricaoSegundaRestritiva'),
                    data_ocorrencia,
                    self.converter_data(rest.get('dataInformacao'))
                ))
                count += 1
            
            self.conn.commit()
            print(f"✓ {count} restritivas inseridas")
            return True
            
        except Exception as e:
            print(f"✗ Erro ao inserir restritivas: {e}")
            self.conn.rollback()
            return False
    
    def inserir_alertas(self, raiz, dados):
        try:
            alertas = dados.get('alertas', [])

            if not alertas:
                print("⚠ Nenhum alerta encontrado")
                return True

            # Deleta alertas antigos
            self.cursor.execute("DELETE FROM cisp_alertas WHERE raiz = %s", (raiz,))

            sql = """
                INSERT INTO cisp_alertas (
                    raiz, identificacao_cliente, codigo_alerta, descricao_alerta,
                    associada_informante, razao_social
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """

            count = 0
            for alerta in alertas:
                self.cursor.execute(sql, (
                    raiz,
                    alerta.get('identificacaoCliente'),
                    alerta.get('codigoAlerta'),
                    alerta.get('descricaoAlerta'),
                    alerta.get('associadaInformante'),
                    alerta.get('razaoSocial')
                ))
                count += 1
            
            self.conn.commit()
            print(f"✓ {count} alertas inseridos")
            return True
            
        except Exception as e:
            print(f"✗ Erro ao inserir alertas: {e}")
            self.conn.rollback()
            return False
    
    def inserir_consultas_mensais(self, raiz, dados):
        try:
            consultas = dados.get('quantidadeConsultasUltimos12Meses', [])
            
            if not consultas:
                print("⚠ Nenhuma consulta mensal encontrada")
                return True
            
            # Deleta consultas antigas
            self.cursor.execute("DELETE FROM cisp_consultas_mensais WHERE raiz = %s", (raiz,))
            
            sql = """
                INSERT INTO cisp_consultas_mensais (
                    raiz, mes, quantidade_consultas
                ) VALUES (%s, %s, %s)
            """
            
            count = 0
            for consulta in consultas:
                self.cursor.execute(sql, (
                    raiz,
                    consulta.get('data'),
                    consulta.get('consultas')
                ))
                count += 1
            
            self.conn.commit()
            print(f"✓ {count} consultas mensais inseridas")
            return True
            
        except Exception as e:
            print(f"✗ Erro ao inserir consultas mensais: {e}")
            self.conn.rollback()
            return False
    
    def inserir_associadas_consultaram(self, raiz, dados):
        try:
            associadas = dados.get('associadaConsultaUltimos30Dias', [])
            
            if not associadas:
                print("⚠ Nenhuma associada consultou")
                return True
            
            # Deleta associadas antigas
            self.cursor.execute("DELETE FROM cisp_associadas_consultaram WHERE raiz = %s", (raiz,))
            
            sql = """
                INSERT INTO cisp_associadas_consultaram (
                    raiz, codigo_associada, razao_social
                ) VALUES (%s, %s, %s)
            """
            
            count = 0
            for associada in associadas:
                self.cursor.execute(sql, (
                    raiz,
                    associada.get('codigoAssociada'),
                    associada.get('razaoSocial')
                ))
                count += 1
            
            self.conn.commit()
            print(f"✓ {count} associadas que consultaram inseridas")
            return True
            
        except Exception as e:
            print(f"✗ Erro ao inserir associadas consultaram: {e}")
            self.conn.rollback()
            return False
    
    def inserir_associadas_nao_concederam(self, raiz, dados):
        try:
            associadas = dados.get('associadaNaoConcederamCredito', [])
            
            if not associadas:
                print("⚠ Nenhuma associada negou crédito")
                return True
            
            # Deleta associadas antigas
            self.cursor.execute("DELETE FROM cisp_associadas_nao_concederam_credito WHERE raiz = %s", (raiz,))
            
            sql = """
                INSERT INTO cisp_associadas_nao_concederam_credito (
                    raiz, codigo_associada, razao_social
                ) VALUES (%s, %s, %s)
            """
            
            count = 0
            for associada in associadas:
                self.cursor.execute(sql, (
                    raiz,
                    associada.get('codigoAssociada'),
                    associada.get('razaoSocial')
                ))
                count += 1
            
            self.conn.commit()
            print(f"✓ {count} associadas que negaram crédito inseridas")
            return True
            
        except Exception as e:
            print(f"✗ Erro ao inserir associadas não concederam: {e}")
            self.conn.rollback()
            return False
    
    def registrar_log(self, raiz, status, mensagem):
        try:
            sql = """
                INSERT INTO cisp_log_sincronizacao (
                    raiz, data_hora, status, mensagem
                ) VALUES (%s, %s, %s, %s)
            """
            
            self.cursor.execute(sql, (
                raiz,
                datetime.now(),
                status,
                mensagem
            ))
            
            self.conn.commit()
            
        except Exception as e:
            print(f"✗ Erro ao registrar log: {e}")
    
    def sincronizar_raiz(self, raiz):
        print(f"\n{'='*60}")
        print(f"SINCRONIZANDO RAIZ: {raiz}")
        print(f"{'='*60}")
        
        # Busca dados da API
        dados = self.obter_dados_api(raiz)
        
        if not dados:
            self.registrar_log(raiz, 'ERROR', 'Falha ao obter dados da API')
            return False
        
        # Insere em todas as tabelas
        sucesso = True
        
        sucesso &= self.inserir_avaliacao_analitica(raiz, dados)
        sucesso &= self.inserir_restritivas(raiz, dados)
        sucesso &= self.inserir_alertas(raiz, dados)
        sucesso &= self.inserir_consultas_mensais(raiz, dados)
        sucesso &= self.inserir_associadas_consultaram(raiz, dados)
        sucesso &= self.inserir_associadas_nao_concederam(raiz, dados)
        
        if sucesso:
            self.registrar_log(raiz, 'SUCCESS', 'Sincronização concluída com sucesso')
            print(f"✅ Raiz {raiz} sincronizada com sucesso em TODAS as tabelas!")
        else:
            self.registrar_log(raiz, 'ERROR', 'Erro em uma ou mais tabelas')
            print(f"⚠ Raiz {raiz} sincronizada com erros")
        
        return sucesso

# =============================================================================
# EXECUÇÃO PRINCIPAL
# =============================================================================

if __name__ == "__main__":
    # Lista de raízes para sincronizar
    raizes = [
        "37608058",  # Carrefour
        # Adicione mais raízes aqui
    ]
    
    integration = CISPIntegration()
    
    if not integration.conectar_db():
        print("✗ Não foi possível conectar ao banco de dados")
        exit(1)
    
    # Sincroniza cada raiz
    total_sucesso = 0
    total_erro = 0
    
    for raiz in raizes:
        if integration.sincronizar_raiz(raiz):
            total_sucesso += 1
        else:
            total_erro += 1
    
    integration.desconectar_db()
    
    # Resumo
    print(f"\n{'='*60}")
    print("RESUMO DA SINCRONIZAÇÃO")
    print(f"{'='*60}")
    print(f"✓ Sucesso: {total_sucesso}")
    print(f"✗ Erro: {total_erro}")
    print(f"Total: {len(raizes)}")
    print(f"{'='*60}\n")
