

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# Imports do Airflow
from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator
from airflow.operators.bash import BashOperator
from airflow.models import Variable
from airflow.exceptions import AirflowSkipException, AirflowFailException
from airflow.utils.dates import days_ago

# Imports dos módulos auxiliares - ajustado para estrutura Docker
import sys

# Adicionar diretorio scripts ao path para imports
sys.path.append('/opt/airflow/scripts')

# Importar módulos diretamente após adicionar ao path
from cliente_google_maps import ClienteGoogleMapsMock, ConfiguracaoAPI
from controle_incremental import (
    GerenciadorArmazenamento, 
    ConsumidorKafkaBairros, 
    ControladorIncremental
)
from verificacao_qualidade import VerificadorIntegridade

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurações padrão da DAG
CONFIGURACOES_PADRAO = {
    'owner': 'engenharia-dados',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'catchup': False
}

# Configurações específicas do projeto - ajustado para Docker
CONFIGURACOES_PROJETO = {
    'diretorio_dados': '/opt/airflow/raw_data',
    'url_mock_api': Variable.get('MOCK_API_URL', default_var='https://google-maps-mock.proxy.beeceptor.com'),
    'kafka_servers': Variable.get('KAFKA_SERVERS', default_var='kafka:29092').split(','),
    'topico_kafka': Variable.get('KAFKA_TOPIC', default_var='bairros_sp'),
    'tipo_armazenamento': Variable.get('STORAGE_TYPE', default_var='s3'),
    'quota_minima': int(Variable.get('QUOTA_MINIMA', default_var='100')),
    'timeout_kafka': int(Variable.get('KAFKA_TIMEOUT', default_var='30'))
}

def obter_configuracao_api() -> ConfiguracaoAPI:
    """
    Obtém configuração da API a partir das variáveis do Airflow
    
    Returns:
        Configuração da API
    """
    return ConfiguracaoAPI(
        url_base=CONFIGURACOES_PROJETO['url_mock_api'],
        timeout=30,
        max_tentativas=5,
        backoff_inicial=2.0,
        backoff_maximo=60.0,
        quota_minima=CONFIGURACOES_PROJETO['quota_minima']
    )

def obter_configuracao_kafka() -> Dict:
    """
    Obtém configuração do Kafka a partir das variáveis do Airflow
    
    Returns:
        Configuração do Kafka
    """
    return {
        'bootstrap_servers': CONFIGURACOES_PROJETO['kafka_servers'],
        'topico': CONFIGURACOES_PROJETO['topico_kafka'],
        'grupo_consumidor': 'dag_coleta_google_maps',
        'timeout': CONFIGURACOES_PROJETO['timeout_kafka']
    }

def obter_configuracao_armazenamento() -> Dict:
    """
    Obtém configuração do armazenamento a partir das variáveis do Airflow
    
    Returns:
        Configuração do armazenamento
    """
    config = {
        'tipo': CONFIGURACOES_PROJETO['tipo_armazenamento']
    }
    
    # Se for S3/MinIO, adiciona configurações específicas
    if config['tipo'] == 's3':
        config['s3'] = {
            'endpoint_url': Variable.get('S3_ENDPOINT_URL', default_var='http://minio:9000'),
            'access_key': Variable.get('S3_ACCESS_KEY', default_var='minio'),
            'secret_key': Variable.get('S3_SECRET_KEY', default_var='minio123'),
            'bucket_name': Variable.get('S3_BUCKET_NAME', default_var='datalake')
        }
    
    return config

def task_verificar_quota(**context) -> bool:
    """
    Task para verificar se há quota suficiente para executar a coleta
    
    Returns:
        True se há quota suficiente, False caso contrário
    """
    logger.info("=== INICIANDO VERIFICAÇÃO DE QUOTA ===")
    
    try:
        # Inicializa cliente da API
        config_api = obter_configuracao_api()
        cliente = ClienteGoogleMapsMock(config_api)
        
        # Verifica quota
        tem_quota, quota_atual = cliente.verificar_quota()
        
        # Armazena informações no XCom para outras tasks
        context['task_instance'].xcom_push(key='quota_inicial', value=quota_atual)
        context['task_instance'].xcom_push(key='tem_quota_suficiente', value=tem_quota)
        
        if not tem_quota:
            logger.warning(f"Quota insuficiente: {quota_atual} (mínimo: {config_api.quota_minima})")
            logger.info("Execução será cancelada e reagendada")
            return False
        
        logger.info(f"Quota suficiente: {quota_atual} (mínimo: {config_api.quota_minima})")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao verificar quota: {e}")
        raise AirflowFailException(f"Falha na verificação de quota: {e}")

