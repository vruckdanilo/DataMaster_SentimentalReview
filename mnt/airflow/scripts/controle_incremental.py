

import os
import json
import logging
from datetime import datetime, date
from typing import Optional, Dict, List, Set
from pathlib import Path
from io import BytesIO
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
import boto3
from botocore.exceptions import ClientError

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GerenciadorArmazenamento:
    """Gerencia operações de armazenamento local ou MinIO"""
    
    def __init__(self, usar_minio: bool = True, configuracao_minio: dict = None):
        self.usar_minio = usar_minio
        self.tipo = "s3" if usar_minio else "local"  # Definir tipo baseado no uso do MinIO
        self.diretorio_local = '/opt/airflow/raw_data'
        self.bucket_minio = 'datalake'
        
        # Configuração padrão para MinIO no Docker
        config_padrao = {
            'endpoint': 'minio:9000',
            'access_key': 'minio',
            'secret_key': 'minio123',
            'secure': False
        }
        
        if usar_minio:
            config_final = {**config_padrao, **(configuracao_minio or {})}
            self.cliente_minio = self._configurar_minio(config_final)
        else:
            self.cliente_minio = None
    
    def _configurar_minio(self, config: dict):
        """Configura cliente MinIO"""
        try:
            from minio import Minio
            return Minio(
                endpoint=config['endpoint'],
                access_key=config['access_key'],
                secret_key=config['secret_key'],
                secure=config.get('secure', False)
            )
        except ImportError:
            logger.warning("Biblioteca minio não encontrada. Usando armazenamento local.")
            self.usar_minio = False
            return None
        except Exception as e:
            logger.error(f"Erro ao configurar MinIO: {e}")
            self.usar_minio = False
            return None
    
    def verificar_bairro_processado_hoje(self, bairro: str) -> bool:
        """
        Verifica se um bairro já foi processado hoje
        
        Args:
            bairro: Nome do bairro a verificar
            
        Returns:
            True se já foi processado hoje, False caso contrário
        """
        data_hoje = date.today().strftime("%Y-%m-%d")
        nome_arquivo = f"agencias_{bairro.lower().replace(' ', '_')}.json"
        
        # Usar MinIO se disponível, senão local
        if self.usar_minio and self.cliente_minio:
            try:
                # Caminho no MinIO: landing/google_maps/YYYY-MM-DD/bairro.json
                objeto_path = f"landing/google_maps/{data_hoje}/{nome_arquivo}"
                
                # Verificar se objeto existe no bucket
                self.cliente_minio.stat_object(self.bucket_minio, objeto_path)
                logger.info(f"Bairro {bairro} já processado hoje (MinIO)")
                return True
                
            except Exception as e:
                logger.debug(f"Arquivo não encontrado no MinIO ou erro: {e}")
                # Continuar para verificação local
        
        # Verificação local (fallback ou preferência)
        caminho_arquivo = os.path.join(
            self.diretorio_local, 
            data_hoje, 
            nome_arquivo
        )
        existe_local = os.path.exists(caminho_arquivo)
        
        if existe_local:
            logger.info(f"Bairro {bairro} já processado hoje (local)")
        
        return existe_local
    
    def salvar_dados_bairro(self, bairro: str, dados: Dict, metadados: Dict) -> bool:
        """
        Salva os dados coletados de um bairro
        
        Args:
            bairro: Nome do bairro
            dados: Dados das agências coletadas
            metadados: Metadados da execução
            
        Returns:
            True se salvou com sucesso, False caso contrário
        """
        data_hoje = date.today().strftime("%Y-%m-%d")
        nome_arquivo = f"{bairro.lower().replace(' ', '_')}.json"
        
        dados_completos = {
            'metadados': metadados,
            'agencias': dados,
            'timestamp_salvamento': datetime.now().isoformat()
        }
        
        if self.tipo == "local":
            return self.salvar_dados_localmente(dados_completos, bairro)
        elif self.tipo == "s3":
            return self._salvar_s3(data_hoje, nome_arquivo, dados_completos)
        
        return False
    
    def salvar_dados_localmente(self, dados: Dict, bairro: str, run_id: str = None) -> bool:
        """
        Salva dados localmente com arquitetura Data Lake (arquivos separados por execução)
        
        Args:
            dados: Dados das agências coletadas
            bairro: Nome do bairro
            run_id: ID único da execução (opcional, será gerado se não fornecido)
            
        Returns:
            True se salvou com sucesso, False caso contrário
        """
        try:
            # Gerar run_id único se não fornecido
            if not run_id:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                run_id = f"exec_{timestamp}_{os.getpid()}"
            
            # Data Lake particionamento: /year=2025/month=07/day=01/bairro=vila_madalena/
            data_hoje = datetime.now()
            year = data_hoje.year
            month = data_hoje.month
            day = data_hoje.day
            
            # Estrutura de diretórios particionada
            diretorio_particionado = os.path.join(
                self.diretorio_local,
                f"year={year}",
                f"month={month:02d}", 
                f"day={day:02d}",
                f"bairro={bairro.lower().replace(' ', '_')}"
            )
            os.makedirs(diretorio_particionado, exist_ok=True)
            
            # Nome do arquivo com padrão Data Lake
            nome_arquivo = f"{bairro.lower().replace(' ', '_')}_{run_id}.json"
            caminho_arquivo = os.path.join(diretorio_particionado, nome_arquivo)
            
            # Estrutura de dados Data Lake com metadados ricos
            dados_datalake = {
                "execution_metadata": {
                    "run_id": run_id,
                    "execution_date": data_hoje.isoformat(),
                    "bairro": bairro,
                    "partition_info": {
                        "year": year,
                        "month": month,
                        "day": day
                    },
                    "data_quality": {
                        "total_agencias": len(dados.get('agencias', [])),
                        "total_reviews": sum(len(ag.get('reviews', [])) for ag in dados.get('agencias', [])),
                        "completeness_score": self._calcular_score_qualidade(dados)
                    },
                    "processing_info": {
                        "dag_execution": dados.get('metadados', {}),
                        "timestamp_inicio": dados.get('metadados', {}).get('timestamp_inicio'),
                        "tempo_execucao_segundos": dados.get('metadados', {}).get('tempo_execucao_segundos'),
                        "quota_utilizada": dados.get('metadados', {}).get('quota_final', 0) - dados.get('metadados', {}).get('quota_inicial', 0)
                    }
                },
                "raw_data": {
                    "agencias": dados.get('agencias', [])
                },
                "schema_version": "v1.0",
                "created_at": datetime.now().isoformat()
            }
            
            # Salvar arquivo único da execução
            with open(caminho_arquivo, 'w', encoding='utf-8') as f:
                json.dump(dados_datalake, f, ensure_ascii=False, indent=2)
            
            # Upload para MinIO usando método que funcionava antes
            if self.usar_minio:
                sucesso_minio = self._salvar_s3(datetime.now().strftime('%Y-%m-%d'), nome_arquivo, dados)
                if not sucesso_minio:
                    logger.warning("⚠️ Falha no upload MinIO, mas dados salvos localmente")
            
            logger.info(f"✅ Dados salvos com arquitetura Data Lake: {caminho_arquivo}")
            logger.info(f"📊 Run ID: {run_id}")
            logger.info(f"📈 Agências coletadas: {dados_datalake['execution_metadata']['data_quality']['total_agencias']}")
            logger.info(f"💬 Reviews coletadas: {dados_datalake['execution_metadata']['data_quality']['total_reviews']}")
            logger.info(f"⭐ Score qualidade: {dados_datalake['execution_metadata']['data_quality']['completeness_score']:.2f}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao salvar dados com arquitetura Data Lake: {e}")
            return False
    
    def _calcular_score_qualidade(self, dados: Dict) -> float:
        """
        Calcula score de qualidade dos dados coletados
        
        Args:
            dados: Dados das agências
            
        Returns:
            Score de 0.0 a 1.0 representando qualidade dos dados
        """
        try:
            agencias = dados.get('agencias', [])
            if not agencias:
                return 0.0
            
            total_pontos = 0
            max_pontos = 0
            
            for agencia in agencias:
                # Pontos por campos obrigatórios preenchidos
                if agencia.get('name'): total_pontos += 1
                if agencia.get('place_id'): total_pontos += 1
                if agencia.get('formatted_address'): total_pontos += 1
                if agencia.get('rating'): total_pontos += 1
                max_pontos += 4
                
                # Pontos por reviews de qualidade
                reviews = agencia.get('reviews', [])
                if reviews:
                    total_pontos += min(len(reviews), 2)  # Max 2 pontos por reviews
                max_pontos += 2
            
            return total_pontos / max_pontos if max_pontos > 0 else 0.0
            
        except Exception:
            return 0.0
    
    def _salvar_s3(self, data: str, nome_arquivo: str, dados: Dict) -> bool:
        """Salva dados no S3/MinIO com arquitetura Data Lake (arquivos separados por execução)"""
        if not self.cliente_minio:
            logger.error("Cliente MinIO não configurado")
            return False
        
        try:
            # Extrair bairro dos dados
            bairro = dados.get('metadados', {}).get('bairro', 'desconhecido')
            
            # Gerar run_id único
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            run_id = f"exec_{timestamp}_{os.getpid()}"
            
            # Data Lake particionamento no MinIO: landing/google_maps/year=2025/month=07/day=01/bairro=vila_madalena/
            data_hoje = datetime.now()
            year = data_hoje.year
            month = data_hoje.month
            day = data_hoje.day
            
            # Chave objeto particionada
            chave_objeto = f"landing/google_maps/year={year}/month={month:02d}/day={day:02d}/bairro={bairro.lower().replace(' ', '_')}/{bairro.lower().replace(' ', '_')}_{run_id}.json"
            
            # Estrutura de dados Data Lake com metadados ricos
            dados_datalake = {
                "execution_metadata": {
                    "run_id": run_id,
                    "execution_date": data_hoje.isoformat(),
                    "bairro": bairro,
                    "partition_info": {
                        "year": year,
                        "month": month,
                        "day": day
                    },
                    "data_quality": {
                        "total_agencias": len(dados.get('agencias', [])),
                        "total_reviews": sum(len(ag.get('reviews', [])) for ag in dados.get('agencias', [])),
                        "completeness_score": self._calcular_score_qualidade(dados)
                    },
                    "processing_info": {
                        "dag_execution": dados.get('metadados', {}),
                        "timestamp_inicio": dados.get('metadados', {}).get('timestamp_inicio'),
                        "tempo_execucao_segundos": dados.get('metadados', {}).get('tempo_execucao_segundos'),
                        "quota_utilizada": dados.get('metadados', {}).get('quota_final', 0) - dados.get('metadados', {}).get('quota_inicial', 0)
                    }
                },
                "raw_data": {
                    "agencias": dados.get('agencias', [])
                },
                "schema_version": "v1.0",
                "created_at": datetime.now().isoformat()
            }
            
            # Salvar arquivo único da execução no MinIO
            dados_json = json.dumps(dados_datalake, ensure_ascii=False, indent=2)
            
            self.cliente_minio.put_object(
                bucket_name=self.bucket_minio,
                object_name=chave_objeto,
                data=BytesIO(dados_json.encode('utf-8')),
                length=len(dados_json.encode('utf-8')),
                content_type='application/json'
            )
            
            logger.info(f"✅ Dados salvos com arquitetura Data Lake no MinIO: {chave_objeto}")
            logger.info(f"📊 Run ID: {run_id}")
            logger.info(f"📈 Agências coletadas: {dados_datalake['execution_metadata']['data_quality']['total_agencias']}")
            logger.info(f"💬 Reviews coletadas: {dados_datalake['execution_metadata']['data_quality']['total_reviews']}")
            logger.info(f"⭐ Score qualidade: {dados_datalake['execution_metadata']['data_quality']['completeness_score']:.2f}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao salvar dados no MinIO com arquitetura Data Lake: {e}")
            return False
    
    def listar_bairros_processados_hoje(self) -> Set[str]:
        """
        Lista todos os bairros já processados hoje
        
        Returns:
            Set com nomes dos bairros processados
        """
        data_hoje = date.today().strftime("%Y-%m-%d")
        
        if self.tipo == "local":
            return self._listar_local(data_hoje)
        elif self.tipo == "s3":
            return self._listar_s3(data_hoje)
        
        return set()
    
    def _listar_local(self, data: str) -> Set[str]:
        """Lista bairros processados localmente"""
        bairros = set()
        diretorio = Path(self.diretorio_base) / data
        
        if diretorio.exists():
            for arquivo in diretorio.glob("*.json"):
                if arquivo.name != "metadados_execucao.json":
                    bairro = arquivo.stem.replace('_', ' ').title()
                    bairros.add(bairro)
        
        return bairros
    
    def _listar_s3(self, data: str) -> Set[str]:
        """Lista bairros processados no S3"""
        bairros = set()
        
        if not self.s3_client:
            return bairros
        
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=f"{data}/"
            )
            
            for obj in response.get('Contents', []):
                nome_arquivo = obj['Key'].split('/')[-1]
                if nome_arquivo.endswith('.json') and nome_arquivo != 'metadados_execucao.json':
                    bairro = nome_arquivo[:-5].replace('_', ' ').title()
                    bairros.add(bairro)
        
        except Exception as e:
            logger.error(f"Erro ao listar bairros no S3: {e}")
        
        return bairros

