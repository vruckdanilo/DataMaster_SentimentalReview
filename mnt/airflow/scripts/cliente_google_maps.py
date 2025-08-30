

import requests
import time
import logging
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ConfiguracaoAPI:
    """Configurações para o cliente da API Mock Google Maps"""
    url_base: str = "http://google-maps-mock:3000"
    timeout: int = 30
    max_tentativas: int = 5
    backoff_inicial: float = 2.0
    backoff_maximo: float = 60.0
    quota_minima: int = 100
    
    @classmethod
    def from_env_vars(cls):
        """Cria configuração a partir de variáveis de ambiente"""
        return cls(
            url_base=os.getenv('MOCK_API_URL', 'http://google-maps-mock:3000'),
            timeout=int(os.getenv('API_TIMEOUT', '30')),
            max_tentativas=int(os.getenv('API_MAX_RETRIES', '5')),
            quota_minima=int(os.getenv('API_MIN_QUOTA', '100'))
        )

class ClienteGoogleMapsMock:
    """
    Cliente para interagir com o mock da API Google Maps
    Implementa controle de quota, rate limiting e backoff exponencial
    """
    
    def __init__(self, config: ConfiguracaoAPI):
        self.config = config
        self.quota_atual = 1000  # Quota simulada inicial
        self.session = requests.Session()
        
    def verificar_quota(self) -> Tuple[bool, int]:
        """
        Verifica se há quota suficiente para continuar
        
        Returns:
            Tuple[bool, int]: (tem_quota_suficiente, quota_atual)
        """
        try:
            # Simula verificação de quota via endpoint
            response = self._fazer_requisicao_com_retry(
                "GET", 
                f"{self.config.url_base}/quota/check"
            )
            
            if response and response.status_code == 200:
                data = response.json()
                self.quota_atual = data.get('remaining_quota', self.quota_atual)
            
            tem_quota = self.quota_atual >= self.config.quota_minima
            
            logger.info(f"Quota atual: {self.quota_atual}, Mínima necessária: {self.config.quota_minima}")
            
            return tem_quota, self.quota_atual
            
        except Exception as e:
            logger.error(f"Erro ao verificar quota: {e}")
            return False, 0
    
    def buscar_lugares_texto(self, query: str, bairro: str) -> Optional[List[Dict]]:
        """
        Busca lugares usando text search
        
        Args:
            query: Termo de busca (ex: "Santander")
            bairro: Nome do bairro para filtrar
            
        Returns:
            Lista de lugares encontrados ou None em caso de erro
        """
        query_completa = f"{query} {bairro} São Paulo"
        
        params = {
            'query': query_completa,
            'type': 'bank',
            'radius': 5000,
            'language': 'pt-BR'
        }
        
        logger.info(f"Buscando lugares com query: {query_completa}")
        
        response = self._fazer_requisicao_com_retry(
            "GET",
            f"{self.config.url_base}/textsearch",
            params={}
        )
        
        if response and response.status_code == 200:
            data = response.json()
            lugares = data.get('results', [])
            
            logger.info(f"Encontrados {len(lugares)} lugares para o bairro {bairro}")
            self._decrementar_quota()
            
            return lugares
        
        logger.error(f"Erro na busca de lugares para {bairro}")
        return None
    
    def obter_detalhes_lugar(self, place_id: str) -> Optional[Dict]:
        """
        Obtém detalhes completos de um lugar
        
        Args:
            place_id: ID do lugar no Google Maps
            
        Returns:
            Detalhes do lugar ou None em caso de erro
        """
        params = {
            'place_id': place_id,
            'fields': 'name,formatted_address,geometry,rating,user_ratings_total,opening_hours,phone_number'
        }
        
        logger.info(f"Obtendo detalhes para place_id: {place_id}")
        
        # Mapeamento de place_id para endpoint específico do JSON Server
        endpoint_key = f"place_details_{place_id}"
        
        response = self._fazer_requisicao_com_retry(
            "GET",
            f"{self.config.url_base}/{endpoint_key}",
            params={}
        )
        
        if response and response.status_code == 200:
            data = response.json()
            resultado = data.get('result', {})
            
            self._decrementar_quota()
            return resultado
        
        logger.error(f"Erro ao obter detalhes para place_id: {place_id}")
        return None
    
    def obter_reviews_lugar(self, place_id: str) -> Optional[List[Dict]]:
        """
        Obtém reviews de um lugar específico
        
        Args:
            place_id: ID do lugar no Google Maps
            
        Returns:
            Lista de reviews ou None em caso de erro
        """
        params = {
            'place_id': place_id,
            'fields': 'reviews'
        }
        
        logger.info(f"Obtendo reviews para place_id: {place_id}")
        
        # Mapeamento de place_id para endpoint específico do JSON Server
        endpoint_key = f"place_details_{place_id}"
        
        response = self._fazer_requisicao_com_retry(
            "GET",
            f"{self.config.url_base}/{endpoint_key}",
            params={}
        )
        
        if response and response.status_code == 200:
            data = response.json()
            resultado = data.get('result', {})
            reviews = resultado.get('reviews', [])
            
            self._decrementar_quota()
            return reviews
        
        logger.error(f"Erro ao obter reviews para place_id: {place_id}")
        return None
    
    def geocodificar_endereco(self, endereco: str) -> Optional[Dict]:
        """
        Geocodifica um endereço para obter coordenadas
        
        Args:
            endereco: Endereço a ser geocodificado
            
        Returns:
            Dados de geocodificação ou None em caso de erro
        """
        params = {
            'address': endereco,
            'language': 'pt-BR'
        }
        
        logger.info(f"Geocodificando endereço: {endereco}")
        
        response = self._fazer_requisicao_com_retry(
            "GET",
            f"{self.config.url_base}/geocode/json",
            params=params
        )
        
        if response and response.status_code == 200:
            data = response.json()
            resultados = data.get('results', [])
            
            if resultados:
                self._decrementar_quota()
                return resultados[0]
        
        logger.error(f"Erro ao geocodificar endereço: {endereco}")
        return None
    
    def _fazer_requisicao_com_retry(self, metodo: str, url: str, **kwargs) -> Optional[requests.Response]:
        """
        Faz requisição HTTP com retry e backoff exponencial
        
        Args:
            metodo: Método HTTP (GET, POST, etc.)
            url: URL da requisição
            **kwargs: Argumentos adicionais para requests
            
        Returns:
            Response object ou None em caso de falha
        """
        backoff = self.config.backoff_inicial
        
        for tentativa in range(self.config.max_tentativas):
            try:
                logger.debug(f"Tentativa {tentativa + 1} para {url}")
                
                response = self.session.request(
                    metodo, 
                    url, 
                    timeout=self.config.timeout,
                    **kwargs
                )
                
                # Verifica se a resposta indica limite de quota
                if response.status_code == 429:  # Too Many Requests
                    logger.warning("OVER_QUERY_LIMIT detectado, pausando por 60 segundos")
                    time.sleep(60)
                    continue
                
                # Se a resposta for bem-sucedida, retorna
                if response.status_code == 200:
                    return response
                
                # Para outros códigos de erro, loga e continua
                logger.warning(f"Código de status {response.status_code} para {url}")
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Erro na requisição (tentativa {tentativa + 1}): {e}")
            
            # Aplica backoff exponencial se não for a última tentativa
            if tentativa < self.config.max_tentativas - 1:
                logger.info(f"Aguardando {backoff} segundos antes da próxima tentativa")
                time.sleep(backoff)
                backoff = min(backoff * 2, self.config.backoff_maximo)
        
        logger.error(f"Falha após {self.config.max_tentativas} tentativas para {url}")
        return None
    
    def _decrementar_quota(self):
        """Decrementa a quota atual"""
        self.quota_atual = max(0, self.quota_atual - 1)
        logger.debug(f"Quota decrementada para: {self.quota_atual}")
    
    def obter_status_quota(self) -> Dict:
        """
        Retorna informações sobre o status atual da quota
        
        Returns:
            Dicionário com informações da quota
        """
        return {
            'quota_atual': self.quota_atual,
            'quota_minima': self.config.quota_minima,
            'pode_continuar': self.quota_atual >= self.config.quota_minima,
            'timestamp': datetime.now().isoformat()
        }