def task_obter_proximo_bairro_sequencial(**context) -> str:
    """
    Task para obter o próximo bairro da lista sequencial
    
    Returns:
        Nome do bairro a ser processado
    """
    logger.info("=== INICIANDO OBTENÇÃO SEQUENCIAL DE BAIRRO ===")
    
    try:
        # Inicializa componentes
        config_armazenamento = obter_configuracao_armazenamento()
        
        if config_armazenamento['tipo'] == 's3':
            gerenciador = GerenciadorArmazenamento(True, config_armazenamento.get('s3'))
        else:
            gerenciador = GerenciadorArmazenamento(False)
        
        # Importar controlador sequencial
        from controle_sequencial_bairros import ControladorSequencialBairros
        controlador_sequencial = ControladorSequencialBairros(gerenciador)
        
        # Obtém próximo bairro para processar na sequência
        bairro = controlador_sequencial.obter_bairro_atual_para_processar()
        
        if not bairro:
            logger.info("Todos os bairros da lista sequencial foram processados!")
            raise AirflowSkipException("Lista de bairros sequencial completa")
        
        # Armazena apenas o bairro no XCom (objetos Python não são serializáveis)
        context['task_instance'].xcom_push(key='bairro_atual', value=bairro)
        
        # Obtém e exibe estatísticas de progresso
        estatisticas = controlador_sequencial.obter_estatisticas_progresso()
        logger.info(f"Progresso atual: {estatisticas['progresso_geral']['percentual_concluido']}% concluído")
        logger.info(f"Bairro selecionado: {bairro} (posição {estatisticas['progresso_geral']['bairro_atual_index'] + 1} de {estatisticas['progresso_geral']['total_bairros']})")
        
        # Enviar bairro para o Kafka para manter integração
        config_kafka = obter_configuracao_kafka()
        produtor_kafka = ConsumidorKafkaBairros(config_kafka)
        if produtor_kafka.conectar():
            # Produzir mensagem com o bairro atual
            dados_bairro = {
                'bairro': bairro,
                'timestamp': datetime.now().isoformat(),
                'origem': 'sequencial',
                'progresso': estatisticas['progresso_geral']
            }
            success = produtor_kafka.producer.send(config_kafka.get('topico', 'bairros_sp'), 
                                                  value=dados_bairro)
            logger.info(f"Bairro {bairro} enviado para Kafka: {success}")
            produtor_kafka.fechar_conexoes()
        
        return bairro
        
    except AirflowSkipException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter próximo bairro sequencial: {e}")
        raise AirflowFailException(f"Falha na obtenção sequencial: {e}")

def task_verificar_processamento_incremental(**context) -> bool:
    """
    Task para verificar se o bairro já foi processado hoje
    
    Returns:
        True se deve prosseguir, False se já foi processado
    """
    logger.info("=== VERIFICANDO PROCESSAMENTO INCREMENTAL ===")
    
    try:
        # Obtém bairro do XCom (retorno da task anterior)
        bairro = context['task_instance'].xcom_pull(task_ids='obter_proximo_bairro_sequencial')
        
        if not bairro:
            logger.error("Bairro não encontrado no XCom")
            raise AirflowFailException("Bairro não disponível para verificação")
        
        # Inicializa gerenciador de armazenamento
        config_armazenamento = obter_configuracao_armazenamento()
        
        if config_armazenamento['tipo'] == 's3':
            gerenciador = GerenciadorArmazenamento(True, config_armazenamento.get('s3'))
        else:
            gerenciador = GerenciadorArmazenamento(False)
        
        # Verifica se já foi processado
        ja_processado = gerenciador.verificar_bairro_processado_hoje(bairro)
        
        if ja_processado:
            logger.info(f"Bairro {bairro} já foi processado hoje - pulando")
            raise AirflowSkipException(f"Bairro {bairro} já processado hoje")
        
        logger.info(f"Bairro {bairro} não foi processado hoje - prosseguindo")
        return True
        
    except AirflowSkipException:
        raise
    except Exception as e:
        logger.error(f"Erro na verificação incremental: {e}")
        raise AirflowFailException(f"Falha na verificação incremental: {e}")

