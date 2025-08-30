#!/usr/bin/env python3
"""
Script para testar conectividade com Spark Master
"""

import requests
import sys

def test_spark_connection():
    """Testa a conectividade com o Spark Master"""
    
    spark_master_url = "http://spark-master:8082"
    
    try:
        print(f"Testando conectividade com {spark_master_url}...")
        
        # Testa endpoint básico
        response = requests.get(f"{spark_master_url}/", timeout=10)
        
        if response.status_code == 200:
            print("✅ Conectividade com Spark Master OK")
            
            # Testa endpoint da API de submissão
            api_url = f"{spark_master_url}/v1/submissions"
            response = requests.get(api_url, timeout=10)
            
            if response.status_code in [200, 404]:  
                print("✅ API de submissões acessível")
                return True
            else:
                print(f"⚠️ API de submissões retornou status {response.status_code}")
                return False
        else:
            print(f"❌ Erro de conectividade: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erro de conectividade: {e}")
        return False

if __name__ == "__main__":
    success = test_spark_connection()
    sys.exit(0 if success else 1)