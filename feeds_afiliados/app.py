import feedgenerator
import requests
from bs4 import BeautifulSoup
import datetime
import json
import os
import time
import threading
import random
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
from flask import Flask, render_template, request, jsonify, send_from_directory, redirect
from flask_cors import CORS

# ========== CONFIGURAÇÃO FLASK ==========
app = Flask(__name__)
CORS(app)

# ========== SISTEMA COMPLETO ==========
class AdvancedAffiliateSystem:
    def __init__(self):
        self.config_file = 'data/config.json'
        self.stats_file = 'data/stats.json'
        
        # Garante pastas existem
        os.makedirs('feeds', exist_ok=True)
        os.makedirs('data', exist_ok=True)
        os.makedirs('templates', exist_ok=True)
        
        # Inicializa
        self.config = self.load_config()
        self.stats = self.load_stats()
        
        # Session para requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Inicializa feeds
        self.init_sample_feeds()
    
    def load_config(self):
        """Carrega configurações"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return self.get_default_config()
    
    def load_stats(self):
        """Carrega estatísticas"""
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return self.get_default_stats()
    
    def get_default_config(self):
        """Configuração padrão"""
        return {
            "custom_sites": [],
            "setup_completed": False,
            "whatsapp": {
                "enabled": False,
                "phone_numbers": [],
                "daily_limit": 20,
                "whatsapp_api_key": "",
                "products_per_interval": 5,
                "send_times": ["09:00", "13:00", "17:00", "21:00"]
            },
            "update_settings": {
                "interval_hours": 4,
                "products_per_update": 20,
                "start_immediately": True
            },
            "affiliate_settings": {
                "default_affiliate_type": "tag"
            }
        }
    
    def get_default_stats(self):
        """Estatísticas padrão"""
        return {
            "total_products_found": 0,
            "total_products_sent": 0,
            "total_feeds_generated": 0,
            "last_update": None,
            "next_update": None,
            "whatsapp_stats": {
                "sent_today": 0,
                "failed_today": 0,
                "last_sent": None
            }
        }
    
    def save_config(self):
        """Salva configurações"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def save_stats(self):
        """Salva estatísticas"""
        with open(self.stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2, ensure_ascii=False)
    
    def init_sample_feeds(self):
        """Cria feeds de exemplo"""
        if not os.path.exists('feeds'):
            os.makedirs('feeds', exist_ok=True)
        
        # Feed exemplo 1
        feed1 = feedgenerator.Rss201rev2Feed(
            title="Promoções Amazon - Sistema Automático",
            link="https://www.amazon.com.br",
            description="Ofertas coletadas automaticamente da Amazon",
            language="pt-br"
        )
        
        feed1.add_item(
            title="🔥 Smartphone Android 128GB",
            link="https://www.amazon.com.br/dp/B0C1234567",
            description="Smartphone com tela 6.5'', 8GB RAM, 128GB",
            pubdate=datetime.datetime.now()
        )
        
        with open('feeds/amazon_promocoes.xml', 'w', encoding='utf-8') as f:
            feed1.write(f, 'utf-8')
    
    def scrape_site(self, url):
        """Raspa site (simplificado)"""
        try:
            # Para demonstração, retorna produtos fictícios
            return [
                {
                    'title': 'Produto Exemplo 1',
                    'link': f'{url}/produto1',
                    'price': 'R$ 299,90',
                    'category': 'Eletrônicos'
                },
                {
                    'title': 'Produto Exemplo 2', 
                    'link': f'{url}/produto2',
                    'price': 'R$ 149,50',
                    'category': 'Acessórios'
                }
            ]
        except:
            return []
    
    def create_feed(self, products, site_name):
        """Cria feed RSS"""
        if not products:
            return None
        
        feed = feedgenerator.Rss201rev2Feed(
            title=f"Promoções {site_name}",
            link="https://seu-app.onrender.com",
            description=f"Ofertas coletadas do {site_name}",
            language="pt-br"
        )
        
        for product in products[:10]:
            feed.add_item(
                title=product['title'],
                link=product['link'],
                description=f"Preço: {product['price']} | Categoria: {product['category']}",
                pubdate=datetime.datetime.now()
            )
        
        filename = f"feeds/{site_name.lower().replace(' ', '_')}.xml"
        with open(filename, 'w', encoding='utf-8') as f:
            feed.write(f, 'utf-8')
        
        return filename

# ========== INICIALIZA SISTEMA ==========
system = AdvancedAffiliateSystem()

# ========== ROTAS PRINCIPAIS ==========
@app.route('/')
def index():
    """Página principal"""
    if not system.config.get("setup_completed"):
        return redirect('/setup')
    return render_template('index.html')