def task_coletar_dados_google_maps(**context) -> dict:
    """
    Task principal para coletar dados de até 2 agências não visitadas do bairro atual
    com até 10 comentários por agência
    
    Returns:
        Dicionário com dados coletados e estatísticas
    """
    logger.info("=== INICIANDO COLETA SEQUENCIAL DE DADOS GOOGLE MAPS ===")
    
    try:
        # Recupera bairro e controlador do XCom
        bairro = context['task_instance'].xcom_pull(
            task_ids='obter_proximo_bairro_sequencial', 
            key='bairro_atual'
        )
        
        if not bairro:
            logger.error("Bairro não encontrado no XCom")
            raise AirflowFailException("Bairro não disponível")
        
        logger.info(f"Processando bairro sequencialmente: {bairro}")
        
        # Reinicializar controlador sequencial
        config_armazenamento = obter_configuracao_armazenamento()
        if config_armazenamento['tipo'] == 's3':
            gerenciador = GerenciadorArmazenamento(True, config_armazenamento.get('s3'))
        else:
            gerenciador = GerenciadorArmazenamento(False)
        
        from controle_sequencial_bairros import ControladorSequencialBairros
        controlador_sequencial = ControladorSequencialBairros(gerenciador)
        
        # Verificar se há agências pendentes no bairro atual
        if not controlador_sequencial.tem_agencias_pendentes(bairro):
            logger.info(f"Bairro {bairro} já foi completamente processado. Avançando para próximo.")
            controlador_sequencial.avancar_para_proximo_bairro()
            raise AirflowSkipException(f"Bairro {bairro} já processado completamente")
        
        # Configurações (usando classes já importadas no topo da DAG)
        config_google = ConfiguracaoAPI.from_env_vars()
        
        # Cliente Google Maps Mock
        cliente = ClienteGoogleMapsMock(config_google)
        
        # Primeiro: Buscar todas as agências disponíveis do bairro na API
        logger.info(f"Buscando agências Santander no bairro {bairro}")
        agencias_disponiveis = cliente.buscar_lugares_texto("Santander", bairro)
        
        if not agencias_disponiveis:
            logger.info(f"Nenhuma agência encontrada para o bairro {bairro}")
            return {
                'bairro': bairro,
                'agencias_coletadas': [],
                'total_agencias': 0,
                'total_reviews': 0,
                'data_coleta': datetime.now().isoformat(),
                'tipo_execucao': 'sequencial'
            }
        
        logger.info(f"Encontradas {len(agencias_disponiveis)} agências disponíveis em {bairro}")
        
        # Segundo: Selecionar até 2 agências não consultadas
        agencias_para_processar = controlador_sequencial.obter_agencias_para_processar(bairro, agencias_disponiveis)
        
        if not agencias_para_processar:
            logger.info(f"Todas as agências de {bairro} já foram processadas")
            return {
                'bairro': bairro,
                'agencias_coletadas': [],
                'total_agencias': len(agencias_disponiveis),
                'total_reviews': 0,
                'data_coleta': datetime.now().isoformat(),
                'tipo_execucao': 'sequencial',
                'todas_processadas': True
            }
        
        logger.info(f"Selecionadas {len(agencias_para_processar)} agências para processar no bairro {bairro}")
        
        # Inicializar metadados da execução
        inicio_execucao = datetime.now()
        metadados = {
            'bairro': bairro,
            'data_coleta': inicio_execucao.strftime('%Y-%m-%d'),
            'timestamp_inicio': inicio_execucao.isoformat(),
            'query_usada': f"Santander {bairro} São Paulo",
            'quota_inicial': cliente.quota_atual,
            'agencias_disponiveis': len(agencias_disponiveis),
            'agencias_selecionadas': len(agencias_para_processar),
            'tipo_execucao': 'sequencial',
            'erros': []
        }
        
        # Processar cada agência selecionada
        agencias_detalhadas = []
        total_reviews = 0
        
        for idx, agencia in enumerate(agencias_para_processar):
            try:
                place_id = agencia.get('place_id')
                if not place_id:
                    logger.warning(f"Agência sem place_id: {agencia.get('name', 'N/A')}")
                    continue
                
                logger.info(f"Processando agência: {agencia.get('name', 'N/A')} - {place_id}")
                
                # Obter detalhes da agência
                detalhes = cliente.obter_detalhes_lugar(place_id)
                if detalhes:
                    agencia.update(detalhes)
                
                # Obter reviews da agência (sem parâmetro limite)
                reviews = cliente.obter_reviews_lugar(place_id)
                if reviews:
                    # Limitar a 10 reviews
                    reviews_limitadas = reviews[:10]
                    agencia['reviews'] = reviews_limitadas
                    total_reviews += len(reviews_limitadas)
                    logger.info(f"Coletadas {len(reviews_limitadas)} reviews para {agencia.get('name', 'N/A')}")
                else:
                    agencia['reviews'] = []
                
                # Adicionar metadados da coleta
                agencia.update({
                    'bairro_pesquisado': bairro,
                    'timestamp_coleta': datetime.now().isoformat(),
                    'data_coleta': datetime.now().strftime('%Y-%m-%d'),
                    'tipo_execucao': 'sequencial',
                    'reviews_coletadas': len(reviews_limitadas) if reviews else 0
                })
                
                agencias_detalhadas.append(agencia)
                
                logger.info(f"Agência processada: {agencia.get('name', 'N/A')}")
                
            except Exception as e:
                erro_msg = f"Erro ao processar agência {idx+1}: {e}"
                logger.error(erro_msg)
                metadados['erros'].append(erro_msg)
        
        # Finaliza metadados
        fim_execucao = datetime.now()
        metadados['quantidade_agencias'] = len(agencias_detalhadas)
        metadados['quota_final'] = cliente.quota_atual
        metadados['tempo_execucao_segundos'] = (fim_execucao - inicio_execucao).total_seconds()
        
        logger.info(f"Coleta finalizada: {len(agencias_detalhadas)} agências processadas")
        logger.info(f"Quota utilizada: {metadados['quota_inicial'] - metadados['quota_final']}")
        
        # CRÍTICO: Marcar agências como consultadas no arquivo de controle
        total_comentarios = sum(len(ag.get('reviews', [])) for ag in agencias_detalhadas)
        if agencias_detalhadas:
            try:
                controlador_sequencial.marcar_agencias_como_consultadas(bairro, agencias_detalhadas, total_comentarios)
                logger.info(f"✅ Marcadas {len(agencias_detalhadas)} agências como consultadas no arquivo de controle")
                logger.info(f"✅ Total de comentários registrados: {total_comentarios}")
            except Exception as e:
                logger.error(f"❌ Erro ao marcar agências como consultadas: {e}")
        
        # Armazena dados no XCom
        dados_completos = {
            'metadados': metadados,
            'agencias': agencias_detalhadas
        }
        
        context['task_instance'].xcom_push(key='dados_coletados', value=dados_completos)
        
        return dados_completos
        
    except Exception as e:
        logger.error(f"Erro na coleta de dados: {e}")
        raise AirflowFailException(f"Falha na coleta de dados: {e}")

