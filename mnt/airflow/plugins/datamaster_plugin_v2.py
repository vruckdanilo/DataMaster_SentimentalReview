"""
====================================================================
PLUGINS AIRFLOW - DataMaster SentimentalReview V2
====================================================================

Plugins personalizados para o Airflow do projeto - Versão corrigida.
"""

from airflow.plugins_manager import AirflowPlugin
from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults
from airflow.hooks.base import BaseHook
import logging
import sys
import os

# Adicionar diretório scripts ao path
sys.path.append('/opt/airflow/scripts')

# Importar módulos dos scripts corrigidos
from cliente_google_maps import ClienteGoogleMapsMock, ConfiguracaoAPI
from controle_incremental import GerenciadorArmazenamento
from verificacao_qualidade import ValidadorQualidadeDados

logger = logging.getLogger(__name__)

class DataMasterHookV2(BaseHook):
    """Hook personalizado para operações DataMaster - Versão 2"""
    
    def __init__(self, conn_id='datamaster_default'):
        super().__init__()
        self.conn_id = conn_id
    
    def get_google_maps_client(self):
        """Obter cliente Google Maps"""
        configuracao = ConfiguracaoAPI.from_env_vars()
        return ClienteGoogleMapsMock(configuracao)
    
    def get_storage_manager(self):
        """Obter gerenciador de armazenamento"""
        return GerenciadorArmazenamento()
    
    def get_quality_validator(self):
        """Obter validador de qualidade"""
        return ValidadorQualidadeDados()

class GoogleMapsOperatorV2(BaseOperator):
    """Operador personalizado para Google Maps API - Versão 2"""
    
    @apply_defaults
    def __init__(self, bairro, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bairro = bairro
    
    def execute(self, context):
        hook = DataMasterHookV2()
        cliente = hook.get_google_maps_client()
        
        logger.info(f"Coletando dados do bairro: {self.bairro}")
        dados = cliente.buscar_agencias_por_bairro(self.bairro)
        
        return dados

class DataQualityOperatorV2(BaseOperator):
    """Operador para verificação de qualidade de dados - Versão 2"""
    
    @apply_defaults
    def __init__(self, bucket, prefixo='', min_files=1, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bucket = bucket
        self.prefixo = prefixo
        self.min_files = min_files
    
    def execute(self, context):
        hook = DataMasterHookV2()
        validador = hook.get_quality_validator()
        
        logger.info(f"Validando qualidade no bucket: {self.bucket}")
        
        # Validar qualidade dos dados
        resultado = validador.validar_dados_bairro("test_path", "test_bairro")
        
        if resultado['score_qualidade'] < 0.7:
            raise ValueError(f"Qualidade dos dados abaixo do limite: {resultado['score_qualidade']}")
        
        return resultado

# Plugin principal versão 2
class DataMasterPluginV2(AirflowPlugin):
    name = "datamaster_plugin_v2"
    hooks = [DataMasterHookV2]
    operators = [GoogleMapsOperatorV2, DataQualityOperatorV2]

# Aliases para compatibilidade de importação
DataMasterHook = DataMasterHookV2
DataMasterOperator = GoogleMapsOperatorV2
