# keep_alive.py - Mantém app ativo no Render Free
import requests
import time
import os

def ping_app():
    """Faz ping no app para manter ativo"""
    url = os.environ.get('APP_URL', 'https://seu-projeto.onrender.com')
    
    try:
        response = requests.get(f"{url}/api/health", timeout=10)
        print(f"✅ Ping realizado: {response.status_code}")
        return True
    except Exception as e:
        print(f"❌ Erro no ping: {e}")
        return False

if __name__ == "__main__":
    print("🔄 Iniciando keep-alive service...")
    
    # Ping a cada 10 minutos
    while True:
        ping_app()
        time.sleep(600)  # 10 minutos