def task_salvar_dados(**context) -> bool:
    """
    Task para salvar os dados coletados
    
    Returns:
        True se salvou com sucesso
    """
    logger.info("=== SALVANDO DADOS COLETADOS ===")
    
    try:
        # Obtém dados do XCom
        bairro = context['task_instance'].xcom_pull(key='bairro_atual', task_ids='obter_proximo_bairro_sequencial')
        dados_completos = context['task_instance'].xcom_pull(key='dados_coletados', task_ids='coletar_dados_google_maps')
        
        if not bairro or not dados_completos:
            raise AirflowFailException("Dados não disponíveis para salvamento")
        
        # Inicializa gerenciador de armazenamento
        config_armazenamento = obter_configuracao_armazenamento()
        
        if config_armazenamento['tipo'] == 's3':
            gerenciador = GerenciadorArmazenamento(True, config_armazenamento.get('s3'))
        else:
            gerenciador = GerenciadorArmazenamento(False)
        
        # Salva dados com nova arquitetura Data Lake (arquivos separados por execução)
        dados_para_salvar = {
            'agencias': dados_completos['agencias'], 
            'metadados': dados_completos['metadados']
        }
        sucesso = gerenciador.salvar_dados_localmente(dados_para_salvar, bairro)
        
        if not sucesso:
            raise AirflowFailException("Falha ao salvar dados")
        
        logger.info(f"Dados do bairro {bairro} salvos com sucesso")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao salvar dados: {e}")
        raise AirflowFailException(f"Falha no salvamento: {e}")

