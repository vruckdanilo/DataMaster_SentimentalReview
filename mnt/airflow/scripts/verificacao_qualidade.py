

import json
import logging
from datetime import datetime, date
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from dataclasses import dataclass

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ResultadoValidacao:
    """Resultado de uma validação de qualidade"""
    
    def __init__(self, bairro: str, data_validacao, score_qualidade: float, 
                 total_agencias: int, problemas_encontrados: List[str], 
                 metricas_detalhadas: Dict, recomendacoes: List[str], 
                 aprovado: bool):
        self.bairro = bairro
        self.data_validacao = data_validacao
        self.score_qualidade = score_qualidade
        self.total_agencias = total_agencias
        self.problemas_encontrados = problemas_encontrados
        self.metricas_detalhadas = metricas_detalhadas
        self.recomendacoes = recomendacoes
        self.aprovado = aprovado
        # Compatibilidade com código antigo
        self.valido = aprovado
        self.metricas = metricas_detalhadas

class ValidadorQualidadeDados:
    """
    Valida a qualidade dos dados coletados por bairro
    """
    
    def __init__(self, configuracao: Optional[Dict] = None, usar_minio: bool = True):
        self.configuracao = configuracao or {}
        self.diretorio_base = "/opt/airflow/raw_data"
        self.usar_minio = usar_minio
        self.bucket_minio = 'datalake'
        
        # Configurar MinIO se solicitado
        if usar_minio:
            self._configurar_minio()
        
        # Critérios mínimos de qualidade ajustados para Santander
        self.criterios_minimos = {
            'min_agencias_por_bairro': self.configuracao.get('min_agencias', 1),
            'max_agencias_por_bairro': self.configuracao.get('max_agencias', 50),  # Limite razoável
            'campos_obrigatorios_agencia': [
                'place_id', 'name', 'formatted_address', 
                'geometry', 'types'
            ],
            'campos_desejados_agencia': [
                'rating', 'user_ratings_total', 'business_status'
            ],
            'rating_minimo': self.configuracao.get('rating_minimo', 1.0),
            'rating_maximo': self.configuracao.get('rating_maximo', 5.0),
            'tipos_validos': ['bank', 'establishment', 'finance', 'point_of_interest'],
            'min_score_qualidade': 0.7,
            'max_agencias_sem_rating': 0.3,  # 30% máximo sem rating
            'min_reviews_por_agencia': 0  # Mínimo de reviews (pode ser 0)
        }
        
        self.cliente_minio = None
    
    def _contar_agencias_unicas(self, agencias):
        """Conta agências únicas baseado no place_id para evitar duplicatas"""
        place_ids_unicos = set()
        for agencia in agencias:
            place_id = agencia.get('place_id')
            if place_id:
                place_ids_unicos.add(place_id)
        return len(place_ids_unicos)
    
    def _calcular_metricas_unicas(self, agencias):
        """Calcula métricas únicas (agências e reviews) baseado no place_id"""
        place_ids_dados = {}
        
        for agencia in agencias:
            place_id = agencia.get('place_id')
            if place_id and place_id not in place_ids_dados:
                place_ids_dados[place_id] = {
                    'reviews': agencia.get('user_ratings_total', 0) or 0,
                    'rating': agencia.get('rating', 0) or 0
                }
        
        return {
            'total_agencias': len(place_ids_dados),
            'total_reviews': sum(d['reviews'] for d in place_ids_dados.values()),
            'total_registros': len(agencias),
            'duplicatas_detectadas': len(agencias) - len(place_ids_dados)
        }
        
    def _configurar_minio(self):
        """Configura cliente MinIO para acesso aos dados"""
        try:
            from minio import Minio
            
            # Configuração padrão para MinIO no Docker
            self.cliente_minio = Minio(
                endpoint='minio:9000',
                access_key='minio',
                secret_key='minio123',
                secure=False
            )
            
            # Verificar se bucket existe
            if not self.cliente_minio.bucket_exists(self.bucket_minio):
                logger.warning(f"Bucket {self.bucket_minio} não encontrado no MinIO")
                
        except ImportError:
            logger.warning("Biblioteca minio não encontrada. Usando verificação local apenas.")
            self.usar_minio = False
            self.cliente_minio = None
        except Exception as e:
            logger.error(f"Erro ao configurar MinIO: {e}")
            self.usar_minio = False
            self.cliente_minio = None
    
    def _carregar_dados_arquivo(self, caminho_arquivo: str) -> Dict:
        """Carrega dados do arquivo local ou MinIO"""
        try:
            # Tentar carregar do sistema local primeiro
            with open(caminho_arquivo, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            if self.usar_minio and self.cliente_minio:
                try:
                    # Tentar carregar do MinIO
                    response = self.cliente_minio.get_object(self.bucket_minio, caminho_arquivo)
                    return json.loads(response.data.decode('utf-8'))
                except Exception as e:
                    logger.error(f"Erro ao carregar do MinIO: {e}")
                    raise FileNotFoundError(f"Arquivo não encontrado: {caminho_arquivo}")
            else:
                raise
        except Exception as e:
            logger.error(f"Erro ao carregar arquivo {caminho_arquivo}: {e}")
            raise

    def validar_dados_bairro(self, caminho_arquivo: str, bairro: str) -> ResultadoValidacao:
        """
        Valida os dados coletados para um bairro específico
        """
        try:
            # Carregar dados do arquivo local ou MinIO
            dados = self._carregar_dados_arquivo(caminho_arquivo)
            
            problemas = []
            metricas = {}
            recomendacoes = []
            
            # Extrai dados
            metadados = dados.get('metadados', {})
            agencias = dados.get('agencias', [])
            
            # Verificações básicas
            metricas['total_agencias'] = len(agencias)
            metricas['bairro'] = bairro
            metricas['data_coleta'] = metadados.get('data_coleta')
            
            # Valida quantidade mínima de agências
            if len(agencias) < self.criterios_minimos['min_agencias_por_bairro']:
                problemas.append(f"Menos de {self.criterios_minimos['min_agencias_por_bairro']} agências encontradas")
            
            # Valida quantidade máxima (pode indicar dados incorretos)
            if len(agencias) > self.criterios_minimos['max_agencias_por_bairro']:
                problemas.append(f"Muitas agências encontradas ({len(agencias)}), verificar filtros")
            
            # Validar cada agência
            agencias_com_rating = 0
            agencias_sem_coordenadas = 0
            
            for i, agencia in enumerate(agencias):
                # Campos obrigatórios
                for campo in self.criterios_minimos['campos_obrigatorios_agencia']:
                    if campo not in agencia or not agencia[campo]:
                        problemas.append(f"Agência {i+1}: campo '{campo}' ausente ou vazio")
                
                # Rating se disponível
                if 'rating' in agencia and agencia['rating']:
                    agencias_com_rating += 1
                    rating = agencia['rating']
                    if rating < self.criterios_minimos['rating_minimo'] or rating > self.criterios_minimos['rating_maximo']:
                        problemas.append(f"Agência {i+1}: rating inválido ({rating})")
                
                # Coordenadas
                geometry = agencia.get('geometry', {})
                location = geometry.get('location', {})
                if not location.get('lat') or not location.get('lng'):
                    agencias_sem_coordenadas += 1
            
            # Métricas de qualidade
            metricas['agencias_com_rating'] = agencias_com_rating
            metricas['agencias_sem_coordenadas'] = agencias_sem_coordenadas
            metricas['percentual_com_rating'] = (agencias_com_rating / len(agencias)) * 100 if agencias else 0
            
            # Calcular score de qualidade
            score_qualidade = self._calcular_score_qualidade(metricas, problemas)
            metricas['score_qualidade'] = score_qualidade
            
            # Gerar recomendações
            if metricas['percentual_com_rating'] < 50:
                recomendacoes.append("Poucas agências com rating - verificar filtros de busca")
            
            if agencias_sem_coordenadas > len(agencias) * 0.1:
                recomendacoes.append("Muitas agências sem coordenadas - verificar geocoding")
            
            return ResultadoValidacao(
                bairro=bairro,
                data_validacao=datetime.now(),
                score_qualidade=score_qualidade,
                total_agencias=len(agencias),
                problemas_encontrados=problemas,
                metricas_detalhadas=metricas,
                recomendacoes=recomendacoes,
                aprovado=score_qualidade >= self.criterios_minimos['min_score_qualidade']
            )
            
        except Exception as e:
            logger.error(f"Erro ao validar dados do bairro {bairro}: {e}")
            return ResultadoValidacao(
                bairro=bairro,
                data_validacao=datetime.now(),
                score_qualidade=0.0,
                total_agencias=0,
                problemas_encontrados=[f"Erro na validação: {str(e)}"],
                metricas_detalhadas={},
                recomendacoes=["Verificar estrutura do arquivo de dados"],
                aprovado=False
            )
    
    def _validar_dados_em_memoria(self, dados_completos: Dict, bairro: str) -> ResultadoValidacao:
        """
        Valida dados que estão em memória ao invés de arquivo
        
        Args:
            dados_completos: Dados já carregados em memória
            bairro: Nome do bairro sendo validado
            
        Returns:
            ResultadoValidacao com o resultado da validação
        """
        try:
            problemas = []
            metricas = {}
            recomendacoes = []
            
            # Extrai dados
            metadados = dados_completos.get('metadados', {})
            agencias = dados_completos.get('agencias', [])
            
            # Verificações básicas
            metricas['total_agencias'] = len(agencias)
            metricas['bairro'] = bairro
            metricas['data_coleta'] = metadados.get('data_coleta')
            
            # Valida quantidade mínima de agências
            if len(agencias) < self.criterios_minimos['min_agencias_por_bairro']:
                problemas.append(f"Menos de {self.criterios_minimos['min_agencias_por_bairro']} agências encontradas")
            
            # Valida quantidade máxima (pode indicar dados incorretos)
            if len(agencias) > self.criterios_minimos['max_agencias_por_bairro']:
                problemas.append(f"Muitas agências encontradas ({len(agencias)}), verificar filtros")
            
            # Validar cada agência
            agencias_com_rating = 0
            agencias_sem_coordenadas = 0
            
            for i, agencia in enumerate(agencias):
                # Campos obrigatórios
                for campo in self.criterios_minimos['campos_obrigatorios_agencia']:
                    if campo not in agencia or not agencia[campo]:
                        problemas.append(f"Agência {i+1}: campo '{campo}' ausente ou vazio")
                
                # Rating se disponível
                if 'rating' in agencia and agencia['rating']:
                    agencias_com_rating += 1
                    rating = agencia['rating']
                    if rating < self.criterios_minimos['rating_minimo'] or rating > self.criterios_minimos['rating_maximo']:
                        problemas.append(f"Agência {i+1}: rating inválido ({rating})")
                
                # Coordenadas
                geometry = agencia.get('geometry', {})
                location = geometry.get('location', {})
                if not location.get('lat') or not location.get('lng'):
                    agencias_sem_coordenadas += 1
            
            # Métricas de qualidade
            metricas['agencias_com_rating'] = agencias_com_rating
            metricas['agencias_sem_coordenadas'] = agencias_sem_coordenadas
            metricas['percentual_com_rating'] = (agencias_com_rating / len(agencias)) * 100 if agencias else 0
            
            # Calcular score de qualidade
            score_qualidade = self._calcular_score_qualidade(metricas, problemas)
            metricas['score_qualidade'] = score_qualidade
            
            # Gerar recomendações
            if metricas['percentual_com_rating'] < 50:
                recomendacoes.append("Poucas agências com rating - verificar filtros de busca")
            
            if agencias_sem_coordenadas > len(agencias) * 0.1:
                recomendacoes.append("Muitas agências sem coordenadas - verificar geocoding")
            
            return ResultadoValidacao(
                bairro=bairro,
                data_validacao=datetime.now(),
                score_qualidade=score_qualidade,
                total_agencias=len(agencias),
                problemas_encontrados=problemas,
                metricas_detalhadas=metricas,
                recomendacoes=recomendacoes,
                aprovado=score_qualidade >= self.criterios_minimos['min_score_qualidade']
            )
            
        except Exception as e:
            logger.error(f"Erro ao validar dados do bairro {bairro}: {e}")
            return ResultadoValidacao(
                bairro=bairro,
                data_validacao=datetime.now(),
                score_qualidade=0.0,
                total_agencias=0,
                problemas_encontrados=[f"Erro na validação: {str(e)}"],
                metricas_detalhadas={},
                recomendacoes=["Verificar estrutura dos dados"],
                aprovado=False
            )
    
    def _calcular_score_qualidade(self, metricas: Dict, problemas: List[str]) -> float:
        """
        Calcula score de qualidade baseado nas métricas
        
        Args:
            metricas: Métricas coletadas
            problemas: Lista de problemas encontrados
            
        Returns:
            Score de 0.0 a 1.0
        """
        score_base = 1.0
        
        # Penalizar por cada problema encontrado
        if problemas:
            # Problemas críticos reduzem mais o score
            problemas_criticos = [
                p for p in problemas 
                if any(keyword in p.lower() for keyword in ['ausente', 'vazio', 'inválido', 'erro'])
            ]
            score_base -= len(problemas_criticos) * 0.15  # -15% por problema crítico
            score_base -= (len(problemas) - len(problemas_criticos)) * 0.05  # -5% por problema menor
        
        # Bonificar por métricas positivas
        if 'percentual_com_rating' in metricas:
            percentual_rating = metricas['percentual_com_rating'] / 100
            score_base += percentual_rating * 0.2  # Até +20% se todos têm rating
        
        # Penalizar se muitas agências sem coordenadas
        if 'agencias_sem_coordenadas' in metricas and 'total_agencias' in metricas:
            if metricas['total_agencias'] > 0:
                percentual_sem_coord = metricas['agencias_sem_coordenadas'] / metricas['total_agencias']
                if percentual_sem_coord > 0.1:  # Se mais de 10% sem coordenadas
                    score_base -= percentual_sem_coord * 0.3
        
        # Garantir que o score fique entre 0.0 e 1.0
        return max(0.0, min(1.0, score_base))
    
    def _gerar_recomendacoes(self, metricas: Dict, problemas: List[str]) -> List[str]:
        """
        Gera recomendações baseadas nas métricas e problemas
        
        Args:
            metricas: Métricas coletadas
            problemas: Lista de problemas encontrados
            
        Returns:
            Lista de recomendações
        """
        recomendacoes = []
        
        # Recomendações baseadas no percentual de rating
        if 'percentual_com_rating' in metricas:
            percentual = metricas['percentual_com_rating']
            if percentual < 30:
                recomendacoes.append("Muito poucas agências com rating - verificar filtros de busca e tipos")
            elif percentual < 50:
                recomendacoes.append("Poucas agências com rating - considerar ajustar query de busca")
        
        # Recomendações baseadas em coordenadas
        if 'agencias_sem_coordenadas' in metricas and 'total_agencias' in metricas:
            total = metricas.get('total_agencias', 0)
            sem_coord = metricas.get('agencias_sem_coordenadas', 0)
            if total > 0 and (sem_coord / total) > 0.1:
                recomendacoes.append("Muitas agências sem coordenadas - verificar processo de geocoding")
        
        # Recomendações baseadas no número total de agências
        total_agencias = metricas.get('total_agencias', 0)
        if total_agencias == 0:
            recomendacoes.append("Nenhuma agência encontrada - revisar query de busca e filtros")
        elif total_agencias > self.criterios_minimos['max_agencias_por_bairro']:
            recomendacoes.append("Muitas agências encontradas - refinar filtros para evitar resultados irrelevantes")
        
        # Recomendações baseadas em problemas específicos
        if problemas:
            campos_ausentes = [p for p in problemas if 'ausente' in p or 'vazio' in p]
            if campos_ausentes:
                recomendacoes.append("Campos obrigatórios ausentes - verificar mapeamento da API")
            
            ratings_invalidos = [p for p in problemas if 'rating inválido' in p]
            if ratings_invalidos:
                recomendacoes.append("Ratings inválidos detectados - verificar validação de dados")
        
        # Se nenhuma recomendação específica, dar recomendação padrão
        if not recomendacoes and metricas.get('score_qualidade', 0) < 0.8:
            recomendacoes.append("Revisar processo de coleta para melhorar qualidade dos dados")
        
        return recomendacoes

class VerificadorIntegridade:
    """
    Verificador de integridade para todos os dados coletados
    """
    
    def __init__(self, diretorio_dados: str = None):
        # Sempre usar MinIO, pois é onde os dados são salvos
        self.validador = ValidadorQualidadeDados(usar_minio=True)
        self.bucket_minio = 'datalake'
        self.prefixo_dados = 'landing/google_maps'
        
        # Configurar cliente MinIO
        from minio import Minio
        self.cliente_minio = Minio(
            'minio:9000',  # Nome do serviço Docker
            access_key='minio',
            secret_key='minio123',
            secure=False
        )
    
    def verificar_integridade_completa(self, data_verificacao: Optional[str] = None) -> Dict:
        """
        Verifica a integridade de todos os dados de uma data
        
        Args:
            data_verificacao: Data no formato YYYY-MM-DD (padrão: hoje)
            
        Returns:
            Relatório completo de integridade
        """
        if not data_verificacao:
            data_verificacao = date.today().strftime("%Y-%m-%d")
        
        # Buscar arquivos no MinIO
        prefixo_data = f"{self.prefixo_dados}/{data_verificacao}/"
        
        try:
            # Listar objetos no MinIO
            objetos = list(self.cliente_minio.list_objects(
                self.bucket_minio, 
                prefix=prefixo_data,
                recursive=False
            ))
            
            # Filtrar apenas arquivos JSON de bairros (excluir metadados)
            arquivos_bairros = [
                obj for obj in objetos 
                if obj.object_name.endswith('.json') and 'metadados_execucao' not in obj.object_name
            ]
            
            if not arquivos_bairros:
                return {
                    'data': data_verificacao,
                    'status': 'sem_dados',
                    'mensagem': f'Nenhum dado encontrado para {data_verificacao}',
                    'timestamp_verificacao': datetime.now().isoformat()
                }
                
        except Exception as e:
            return {
                'data': data_verificacao,
                'status': 'erro_acesso',
                'mensagem': f'Erro ao acessar dados no MinIO: {str(e)}',
                'timestamp_verificacao': datetime.now().isoformat()
            }
        
        resultados_bairros = []
        problemas_gerais = []
        metricas_gerais = {
            'total_bairros': len(arquivos_bairros),
            'bairros_validos': 0,
            'bairros_com_problemas': 0,
            'total_agencias': 0,
            'total_reviews': 0,
            'score_medio_qualidade': 0.0
        }
        
        # Verifica cada bairro
        for objeto in arquivos_bairros:
            try:
                # Ler arquivo do MinIO
                resposta = self.cliente_minio.get_object(self.bucket_minio, objeto.object_name)
                conteudo_json = resposta.read().decode('utf-8')
                dados_bairro = json.loads(conteudo_json)
                resposta.close()
                
                # Extrair nome do bairro do caminho do objeto
                nome_arquivo = objeto.object_name.split('/')[-1]  # Pega apenas o nome do arquivo
                nome_bairro = nome_arquivo.replace('.json', '').replace('_', ' ').title()
                
                # Usar dados já carregados ao invés de re-ler
                resultado = self.validador._validar_dados_em_memoria(dados_bairro, nome_bairro)
                
                bairro_info = {
                    'bairro': nome_bairro,
                    'arquivo': nome_arquivo,
                    'valido': resultado.valido,
                    'score_qualidade': resultado.score_qualidade,
                    'problemas': resultado.problemas_encontrados,
                    'metricas': resultado.metricas
                }
                
                resultados_bairros.append(bairro_info)
                
                # Atualiza métricas gerais
                if resultado.valido:
                    metricas_gerais['bairros_validos'] += 1
                else:
                    metricas_gerais['bairros_com_problemas'] += 1
                
                metricas_gerais['total_agencias'] += resultado.metricas.get('total_agencias', 0)
                metricas_gerais['total_reviews'] += resultado.metricas.get('total_reviews', 0)
                metricas_gerais['score_medio_qualidade'] += resultado.score_qualidade
                
            except Exception as e:
                nome_arquivo = objeto.object_name.split('/')[-1]
                problemas_gerais.append(f"Erro ao processar {nome_arquivo}: {e}")
                metricas_gerais['bairros_com_problemas'] += 1
        
        # Calcula médias
        if metricas_gerais['total_bairros'] > 0:
            metricas_gerais['score_medio_qualidade'] /= metricas_gerais['total_bairros']
            metricas_gerais['percentual_bairros_validos'] = metricas_gerais['bairros_validos'] / metricas_gerais['total_bairros']
            metricas_gerais['media_agencias_por_bairro'] = metricas_gerais['total_agencias'] / metricas_gerais['total_bairros']
        
        # Determina status geral
        if metricas_gerais['percentual_bairros_validos'] >= 0.9:
            status = 'excelente'
        elif metricas_gerais['percentual_bairros_validos'] >= 0.7:
            status = 'bom'
        elif metricas_gerais['percentual_bairros_validos'] >= 0.5:
            status = 'aceitavel'
        else:
            status = 'problematico'
        
        return {
            'data': data_verificacao,
            'status': status,
            'metricas_gerais': metricas_gerais,
            'resultados_por_bairro': resultados_bairros,
            'problemas_gerais': problemas_gerais,
            'timestamp_verificacao': datetime.now().isoformat()
        }
    
    def gerar_relatorio_qualidade(self, data_verificacao: Optional[str] = None) -> str:
        """
        Gera relatório textual de qualidade
        
        Args:
            data_verificacao: Data no formato YYYY-MM-DD (padrão: hoje)
            
        Returns:
            Relatório em formato texto
        """
        resultado = self.verificar_integridade_completa(data_verificacao)
        
        relatorio = []
        relatorio.append(f"=== RELATÓRIO DE QUALIDADE - {resultado['data']} ===")
        relatorio.append(f"Status Geral: {resultado['status'].upper()}")
        relatorio.append("")
        
        # Verificar se há dados coletados
        if resultado['status'] == 'sem_dados':
            relatorio.append("STATUS: Nenhum dado encontrado para esta data")
            relatorio.append(f"Mensagem: {resultado.get('mensagem', 'N/A')}")
            relatorio.append("")
            relatorio.append("RECOMENDAÇÕES:")
            relatorio.append("  • Verificar se a DAG foi executada para esta data")
            relatorio.append("  • Verificar se há dados no Kafka")
            relatorio.append("  • Verificar conectividade com o Google Maps API")
            return "\n".join(relatorio)
        
        # Se chegou aqui, há dados - processar métricas
        if 'metricas_gerais' not in resultado:
            relatorio.append("ERRO: Estrutura de dados inconsistente")
            relatorio.append(f"Chaves disponíveis: {list(resultado.keys())}")
            return "\n".join(relatorio)
        
        metricas = resultado['metricas_gerais']
        relatorio.append("MÉTRICAS GERAIS:")
        relatorio.append(f"  • Total de bairros: {metricas['total_bairros']}")
        relatorio.append(f"  • Bairros válidos: {metricas['bairros_validos']} ({metricas.get('percentual_bairros_validos', 0):.1%})")
        relatorio.append(f"  • Bairros com problemas: {metricas['bairros_com_problemas']}")
        relatorio.append(f"  • Total de agências: {metricas['total_agencias']}")
        relatorio.append(f"  • Média de agências por bairro: {metricas.get('media_agencias_por_bairro', 0):.1f}")
        relatorio.append(f"  • Total de reviews: {metricas['total_reviews']}")
        relatorio.append(f"  • Score médio de qualidade: {metricas['score_medio_qualidade']:.2f}")
        relatorio.append("")
        
        if resultado['problemas_gerais']:
            relatorio.append("PROBLEMAS GERAIS:")
            for problema in resultado['problemas_gerais']:
                relatorio.append(f"  ⚠️  {problema}")
            relatorio.append("")
        
        # Bairros com problemas
        bairros_problematicos = [b for b in resultado['resultados_por_bairro'] if not b['valido']]
        if bairros_problematicos:
            relatorio.append("BAIRROS COM PROBLEMAS:")
            for bairro in bairros_problematicos:
                relatorio.append(f"  📍 {bairro['bairro']} (Score: {bairro['score_qualidade']:.2f})")
                for problema in bairro['problemas']:
                    relatorio.append(f"     - {problema}")
            relatorio.append("")
        
        relatorio.append(f"Relatório gerado em: {resultado['timestamp_verificacao']}")
        
        return "\n".join(relatorio)

