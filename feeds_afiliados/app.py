import feedgenerator
import requests
from bs4 import BeautifulSoup
import datetime
import json
import os
import schedule
import time
import threading
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for

class AffiliateFeedGenerator:
    def __init__(self, config_file='config.json'):
        """Inicializa o gerador de feeds com configurações"""
        self.config_file = config_file
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Verifica se é primeira execução
        self.is_first_run = not os.path.exists(config_file)
        
        if not self.is_first_run:
            self.load_config()
        else:
            # Configuração inicial padrão
            self.config = self.get_default_config()
    
    def get_default_config(self):
        """Retorna configuração padrão para primeira execução"""
        return {
            "affiliate_tags": {},
            "sites": {
                "amazon": "https://www.amazon.com.br/gp/goldbox",
                "aliexpress": "https://pt.aliexpress.com/category/201002003/discount.html",
                "magazineluiza": "https://www.magazineluiza.com.br/",
                "americanas": "https://www.americanas.com.br/",
                "mercadolivre": "https://www.mercadolivre.com.br/ofertas",
                "shein": "https://pt.shein.com/",
                "shopee": "https://shopee.com.br/",
                "centauro": "https://www.centauro.com.br/promocoes",
                "netshoes": "https://www.netshoes.com.br/",
                "dafiti": "https://www.dafiti.com.br/",
                "zoom": "https://www.zoom.com.br/",
                "kabum": "https://www.kabum.com.br/"
            },
            "update_interval_hours": 6,
            "output_folder": "feeds",
            "setup_completed": False
        }
    
    def load_config(self):
        """Carrega as configurações do arquivo JSON"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except:
            self.config = self.get_default_config()
    
    def save_config(self):
        """Salva as configurações no arquivo JSON"""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def complete_setup(self, affiliate_data):
        """Completa o setup inicial com dados do usuário"""
        self.config['affiliate_tags'] = affiliate_data.get('affiliate_tags', {})
        self.config['setup_completed'] = True
        self.save_config()
        return True
    
    def add_affiliate_tag(self, url, site_name):
        """Adiciona tag de afiliado à URL"""
        if site_name in self.config["affiliate_tags"]:
            tag = self.config["affiliate_tags"][site_name]
            if not tag or tag == "seu-codigo":
                return url  # Não modifica se não configurado
            
            # Verifica se já tem tag
            if 'tag=' in url or 'afiliado=' in url or 'ref=' in url:
                return url
            
            # Adiciona tag baseada no site
            parsed = urlparse(url)
            if parsed.netloc.endswith('amazon.com.br'):
                separator = '&' if parsed.query else '?'
                return f"{url}{separator}tag={tag}"
            elif 'mercadolivre' in parsed.netloc:
                separator = '&' if parsed.query else '?'
                return f"{url}{separator}afiliado={tag}"
            elif 'aliexpress' in parsed.netloc:
                separator = '&' if parsed.query else '?'
                return f"{url}{separator}aff_fcid={tag}"
            else:
                separator = '&' if parsed.query else '?'
                return f"{url}{separator}ref={tag}"
        
        return url
    
    def scrape_amazon(self, url):
        """Extrai produtos da Amazon"""
        try:
            response = self.session.get(url, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')
            products = []
            
            # Melhores seletores para Amazon
            product_selectors = [
                '[data-component-type="s-search-result"]',
                '.deal-tile',
                '.a-carousel-card',
                '.s-result-item'
            ]
            
            all_products = []
            for selector in product_selectors:
                all_products.extend(soup.select(selector))
            
            for product in all_products[:40]:
                try:
                    # Tenta múltiplos seletores
                    title_elem = product.select_one('h2 a span, .a-text-normal, .deal-title')
                    link_elem = product.select_one('h2 a, a.a-link-normal, a.deal-link')
                    price_elem = product.select_one('.a-price-whole, .a-price, .deal-price-text')
                    img_elem = product.select_one('.s-image, img.s-latency-cf-section, .deal-image')
                    
                    if title_elem and link_elem:
                        title = title_elem.text.strip()[:150]
                        link = urljoin('https://www.amazon.com.br', link_elem.get('href', ''))
                        
                        # Extrai preço
                        if price_elem:
                            price_text = price_elem.text.strip()
                            # Remove caracteres não numéricos
                            price = ''.join(filter(str.isdigit, price_text)) or "Preço não disponível"
                        else:
                            price = "Preço não disponível"
                        
                        img = img_elem.get('src', '') if img_elem else ''
                        
                        products.append({
                            'title': title,
                            'link': link,
                            'price': f"R$ {price}" if price != "Preço não disponível" else price,
                            'image': img,
                            'description': f"{title} - R${price}"
                        })
                except:
                    continue
            
            return products[:25]  # Limitar a 25 produtos
        except Exception as e:
            print(f"Erro ao buscar Amazon: {e}")
            return []
    
    def scrape_generic(self, url, site_name):
        """Extrai produtos de sites genéricos"""
        try:
            response = self.session.get(url, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')
            products = []
            
            # Seletores genéricos para e-commerce
            selectors = [
                '.product', '.item', '.card', '[data-product]',
                '.prateleira', '.vitrine', '.listagem-item',
                'article', '.produto', '.product-item'
            ]
            
            all_products = []
            for selector in selectors:
                all_products.extend(soup.select(selector))
            
            for product in all_products[:50]:
                try:
                    # Busca título
                    title_elem = product.select_one(
                        'h2, h3, h4, .product-name, .productTitle, .title, .nome-produto, .produto-nome, [data-name]'
                    )
                    
                    # Busca link
                    link_elem = product.select_one(
                        'a, .product-link, .link-produto, [href]'
                    )
                    
                    # Busca preço
                    price_elem = product.select_one(
                        '.price, .product-price, .valor, .current-price, .preco, [data-price]'
                    )
                    
                    # Busca imagem
                    img_elem = product.select_one(
                        'img, .product-image, .imagem-produto, [data-src], [src]'
                    )
                    
                    if title_elem and link_elem:
                        title = title_elem.text.strip()[:100]
                        link = urljoin(url, link_elem.get('href', ''))
                        
                        if price_elem:
                            price_text = price_elem.text.strip()
                            # Limpa o preço
                            price = ''.join(filter(lambda x: x.isdigit() or x in ',.', price_text))
                            price = price if price else "Preço não disponível"
                        else:
                            price = "Preço não disponível"
                        
                        img = ''
                        if img_elem:
                            img = img_elem.get('src', '') or img_elem.get('data-src', '')
                        
                        products.append({
                            'title': title,
                            'link': link,
                            'price': f"R$ {price}" if price != "Preço não disponível" else price,
                            'image': img,
                            'description': f"{title} - R${price}"
                        })
                except:
                    continue
            
            return products[:20]
        except Exception as e:
            print(f"Erro ao buscar {site_name}: {e}")
            return []
    
    def create_feed(self, site_name, products, site_url):
        """Cria arquivo RSS para um site específico"""
        if not products:
            return None
        
        # Verifica se tem tag de afiliado configurada
        if not self.config.get('affiliate_tags', {}).get(site_name):
            print(f"  ⚠  {site_name}: Sem tag de afiliado configurada")
            return None
        
        # Configurações do feed
        feed = feedgenerator.Rss201rev2Feed(
            title=f"Promoções {site_name.capitalize()} - Afiliado",
            link=site_url,
            description=f"Ofertas e promoções do {site_name} com links de afiliado",
            language="pt-br",
            generator="Sistema Automático de Feeds RSS"
        )
        
        # Adiciona produtos ao feed
        for product in products:
            # Adiciona tag de afiliado
            affiliate_link = self.add_affiliate_tag(product['link'], site_name)
            
            feed.add_item(
                title=f"🔥 {product['title'][:80]} - {product['price']}",
                link=affiliate_link,
                description=f'''
                <div style="font-family: Arial, sans-serif; padding: 15px; border: 1px solid #eee; border-radius: 8px;">
                    <h3 style="margin-top: 0;">{product['title']}</h3>
                    <p style="font-size: 24px; color: #B12704; font-weight: bold;">{product['price']}</p>
                    <p><a href="{affiliate_link}" style="background: #FF9900; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">VER OFERTA →</a></p>
                    {f'<img src="{product["image"]}" width="300" style="max-width: 100%; border-radius: 5px;">' if product['image'] else ''}
                </div>
                ''',
                pubdate=datetime.datetime.now(),
                unique_id=affiliate_link + str(datetime.datetime.now().timestamp())
            )
        
        # Salva o feed
        os.makedirs(self.config['output_folder'], exist_ok=True)
        filename = os.path.join(self.config['output_folder'], f'{site_name}_promocoes.xml')
        
        with open(filename, 'w', encoding='utf-8') as f:
            feed.write(f, 'utf-8')
        
        print(f"  ✓ Feed salvo: {filename}")
        return filename
    
    def generate_all_feeds(self):
        """Gera feeds para todos os sites configurados"""
        print(f"\n{'='*60}")
        print(f"{datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')} - Iniciando geração de feeds...")
        print('='*60)
        
        for site_name, site_url in self.config['sites'].items():
            print(f"\n📦 Processando {site_name.upper()}...")
            
            # Verifica se tem tag configurada
            if not self.config.get('affiliate_tags', {}).get(site_name):
                print(f"  ⚠  Tag de afiliado não configurada - Pulando")
                continue
            
            # Seleciona o scraper apropriado
            if site_name == 'amazon':
                products = self.scrape_amazon(site_url)
            else:
                products = self.scrape_generic(site_url, site_name)
            
            # Cria o feed
            if products:
                feed_file = self.create_feed(site_name, products, site_url)
                if feed_file:
                    print(f"  ✅ {len(products)} produtos adicionados")
                else:
                    print(f"  ❌ Erro ao criar feed")
            else:
                print(f"  ⚠  Nenhum produto encontrado")
        
        print(f"\n{'='*60}")
        print("✅ Geração de feeds concluída!")
        print('='*60)
    
    def run_scheduled(self):
        """Executa em intervalo configurado"""
        # Só agenda se o setup estiver completo
        if not self.config.get('setup_completed', False):
            print("⏰ Setup não completo - Agendamento desativado")
            return
        
        interval = self.config.get('update_interval_hours', 6)
        schedule.every(interval).hours.do(self.generate_all_feeds)
        
        # Executa imediatamente na primeira vez
        self.generate_all_feeds()
        
        print(f"\n⏰ Sistema agendado para atualizar a cada {interval} horas")
        print("🛑 Pressione Ctrl+C para parar\n")
        
        while True:
            schedule.run_pending()
            time.sleep(60)  # Verifica a cada minuto

# Inicializa o gerador
generator = AffiliateFeedGenerator()

# Cria aplicação Flask
app = Flask(__name__)

# Middleware para verificar setup
@app.before_request
def check_setup():
    """Verifica se o setup foi completado"""
    # URLs permitidas sem setup
    allowed_paths = ['/setup', '/api/setup', '/static/', '/favicon.ico']
    
    if any(request.path.startswith(path) for path in allowed_paths):
        return
    
    if not generator.config.get('setup_completed', False):
        return redirect(url_for('setup_page'))

# Rotas da aplicação
@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html', config=generator.config)

@app.route('/setup')
def setup_page():
    """Página de setup inicial"""
    if generator.config.get('setup_completed', False):
        return redirect(url_for('index'))
    return render_template('setup.html', sites=generator.config['sites'])

@app.route('/api/setup', methods=['POST'])
def setup_api():
    """API para configurar setup inicial"""
    try:
        data = request.json
        
        if not data or 'affiliate_tags' not in data:
            return jsonify({'status': 'error', 'message': 'Dados inválidos'})
        
        # Completa o setup
        success = generator.complete_setup(data)
        
        if success:
            # Inicia o agendador
            scheduler_thread = threading.Thread(target=generator.run_scheduled, daemon=True)
            scheduler_thread.start()
            
            return jsonify({
                'status': 'success',
                'message': 'Setup completado com sucesso!',
                'redirect': '/'
            })
        else:
            return jsonify({'status': 'error', 'message': 'Erro ao salvar configurações'})
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/config', methods=['GET', 'POST'])
def config_api():
    """API para gerenciar configurações"""
    if request.method == 'POST':
        data = request.json
        
        # Atualiza tags de afiliado
        if 'affiliate_tags' in data:
            generator.config['affiliate_tags'].update(data['affiliate_tags'])
        
        # Atualiza intervalo
        if 'update_interval_hours' in data:
            generator.config['update_interval_hours'] = data['update_interval_hours']
        
        generator.save_config()
        return jsonify({'status': 'success', 'config': generator.config})
    
    return jsonify(generator.config)

@app.route('/api/feeds/generate', methods=['POST'])
def generate_feed():
    """API para gerar feed específico"""
    data = request.json
    site_name = data.get('site')
    
    if site_name in generator.config['sites']:
        site_url = generator.config['sites'][site_name]
        
        # Verifica se tem tag configurada
        if not generator.config.get('affiliate_tags', {}).get(site_name):
            return jsonify({
                'status': 'error',
                'message': f'Configure primeiro a tag de afiliado para {site_name}'
            })
        
        # Busca produtos
        if site_name == 'amazon':
            products = generator.scrape_amazon(site_url)
        else:
            products = generator.scrape_generic(site_url, site_name)
        
        if products:
            # Cria feed
            feed_file = generator.create_feed(site_name, products, site_url)
            
            if feed_file:
                return jsonify({
                    'status': 'success',
                    'message': f'Feed gerado com {len(products)} produtos',
                    'feed_url': f'/feeds/{os.path.basename(feed_file)}',
                    'products_count': len(products)
                })
    
    return jsonify({'status': 'error', 'message': 'Site não encontrado ou sem produtos'})

@app.route('/api/feeds/generate-all', methods=['POST'])
def generate_all():
    """API para gerar todos os feeds"""
    try:
        generator.generate_all_feeds()
        return jsonify({
            'status': 'success',
            'message': 'Todos os feeds foram gerados'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Erro: {str(e)}'
        })

@app.route('/feeds/<filename>')
def serve_feed(filename):
    """Serve o feed RSS"""
    return send_from_directory(generator.config['output_folder'], filename)

@app.route('/feeds')
def list_feeds():
    """Lista todos os feeds disponíveis"""
    feeds = []
    if os.path.exists(generator.config['output_folder']):
        for file in os.listdir(generator.config['output_folder']):
            if file.endswith('.xml'):
                feeds.append({
                    'name': file,
                    'url': f'/feeds/{file}',
                    'size': os.path.getsize(os.path.join(generator.config['output_folder'], file)),
                    'modified': datetime.datetime.fromtimestamp(
                        os.path.getmtime(os.path.join(generator.config['output_folder'], file))
                    ).strftime('%d/%m/%Y %H:%M')
                })
    
    return jsonify({'feeds': feeds})

def start_scheduler():
    """Inicia o agendador"""
    generator.run_scheduled()

if __name__ == "__main__":
    # Cria pastas necessárias
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    os.makedirs('feeds', exist_ok=True)
    
    # Cria templates se não existirem
    if not os.path.exists('templates/setup.html'):
        with open('templates/setup.html', 'w', encoding='utf-8') as f:
            f.write('''
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Configuração Inicial - Feeds RSS</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --primary: #667eea;
            --secondary: #764ba2;
            --success: #10b981;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .setup-container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            width: 100%;
            max-width: 800px;
            box-shadow: 0 30px 80px rgba(0,0,0,0.15);
        }
        
        .setup-header {
            text-align: center;
            margin-bottom: 40px;
        }
        
        .setup-header h1 {
            color: #1f2937;
            margin-bottom: 10px;
            font-size: 2.5rem;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 15px;
        }
        
        .setup-header p {
            color: #6b7280;
            font-size: 1.1rem;
            line-height: 1.6;
        }
        
        .setup-form {
            margin-bottom: 30px;
        }
        
        .form-group {
            margin-bottom: 25px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 10px;
            font-weight: 600;
            color: #374151;
            font-size: 1.1rem;
        }
        
        .form-group small {
            display: block;
            margin-top: 5px;
            color: #6b7280;
            font-size: 0.9rem;
        }
        
        .site-config {
            background: #f9fafb;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid #e5e7eb;
        }
        
        .site-header {
            display: flex;
            align-items: center;
            margin-bottom: 15px;
            gap: 15px;
        }
        
        .site-icon {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
        }
        
        .site-name {
            font-weight: 600;
            color: #1f2937;
            font-size: 1.2rem;
        }
        
        .site-url {
            color: #6b7280;
            font-size: 0.9rem;
            margin-top: 2px;
        }
        
        .input-group {
            display: flex;
            gap: 15px;
            align-items: center;
        }
        
        .input-group input {
            flex: 1;
            padding: 14px 18px;
            border: 2px solid #e5e7eb;
            border-radius: 10px;
            font-size: 1rem;
            transition: all 0.3s;
        }
        
        .input-group input:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        .input-group .hint {
            color: #9ca3af;
            font-size: 0.9rem;
            font-style: italic;
        }
        
        .setup-footer {
            text-align: center;
            margin-top: 40px;
            padding-top: 30px;
            border-top: 2px solid #f3f4f6;
        }
        
        .btn {
            padding: 16px 40px;
            border: none;
            border-radius: 12px;
            font-size: 1.1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            display: inline-flex;
            align-items: center;
            gap: 12px;
            text-decoration: none;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, var(--success) 0%, #059669 100%);
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 15px 30px rgba(16, 185, 129, 0.3);
        }
        
        .loading {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.7);
            z-index: 1000;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 1.5rem;
            flex-direction: column;
            gap: 20px;
        }
        
        .loading-spinner {
            width: 50px;
            height: 50px;
            border: 5px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: white;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .notification {
            position: fixed;
            top: 30px;
            right: 30px;
            padding: 20px 25px;
            border-radius: 12px;
            color: white;
            font-weight: 600;
            z-index: 1001;
            animation: slideIn 0.3s ease;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .notification-success {
            background: linear-gradient(135deg, var(--success) 0%, #059669 100%);
        }
        
        .notification-error {
            background: #ef4444;
        }
        
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        
        @keyframes slideOut {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }
        
        @media (max-width: 768px) {
            .setup-container {
                padding: 25px;
            }
            
            .setup-header h1 {
                font-size: 2rem;
            }
            
            .input-group {
                flex-direction: column;
                align-items: stretch;
            }
            
            .btn {
                width: 100%;
                justify-content: center;
            }
        }
    </style>
</head>
<body>
    <div class="setup-container">
        <div class="setup-header">
            <h1><i class="fas fa-tools"></i> Configuração Inicial</h1>
            <p>Para começar a usar o sistema, configure seus códigos de afiliado nos sites abaixo. Você pode deixar em branco os sites que não deseja monitorar.</p>
        </div>
        
        <div class="setup-form">
            <div class="form-group">
                <label><i class="fas fa-info-circle"></i> Como funciona:</label>
                <small>O sistema irá monitorar automaticamente os sites configurados e gerar feeds RSS com SEUS links de afiliado. Configure uma vez e funcione 24h/dia!</small>
            </div>
            
            <form id="setupForm">
                {% for site_name, site_url in sites.items() %}
                <div class="site-config">
                    <div class="site-header">
                        <div class="site-icon">
                            <i class="fas fa-store"></i>
                        </div>
                        <div>
                            <div class="site-name">{{ site_name.upper() }}</div>
                            <div class="site-url">{{ site_url }}</div>
                        </div>
                    </div>
                    
                    <div class="input-group">
                        <input type="text" 
                               name="{{ site_name }}" 
                               placeholder="Digite seu código de afiliado..."
                               autocomplete="off">
                        <div class="hint">
                            {% if site_name == 'amazon' %}
                            Tag: sua-tag-20
                            {% elif site_name == 'mercadolivre' %}
                            Código afiliado
                            {% elif site_name == 'aliexpress' %}
                            aff_fcid
                            {% else %}
                            Código de referência
                            {% endif %}
                        </div>
                    </div>
                </div>
                {% endfor %}
                
                <div class="form-group">
                    <label><i class="fas fa-clock"></i> Intervalo de Atualização:</label>
                    <div class="input-group">
                        <input type="number" 
                               name="update_interval" 
                               value="6" 
                               min="1" 
                               max="24"
                               placeholder="Horas entre atualizações">
                        <div class="hint">O sistema atualizará os feeds automaticamente a cada X horas</div>
                    </div>
                </div>
            </form>
        </div>
        
        <div class="setup-footer">
            <button class="btn btn-primary" onclick="completeSetup()">
                <i class="fas fa-rocket"></i> CONCLUIR CONFIGURAÇÃO E INICIAR SISTEMA
            </button>
            <p style="margin-top: 20px; color: #6b7280; font-size: 0.9rem;">
                <i class="fas fa-lightbulb"></i> Você poderá alterar essas configurações depois na interface principal
            </p>
        </div>
    </div>
    
    <div class="loading" id="loadingOverlay">
        <div class="loading-spinner"></div>
        <div>Configurando sistema...</div>
    </div>
    
    <script>
        function showLoading(message) {
            const loading = document.getElementById('loadingOverlay');
            loading.style.display = 'flex';
        }
        
        function hideLoading() {
            document.getElementById('loadingOverlay').style.display = 'none';
        }
        
        function showNotification(message, type) {
            const notification = document.createElement('div');
            notification.className = `notification notification-${type}`;
            notification.innerHTML = `
                <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'}"></i>
                ${message}
            `;
            
            document.body.appendChild(notification);
            
            setTimeout(() => {
                notification.style.animation = 'slideOut 0.3s ease';
                setTimeout(() => notification.remove(), 300);
            }, 4000);
        }
        
        async function completeSetup() {
            showLoading('Salvando configurações...');
            
            try {
                const form = document.getElementById('setupForm');
                const inputs = form.querySelectorAll('input');
                
                const affiliate_tags = {};
                let update_interval = 6;
                
                inputs.forEach(input => {
                    if (input.name === 'update_interval') {
                        update_interval = parseInt(input.value) || 6;
                    } else {
                        const value = input.value.trim();
                        if (value) {
                            affiliate_tags[input.name] = value;
                        }
                    }
                });
                
                // Verifica se pelo menos um site foi configurado
                if (Object.keys(affiliate_tags).length === 0) {
                    showNotification('Configure pelo menos um código de afiliado para continuar', 'error');
                    hideLoading();
                    return;
                }
                
                const response = await fetch('/api/setup', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        affiliate_tags,
                        update_interval_hours: update_interval
                    })
                });
                
                const result = await response.json();
                
                if (result.status === 'success') {
                    showNotification('Sistema configurado com sucesso!', 'success');
                    
                    // Redireciona após 2 segundos
                    setTimeout(() => {
                        window.location.href = result.redirect || '/';
                    }, 2000);
                    
                } else {
                    showNotification(result.message || 'Erro ao configurar sistema', 'error');
                    hideLoading();
                }
                
            } catch (error) {
                showNotification('Erro de conexão: ' + error.message, 'error');
                hideLoading();
            }
        }
        
        // Auto-focus no primeiro input
        document.addEventListener('DOMContentLoaded', () => {
            const firstInput = document.querySelector('input');
            if (firstInput) {
                firstInput.focus();
            }
        });
    </script>
</body>
</html>
            ''')
    
    # Inicia o sistema
    print("\n" + "="*60)
    print("🚀 SISTEMA DE FEEDS RSS PARA AFILIADOS")
    print("="*60)
    
    if generator.is_first_run:
        print("\n📝 PRIMEIRA EXECUÇÃO DETECTADA")
        print("Acesse: http://localhost:5000/setup")
        print("Para configurar seus códigos de afiliado")
    else:
        print("\n✅ Sistema já configurado")
        print("📊 Acesse a interface em: http://localhost:5000")
        
        # Inicia o agendador em thread separada
        scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
        scheduler_thread.start()
    
    print("\n" + "="*60 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)