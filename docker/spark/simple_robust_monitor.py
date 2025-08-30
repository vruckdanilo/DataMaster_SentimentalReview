#!/usr/bin/env python3
import os
import json
import time
import subprocess
from pathlib import Path

# Diretórios
TRIGGER_DIR = '/opt/airflow/pyspark/triggers'
COMPLETED_DIR = '/opt/airflow/pyspark/completed'

def log_message(msg):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{timestamp}] {msg}', flush=True)

def process_trigger(trigger_file):
    try:
        log_message(f'Processando trigger: {trigger_file}')
        
        # Ler trigger
        with open(trigger_file, 'r') as f:
            trigger_data = json.load(f)
        
        job_type = trigger_data.get('job_type', 'unknown')
        log_message(f'Job type: {job_type}')
        
        # Simular processamento (sem executar Spark real por enquanto)
        log_message('Simulando execução do job...')
        time.sleep(2)
        
        # Criar arquivo completed
        trigger_name = os.path.basename(trigger_file).replace('.json', '')
        completed_file = f'{COMPLETED_DIR}/{trigger_name}_completed.json'
        
        completed_data = {
            'job_type': job_type,
            'status': 'success',
            'processed_at': int(time.time()),
            'message': 'Job processado com sucesso (simulado)'
        }
        
        with open(completed_file, 'w') as f:
            json.dump(completed_data, f, indent=2)
        
        # Remover trigger original
        os.remove(trigger_file)
        
        log_message(f'Trigger processado com sucesso: {completed_file}')
        return True
        
    except Exception as e:
        log_message(f'Erro ao processar trigger {trigger_file}: {e}')
        return False

def main():
    log_message('=== MONITOR SPARK SIMPLES INICIADO ===')
    log_message(f'Monitorando: {TRIGGER_DIR}')
    log_message(f'Completed em: {COMPLETED_DIR}')
    
    # Criar diretórios se não existirem
    os.makedirs(TRIGGER_DIR, exist_ok=True)
    os.makedirs(COMPLETED_DIR, exist_ok=True)
    
    while True:
        try:
            # Procurar triggers
            for trigger_file in Path(TRIGGER_DIR).glob('*.json'):
                if trigger_file.is_file():
                    process_trigger(str(trigger_file))
            
            # Aguardar 5 segundos
            time.sleep(5)
            
        except KeyboardInterrupt:
            log_message('Monitor interrompido pelo usuário')
            break
        except Exception as e:
            log_message(f'Erro no loop principal: {e}')
            time.sleep(10)

if __name__ == '__main__':
    main()