class ConsumidorKafkaBairros:
    """
    Consumidor Kafka para obter bairros a serem processados
    """
    
    def __init__(self, config_kafka: Dict):
        self.config = config_kafka
        self.topico = config_kafka.get('topico', 'bairros_sp')
        self.grupo_consumidor = config_kafka.get('grupo_consumidor', 'dag_coleta_google_maps')
        
        self.consumer = None
        self.producer = None
    
    def conectar(self) -> bool:
        """
        Conecta ao Kafka
        
        Returns:
            True se conectou com sucesso, False caso contrário
        """
        try:
            self.consumer = KafkaConsumer(
                self.topico,
                bootstrap_servers=self.config.get('bootstrap_servers', ['localhost:9092']),
                group_id=self.grupo_consumidor,
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                value_deserializer=lambda x: json.loads(x.decode('utf-8')) if x else None,
                consumer_timeout_ms=30000  # 30 segundos timeout
            )
            
            self.producer = KafkaProducer(
                bootstrap_servers=self.config.get('bootstrap_servers', ['localhost:9092']),
                value_serializer=lambda x: json.dumps(x, ensure_ascii=False).encode('utf-8')
            )
            
            logger.info("Conectado ao Kafka com sucesso")
            return True
            
        except KafkaError as e:
            logger.error(f"Erro ao conectar ao Kafka: {e}")
            return False
    
    def consumir_proximo_bairro(self) -> Optional[str]:
        """
        Consome o próximo bairro da fila
        
        Returns:
            Nome do bairro ou None se não houver bairros disponíveis
        """
        if not self.consumer:
            logger.error("Consumer não está conectado")
            return None
        
        try:
            logger.info("Aguardando próximo bairro do Kafka...")
            
            for mensagem in self.consumer:
                if mensagem.value:
                    bairro = mensagem.value.get('bairro')
                    if bairro:
                        logger.info(f"Bairro recebido do Kafka: {bairro}")
                        return bairro
                    else:
                        logger.warning("Mensagem recebida sem campo 'bairro'")
                
                # Consome apenas uma mensagem por vez
                break
            
            logger.info("Nenhum bairro disponível no Kafka")
            return None
            
        except Exception as e:
            logger.error(f"Erro ao consumir bairro do Kafka: {e}")
            return None
    
    def rejeitar_bairro(self, bairro: str, motivo: str) -> bool:
        """
        Rejeita um bairro e o recoloca na fila para processamento posterior
        
        Args:
            bairro: Nome do bairro rejeitado
            motivo: Motivo da rejeição
            
        Returns:
            True se rejeitou com sucesso, False caso contrário
        """
        if not self.producer:
            logger.error("Producer não está conectado")
            return False
        
        try:
            mensagem = {
                'bairro': bairro,
                'timestamp_rejeicao': datetime.now().isoformat(),
                'motivo': motivo,
                'tentativas': 1
            }
            
            self.producer.send(self.topico, value=mensagem)
            self.producer.flush()
            
            logger.info(f"Bairro {bairro} rejeitado e recolocado na fila. Motivo: {motivo}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao rejeitar bairro: {e}")
            return False
    
    def fechar_conexoes(self):
        """Fecha as conexões com o Kafka"""
        try:
            if self.consumer:
                self.consumer.close()
            if self.producer:
                self.producer.close()
            logger.info("Conexões Kafka fechadas")
        except Exception as e:
            logger.error(f"Erro ao fechar conexões Kafka: {e}")

