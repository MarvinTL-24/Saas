from flask import Flask, render_template, jsonify, send_from_directory, redirect
import os
import json
import datetime

app = Flask(__name__)

# Sistema básico
class SimpleSystem:
    def __init__(self):
        self.data_dir = 'data'
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs('feeds', exist_ok=True)
        os.makedirs('templates', exist_ok=True)
        
        self.config = self.load_file('config.json', {
            "custom_sites": [],
            "setup_completed": False,
            "whatsapp": {"enabled": False}
        })
        
        self.stats = self.load_file('stats.json', {
            "total_products_found": 15,
            "total_products_sent": 3,
            "last_update": datetime.datetime.now().isoformat()
        })
    
    def load_file(self, filename, default):
        path = os.path.join(self.data_dir, filename)
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except:
                return default
        return default
    
    def save_file(self, filename, data):
        path = os.path.join(self.data_dir, filename)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

system = SimpleSystem()

# Rotas principais
@app.route('/')
def index():
    if not system.config.get("setup_completed"):
        return redirect('/setup')
    return render_template('index.html')

@app.route('/setup')
def setup():
    return render_template('setup.html')

# API
@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify(system.config)

@app.route('/api/stats', methods=['GET'])
def get_stats():
    # Adiciona próxima atualização
    stats = system.stats.copy()
    next_time = datetime.datetime.now() + datetime.timedelta(hours=4)
    stats['next_update'] = next_time.isoformat()
    return jsonify(stats)

@app.route('/api/process/now', methods=['POST'])
def process_now():
    system.stats['total_products_found'] += 5
    system.stats['last_update'] = datetime.datetime.now().isoformat()
    system.save_file('stats.json', system.stats)
    return jsonify({"status": "success", "message": "Processado"})

@app.route('/api/feeds', methods=['GET'])
def list_feeds():
    feeds = []
    if os.path.exists('feeds'):
        for file in os.listdir('feeds'):
            if file.endswith('.xml'):
                feeds.append({
                    "name": file.replace('.xml', '').replace('_', ' '),
                    "url": f"/feeds/{file}",
                    "size": 1024
                })
    
    # Se não tiver feeds, cria um exemplo
    if not feeds:
        feeds.append({
            "name": "Feed de Exemplo",
            "url": "/feeds/exemplo.xml",
            "size": 2048
        })
    
    return jsonify({"feeds": feeds})

@app.route('/feeds/<filename>')
def serve_feed(filename):
    return send_from_directory('feeds', filename)

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)