def task_verificar_qualidade_dados(**context) -> Dict:
    """
    Task para verificar a qualidade dos dados coletados
    
    Returns:
        Resultado da verificação de qualidade
    """
    logger.info("=== VERIFICANDO QUALIDADE DOS DADOS ===")
    
    try:
        # Obtém dados do XCom
        dados_completos = context['task_instance'].xcom_pull(task_ids='coletar_dados_google_maps')
        bairro_nome = context['task_instance'].xcom_pull(key='bairro_atual', task_ids='obter_proximo_bairro_sequencial')
        
        if not dados_completos:
            raise AirflowFailException("Dados não disponíveis para verificação")
        
        if not bairro_nome:
            raise AirflowFailException("Nome do bairro não disponível")
        
        # Importa e inicializa verificador
        from verificacao_qualidade import ValidadorQualidadeDados
        
        validador = ValidadorQualidadeDados()
        # Para validação em memória, criar um método alternativo ou salvar temporariamente
        # Por simplicidade, vamos criar uma validação direta aqui
        resultado = validador._validar_dados_em_memoria(dados_completos, bairro_nome)
        
        # Log dos resultados
        logger.info(f"Score de qualidade: {resultado.score_qualidade:.2f}")
        logger.info(f"Dados válidos: {resultado.valido}")
        
        if resultado.problemas_encontrados:
            logger.warning("Problemas encontrados:")
            for problema in resultado.problemas_encontrados:
                logger.warning(f"  - {problema}")
        
        if resultado.recomendacoes:
            logger.info("Recomendações:")
            for recomendacao in resultado.recomendacoes:
                logger.info(f"  - {recomendacao}")
        
        # Armazena resultado no XCom
        resultado_dict = {
            'valido': resultado.valido,
            'score_qualidade': resultado.score_qualidade,
            'problemas': resultado.problemas_encontrados,
            'metricas': resultado.metricas,
            'recomendacoes': resultado.recomendacoes
        }
        
        context['task_instance'].xcom_push(key='resultado_qualidade', value=resultado_dict)
        
        return resultado_dict
        
    except Exception as e:
        logger.error(f"Erro na verificação de qualidade: {e}")
        raise AirflowFailException(f"Falha na verificação de qualidade: {e}")

def task_verificar_integridade_completa(**context) -> Dict:
    """
    Task para verificar integridade de todos os dados do dia (executada apenas se todos os bairros foram processados)
    
    Returns:
        Relatório de integridade completa
    """
    logger.info("=== VERIFICANDO INTEGRIDADE COMPLETA ===")
    
    try:
        # Inicializa verificador
        verificador = VerificadorIntegridade(CONFIGURACOES_PROJETO['diretorio_dados'])
        
        # Executa verificação completa
        relatorio = verificador.verificar_integridade_completa()
        
        # Gera relatório textual
        relatorio_texto = verificador.gerar_relatorio_qualidade()
        
        logger.info("Relatório de integridade:")
        logger.info(relatorio_texto)
        
        # Armazena no XCom
        context['task_instance'].xcom_push(key='relatorio_integridade', value=relatorio)
        
        return relatorio
        
    except Exception as e:
        logger.error(f"Erro na verificação de integridade: {e}")
        raise AirflowFailException(f"Falha na verificação de integridade: {e}")

# Definição da DAG
dag = DAG(
    'dag_coleta_google_maps',
    default_args=CONFIGURACOES_PADRAO,
    description='Coleta incremental de dados de agências Santander via mock Google Maps API',
    schedule_interval=None,  # Execução manual apenas
    max_active_runs=1,  # Apenas uma execução por vez
    tags=['google-maps', 'santander', 'coleta-dados', 'kafka']
)

