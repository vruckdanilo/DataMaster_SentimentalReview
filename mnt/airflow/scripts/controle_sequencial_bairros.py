

import os
import json
import logging
from datetime import datetime, date
from typing import Optional, Dict, List, Set, Tuple
from pathlib import Path
from io import BytesIO

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ControladorSequencialBairros:
    """Controla o progresso sequencial de processamento de bairros e agências"""
    
    # Lista fixa de bairros de São Paulo para processamento sequencial
    BAIRROS_SAO_PAULO = [
        "Vila Madalena", "Pinheiros", "Itaim Bibi", "Moema", 
        "Vila Olímpia", "Brooklin", "Campo Belo", "Saúde",
        "Liberdade", "Bela Vista", "Consolação", "Higienópolis",
        "Jardins", "Cerqueira César", "Paraíso", "Vila Mariana",
        "Aclimação", "Cambuci", "Vila Prudente", "Ipiranga",
        "Santana", "Vila Guilherme", "Tucuruvi", "Mandaqui",
        "Casa Verde", "Limão", "Barra Funda", "Água Branca",
        "Perdizes", "Pompeia", "Lapa", "Vila Leopoldina",
        "Jaguaré", "Butantã", "Morumbi", "Vila Sônia",
        "Campo Limpo", "Capão Redondo", "Jardim São Luís", "M'Boi Mirim",
        "Cidade Ademar", "Pedreira", "Cidade Dutra", "Grajaú",
        "Jabaquara", "Cidade Monções", "Socorro", "Vila Andrade",
        "Santo Amaro", "Chácara Santo Antônio", "Granja Julieta", "Jurubatuba"
    ]
    
    def __init__(self, gerenciador_armazenamento):
        self.armazenamento = gerenciador_armazenamento
        self.arquivo_progresso = "controle_progresso_bairros.json"
        # Detectar ambiente correto (Docker vs Host)
        if hasattr(self.armazenamento, 'diretorio_local'):
            # Se estivermos no container Docker (existe /opt/airflow)
            if os.path.exists('/opt/airflow'):
                self.armazenamento.diretorio_local = '/opt/airflow/raw_data'
            else:
                # No ambiente host, usar caminho mapeado
                base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                self.armazenamento.diretorio_local = os.path.join(base_path, 'raw_data')
        self.progresso = self._carregar_progresso()
    
    def _carregar_progresso(self) -> Dict:
        """Carrega o progresso atual do processamento"""
        try:
            if self.armazenamento.usar_minio and self.armazenamento.cliente_minio:
                # Tentar carregar do MinIO
                try:
                    dados = self.armazenamento.cliente_minio.get_object(
                        self.armazenamento.bucket_minio, 
                        f"controle/{self.arquivo_progresso}"
                    )
                    conteudo = dados.read().decode('utf-8')
                    progresso = json.loads(conteudo)
                    logger.info("Progresso carregado do MinIO")
                    return progresso
                except Exception as e:
                    logger.debug(f"Arquivo de progresso não encontrado no MinIO: {e}")
            
            # Carregar do sistema local
            arquivo_local = os.path.join(self.armazenamento.diretorio_local, self.arquivo_progresso)
            if os.path.exists(arquivo_local):
                with open(arquivo_local, 'r', encoding='utf-8') as f:
                    progresso = json.load(f)
                    logger.info("Progresso carregado do arquivo local")
                    return progresso
                    
        except Exception as e:
            logger.warning(f"Erro ao carregar progresso: {e}")
        
        # Retorna progresso inicial se não encontrou arquivo
        return self._criar_progresso_inicial()
    
    def _criar_progresso_inicial(self) -> Dict:
        """Cria estrutura inicial de progresso"""
        return {
            "bairro_atual_index": 0,
            "data_ultima_atualizacao": datetime.now().isoformat(),
            "bairros_processados": {},
            "estatisticas": {
                "total_bairros": len(self.BAIRROS_SAO_PAULO),
                "total_agencias_processadas": 0,
                "total_comentarios_coletados": 0
            }
        }
    
    def _salvar_progresso(self):
        """Salva o progresso atual"""
        try:
            self.progresso["data_ultima_atualizacao"] = datetime.now().isoformat()
            conteudo_json = json.dumps(self.progresso, indent=2, ensure_ascii=False)
            
            if self.armazenamento.usar_minio and self.armazenamento.cliente_minio:
                # Salvar no MinIO
                dados = BytesIO(conteudo_json.encode('utf-8'))
                self.armazenamento.cliente_minio.put_object(
                    self.armazenamento.bucket_minio,
                    f"controle/{self.arquivo_progresso}",
                    dados,
                    len(conteudo_json.encode('utf-8')),
                    content_type='application/json'
                )
                logger.info("Progresso salvo no MinIO")
            
            # Sempre salvar localmente também
            os.makedirs(self.armazenamento.diretorio_local, exist_ok=True)
            arquivo_local = os.path.join(self.armazenamento.diretorio_local, self.arquivo_progresso)
            with open(arquivo_local, 'w', encoding='utf-8') as f:
                f.write(conteudo_json)
            logger.info("Progresso salvo localmente")
            
        except Exception as e:
            logger.error(f"Erro ao salvar progresso: {e}")
            raise
    
    def obter_bairro_atual_para_processar(self) -> Optional[str]:
        """
        Obtém o próximo bairro que deve ser processado
        
        Returns:
            Nome do bairro ou None se todos foram processados
        """
        # Verificar se já processamos todos os bairros
        if self.progresso["bairro_atual_index"] >= len(self.BAIRROS_SAO_PAULO):
            logger.info("Todos os bairros foram processados!")
            return None
        
        # Obter bairro atual
        bairro_atual = self.BAIRROS_SAO_PAULO[self.progresso["bairro_atual_index"]]
        
        # Verificar se o bairro atual ainda tem agências para processar
        if self._bairro_tem_agencias_pendentes(bairro_atual):
            return bairro_atual
        
        # Se não tem agências pendentes, avançar para próximo bairro
        return self._avancar_para_proximo_bairro()
    
    def _bairro_tem_agencias_pendentes(self, bairro: str) -> bool:
        """
        Verifica se o bairro ainda tem agências não consultadas
        
        Args:
            bairro: Nome do bairro a verificar
            
        Returns:
            True se ainda há agências não consultadas
        """
        dados_bairro = self.progresso["bairros_processados"].get(bairro, {})
        agencias_consultadas = set(dados_bairro.get("agencias_consultadas", []))
        agencias_disponiveis = set(dados_bairro.get("agencias_disponiveis", []))
        
        # Log para debug
        logger.info(f"Verificando bairro {bairro}: {len(agencias_consultadas)} consultadas, {len(agencias_disponiveis)} disponíveis")
        
        # Se não temos informações sobre agências disponíveis ainda, assumir que tem pendentes APENAS na primeira verificação
        if not agencias_disponiveis:
            # Se já consultamos algumas agências mas não temos lista disponível, algo está errado
            if agencias_consultadas:
                logger.warning(f"Bairro {bairro} tem agências consultadas mas não tem lista de disponíveis - forçando avanço")
                return False
            # Primeira vez processando este bairro - assumir que tem pendentes
            logger.info(f"Primeira vez processando bairro {bairro} - assumindo que tem agências pendentes")
            return True
        
        # Verificar se há agências não consultadas
        agencias_pendentes = agencias_disponiveis - agencias_consultadas
        tem_pendentes = len(agencias_pendentes) > 0
        
        logger.info(f"Bairro {bairro}: {len(agencias_pendentes)} agências pendentes")
        
        if not tem_pendentes:
            logger.info(f"Bairro {bairro} não tem mais agências pendentes - pronto para avançar")
        
        return tem_pendentes
    
    def tem_agencias_pendentes(self, bairro: str) -> bool:
        """Método público para verificar se bairro tem agências pendentes"""
        return self._bairro_tem_agencias_pendentes(bairro)
    
    def _avancar_para_proximo_bairro(self) -> Optional[str]:
        """
        Avança para o próximo bairro da lista
        
        Returns:
            Nome do próximo bairro ou None se chegou ao fim
        """
        self.progresso["bairro_atual_index"] += 1
        self._salvar_progresso()
        
        # Verificar se ainda há bairros para processar
        if self.progresso["bairro_atual_index"] >= len(self.BAIRROS_SAO_PAULO):
            logger.info("Chegamos ao final da lista de bairros!")
            return None
        
        # Retornar próximo bairro
        proximo_bairro = self.BAIRROS_SAO_PAULO[self.progresso["bairro_atual_index"]]
        logger.info(f"Avançando para o próximo bairro: {proximo_bairro}")
        return proximo_bairro
    
    def obter_agencias_para_processar(self, bairro: str, agencias_disponiveis: List[Dict]) -> List[Dict]:
        """
        Obtém até 2 agências não consultadas do bairro atual
        
        Args:
            bairro: Nome do bairro
            agencias_disponiveis: Lista de agências disponíveis no bairro
            
        Returns:
            Lista de até 2 agências para processar
        """
        # Atualizar lista de agências disponíveis no progresso
        self._atualizar_agencias_disponiveis(bairro, agencias_disponiveis)
        
        # Obter agências já consultadas
        dados_bairro = self.progresso["bairros_processados"].get(bairro, {})
        agencias_consultadas = set(dados_bairro.get("agencias_consultadas", []))
        
        # Filtrar agências não consultadas
        agencias_pendentes = []
        for agencia in agencias_disponiveis:
            place_id = agencia.get('place_id')
            if place_id and place_id not in agencias_consultadas:
                agencias_pendentes.append(agencia)
        
        # Retornar até 2 agências
        agencias_para_processar = agencias_pendentes[:2]
        logger.info(f"Selecionadas {len(agencias_para_processar)} agências para processar no bairro {bairro}")
        
        return agencias_para_processar
    
    def _atualizar_agencias_disponiveis(self, bairro: str, agencias_disponiveis: List[Dict]):
        """Atualiza a lista de agências disponíveis para o bairro"""
        if bairro not in self.progresso["bairros_processados"]:
            self.progresso["bairros_processados"][bairro] = {
                "agencias_disponiveis": [],
                "agencias_consultadas": [],
                "data_primeira_consulta": datetime.now().isoformat()
            }
        
        # Atualizar lista de place_ids disponíveis
        place_ids_disponiveis = [ag.get('place_id') for ag in agencias_disponiveis if ag.get('place_id')]
        self.progresso["bairros_processados"][bairro]["agencias_disponiveis"] = place_ids_disponiveis
        self.progresso["bairros_processados"][bairro]["total_agencias_encontradas"] = len(place_ids_disponiveis)
    
    def marcar_agencias_como_consultadas(self, bairro: str, agencias_processadas: List[Dict], total_comentarios: int):
        """
        Marca agências como consultadas e atualiza estatísticas
        
        Args:
            bairro: Nome do bairro
            agencias_processadas: Lista de agências que foram processadas
            total_comentarios: Total de comentários coletados
        """
        if bairro not in self.progresso["bairros_processados"]:
            self.progresso["bairros_processados"][bairro] = {
                "agencias_disponiveis": [],
                "agencias_consultadas": [],
                "data_primeira_consulta": datetime.now().isoformat()
            }
        
        # Adicionar place_ids das agências consultadas
        dados_bairro = self.progresso["bairros_processados"][bairro]
        agencias_consultadas = set(dados_bairro.get("agencias_consultadas", []))
        
        for agencia in agencias_processadas:
            place_id = agencia.get('place_id')
            if place_id:
                agencias_consultadas.add(place_id)
        
        # Atualizar progresso
        dados_bairro["agencias_consultadas"] = list(agencias_consultadas)
        dados_bairro["data_ultima_consulta"] = datetime.now().isoformat()
        
        # Atualizar estatísticas gerais
        self.progresso["estatisticas"]["total_agencias_processadas"] += len(agencias_processadas)
        self.progresso["estatisticas"]["total_comentarios_coletados"] += total_comentarios
        
        # Salvar progresso
        self._salvar_progresso()
        
        logger.info(f"Marcadas {len(agencias_processadas)} agências como consultadas no bairro {bairro}")
        logger.info(f"Total de comentários coletados nesta execução: {total_comentarios}")
    
    def obter_estatisticas_progresso(self) -> Dict:
        """
        Obtém estatísticas detalhadas do progresso
        
        Returns:
            Dicionário com estatísticas do progresso
        """
        bairro_atual_index = self.progresso["bairro_atual_index"]
        total_bairros = len(self.BAIRROS_SAO_PAULO)
        
        # Calcular estatísticas detalhadas
        estatisticas = {
            "progresso_geral": {
                "bairro_atual_index": bairro_atual_index,
                "total_bairros": total_bairros,
                "percentual_concluido": round((bairro_atual_index / total_bairros) * 100, 2),
                "bairros_restantes": total_bairros - bairro_atual_index
            },
            "bairro_atual": self.BAIRROS_SAO_PAULO[bairro_atual_index] if bairro_atual_index < total_bairros else "CONCLUÍDO",
            "estatisticas_coleta": self.progresso["estatisticas"],
            "data_ultima_atualizacao": self.progresso["data_ultima_atualizacao"]
        }
        
        return estatisticas
    
    def resetar_progresso(self):
        """Reseta o progresso para o início (usar com cuidado!)"""
        logger.warning("RESETANDO PROGRESSO - todos os dados de progresso serão perdidos!")
        self.progresso = self._criar_progresso_inicial()
        self._salvar_progresso()
        logger.info("Progresso resetado com sucesso")