class ControladorIncremental:
    """
    Controlador principal para processamento incremental
    """
    
    def __init__(self, gerenciador_armazenamento: GerenciadorArmazenamento, 
                 consumidor_kafka: ConsumidorKafkaBairros):
        self.armazenamento = gerenciador_armazenamento
        self.kafka = consumidor_kafka
    
    def obter_proximo_bairro_para_processar(self) -> Optional[str]:
        """
        Obtém o próximo bairro que precisa ser processado
        
        Returns:
            Nome do bairro ou None se não houver bairros para processar
        """
        # Conecta ao Kafka se necessário
        if not self.kafka.consumer:
            if not self.kafka.conectar():
                logger.error("Não foi possível conectar ao Kafka")
                return None
        
        # Tenta consumir um bairro
        bairro = self.kafka.consumir_proximo_bairro()
        
        if not bairro:
            logger.info("Nenhum bairro disponível para processamento")
            return None
        
        # Verifica se o bairro já foi processado hoje
        if self.armazenamento.verificar_bairro_processado_hoje(bairro):
            logger.info(f"Bairro {bairro} já foi processado hoje, pulando...")
            return self.obter_proximo_bairro_para_processar()  # Recursão para próximo bairro
        
        return bairro
    
    def marcar_bairro_como_processado(self, bairro: str, dados_agencias: List[Dict], 
                                    metadados_execucao: Dict) -> bool:
        """
        Marca um bairro como processado salvando seus dados
        
        Args:
            bairro: Nome do bairro
            dados_agencias: Lista de dados das agências coletadas
            metadados_execucao: Metadados da execução
            
        Returns:
            True se salvou com sucesso, False caso contrário
        """
        return self.armazenamento.salvar_dados_bairro(bairro, dados_agencias, metadados_execucao)
    
    def obter_estatisticas_processamento(self) -> Dict:
        """
        Obtém estatísticas do processamento atual
        
        Returns:
            Dicionário com estatísticas
        """
        bairros_processados = self.armazenamento.listar_bairros_processados_hoje()
        
        return {
            'data': date.today().strftime("%Y-%m-%d"),
            'bairros_processados_hoje': len(bairros_processados),
            'lista_bairros_processados': list(bairros_processados),
            'timestamp': datetime.now().isoformat()
        }