# Definição das tasks
task_verificacao_quota = ShortCircuitOperator(
    task_id='verificar_quota',
    python_callable=task_verificar_quota,
    dag=dag,
    doc_md="""
    ## Verificação de Quota
    
    Verifica se há quota suficiente na API para executar a coleta.
    Se a quota for insuficiente (< 100), a execução é cancelada e reagendada.
    """
)

task_obter_bairros = PythonOperator(
    task_id='obter_proximo_bairro_sequencial',
    python_callable=task_obter_proximo_bairro_sequencial,
    dag=dag,
    doc_md="""
    ## Obtenção Sequencial de Bairros
    
    Obtém próximo bairro da lista sequencial para processar.
    Utiliza o controlador sequencial para controle de progresso.
    """
)

task_verificacao_incremental = ShortCircuitOperator(
    task_id='verificar_processamento_incremental',
    python_callable=task_verificar_processamento_incremental,
    dag=dag,
    doc_md="""
    ## Verificação Incremental
    
    Verifica se o bairro já foi processado hoje.
    Se já foi processado, pula a execução para evitar duplicação.
    """
)

task_coleta_dados = PythonOperator(
    task_id='coletar_dados_google_maps',
    python_callable=task_coletar_dados_google_maps,
    dag=dag,
    doc_md="""
    ## Coleta Sequencial de Dados
    
    Task principal que coleta dados sequencialmente das agências Santander:
    1. Processa até 2 agências não visitadas do bairro atual
    2. Coleta até 10 reviews por agência
    3. Marca agências como processadas
    4. Avança para próximo bairro quando necessário
    """
)

task_salvamento = PythonOperator(
    task_id='salvar_dados',
    python_callable=task_salvar_dados,
    dag=dag,
    doc_md="""
    ## Salvamento de Dados
    
    Salva os dados coletados no armazenamento configurado (local ou S3/MinIO).
    Organiza os dados por data e bairro.
    """
)

task_verificacao_qualidade = PythonOperator(
    task_id='verificar_qualidade_dados',
    python_callable=task_verificar_qualidade_dados,
    dag=dag,
    doc_md="""
    ## Verificação de Qualidade
    
    Valida a qualidade dos dados coletados:
    - Completude dos campos obrigatórios
    - Qualidade dos ratings e coordenadas
    - Eficiência do uso de quota
    """
)

task_integridade_completa = PythonOperator(
    task_id='verificar_integridade_completa',
    python_callable=task_verificar_integridade_completa,
    dag=dag,
    trigger_rule='none_failed',  # Executa mesmo se algumas tasks anteriores falharam
    doc_md="""
    ## Verificação de Integridade Completa
    
    Executa verificação de integridade de todos os dados coletados no dia.
    Gera relatório completo de qualidade e estatísticas.
    """
)

# Definição das dependências
task_verificacao_quota >> task_obter_bairros >> task_verificacao_incremental
task_verificacao_incremental >> task_coleta_dados >> task_salvamento
task_salvamento >> task_verificacao_qualidade >> task_integridade_completa

# Documentação da DAG
dag.doc_md = """
# DAG de Coleta Sequencial de Dados - Google Maps API Mock

Esta DAG implementa um pipeline completo para coleta sequencial de dados de agências Santander 
na cidade de São Paulo, processando uma lista fixa de bairros em ordem sequencial.

## Características Principais:

- **Processamento Sequencial**: Percorre lista fixa de bairros em ordem sequencial
- **Controle de Progresso**: Persiste progresso de bairros e agências processadas
- **Execução Limitada**: Processa até 2 agências não visitadas por execução
- **Reviews Limitadas**: Coleta até 10 reviews por agência (máximo 20 por execução)
- **Integração Kafka**: Mantém Kafka para coordenação e monitoramento
- **Verificação de Qualidade**: Valida dados coletados e gera métricas de qualidade
- **Tolerância a Falhas**: Retry automático e tratamento de erros

## Monitoramento:

A DAG gera logs detalhados e métricas de qualidade para monitoramento:
- Quota utilizada por execução
- Número de agências coletadas por bairro
- Score de qualidade dos dados
- Tempo de execução por bairro
- Relatórios de integridade diários
"""