@app.route('/setup')
def setup():
    """Página de configuração"""
    return render_template('setup.html')

# ========== API ENDPOINTS COMPATÍVEIS ==========
@app.route('/api/config', methods=['GET'])
def get_config():
    """Retorna configurações (compatível com frontend)"""
    return jsonify(system.config)

@app.route('/api/config', methods=['POST'])
def update_config():
    """Atualiza configurações"""
    try:
        data = request.json
        if 'update_settings' in data:
            system.config['update_settings'].update(data['update_settings'])
        if 'whatsapp' in data:
            system.config['whatsapp'].update(data['whatsapp'])
        system.save_config()
        return jsonify({"status": "success", "message": "Configuração atualizada"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Retorna estatísticas (compatível com frontend)"""
    # Adiciona dados simulados para compatibilidade
    stats = system.stats.copy()
    stats['total_products'] = stats.get('total_products_found', 0)
    stats['total_products_sent'] = stats.get('total_products_sent', 0)
    
    # Próxima atualização (simulada)
    if not stats.get('next_update'):
        next_time = datetime.datetime.now() + datetime.timedelta(hours=4)
        stats['next_update'] = next_time.isoformat()
    
    return jsonify(stats)

@app.route('/api/feeds', methods=['GET'])
def list_feeds():
    """Lista feeds disponíveis"""
    feeds = []
    if os.path.exists('feeds'):
        for file in os.listdir('feeds'):
            if file.endswith('.xml'):
                filepath = os.path.join('feeds', file)
                feeds.append({
                    "name": file.replace('.xml', '').replace('_', ' ').title(),
                    "url": f"/feeds/{file}",
                    "size": os.path.getsize(filepath)
                })
    
    return jsonify({"feeds": feeds})

@app.route('/feeds/<filename>')
def serve_feed(filename):
    """Serve arquivo de feed"""
    return send_from_directory('feeds', filename)

@app.route('/api/process/now', methods=['POST'])
def process_now():
    """Processa agora"""
    try:
        # Simula processamento
        system.stats["total_products_found"] = system.stats.get("total_products_found", 0) + random.randint(5, 15)
        system.stats["last_update"] = datetime.datetime.now().isoformat()
        
        # Próxima atualização em 4 horas
        next_time = datetime.datetime.now() + datetime.timedelta(hours=4)
        system.stats["next_update"] = next_time.isoformat()
        
        system.save_stats()
        
        return jsonify({
            "status": "success",
            "message": "Processamento simulado com sucesso",
            "products_added": system.stats["total_products_found"]
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/whatsapp/api-key', methods=['POST'])
def update_api_key():
    """Atualiza chave API WhatsApp"""
    try:
        data = request.json
        api_key = data.get('api_key')
        
        if api_key:
            system.config['whatsapp']['whatsapp_api_key'] = api_key
            system.save_config()
            return jsonify({"status": "success", "message": "Chave API atualizada"})
        else:
            return jsonify({"status": "error", "message": "Chave API requerida"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/sites', methods=['GET', 'POST'])
def manage_sites():
    """Gerencia sites"""
    if request.method == 'POST':
        try:
            data = request.json
            if isinstance(data, list):
                system.config['custom_sites'] = data
            else:
                system.config['custom_sites'].append(data)
            
            system.save_config()
            return jsonify({"status": "success", "sites": system.config['custom_sites']})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    
    return jsonify({"sites": system.config['custom_sites']})

@app.route('/api/setup', methods=['POST'])
def complete_setup():
    """Completa setup inicial"""
    try:
        data = request.json
        system.config.update(data)
        system.config['setup_completed'] = True
        system.save_config()
        return jsonify({"status": "success", "message": "Setup completado"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Endpoint de saúde"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "setup_completed": system.config.get("setup_completed", False)
    })

# ========== MANUTENÇÃO PARA PLANO FREE ==========
def keep_alive():
    """Mantém o app ativo no plano free"""
    def ping():
        while True:
            try:
                # Pinga a própria aplicação
                if 'RENDER' in os.environ:
                    app_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', '')}"
                    requests.get(f'{app_url}/api/health', timeout=5)
            except:
                pass
            time.sleep(300)  # 5 minutos
    
    thread = threading.Thread(target=ping, daemon=True)
    thread.start()

# ========== AJUSTE DO FRONTEND ==========
@app.after_request
def add_header(response):
    """Adiciona headers para evitar cache"""
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# ========== INICIALIZAÇÃO ==========
if __name__ == '__main__':
    # Inicia keep-alive se estiver no Render
    if os.environ.get('RENDER'):
        keep_alive()
    
    # Porta do Render ou local
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    # Para Gunicorn
    if os.environ.get('RENDER'):
        keep_alive()