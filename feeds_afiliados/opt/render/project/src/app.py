import feedgenerator
import requests
from bs4 import BeautifulSoup
import datetime
import json
import os
import schedule
import time
import threading
import random
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for
from flask_cors import CORS
from dotenv import load_dotenv
import logging
from dateutil import parser as date_parser
from datetime import timedelta

# Carrega variáveis de ambiente
load_dotenv()

class AdvancedAffiliateSystem:
    def __init__(self, config_file='config.json'):
        """Sistema avançado de feeds RSS + WhatsApp"""
        self.config_file = config_file
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Configuração de logging
        logging.basicConfig(level=logging.INFO, 
                           format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # Verifica se é primeira execução
        self.is_first_run = not os.path.exists(config_file)
        
        if not self.is_first_run:
            self.load_config()
            self.load_stats()
        else:
            self.config = self.get_default_config()
            self.stats = self.get_default_stats()
        
        # Controle de envios
        self.daily_sent = 0
        self.last_reset = datetime.datetime.now()
        self.whatsapp_api_key = None
        
    def get_default_config(self):
        """Configuração padrão"""
        return {
            "custom_sites": [],  # [{name, url, affiliate_type, affiliate_code, categories}]
            "whatsapp": {
                "enabled": False,
                "phone_numbers": [],
                "send_times": ["09:00", "13:00", "17:00", "21:00"],
                "products_per_interval": 5,
                "daily_limit": 20,
                "message_template": "🔥 *OFERTA ESPECIAL* 🔥\n\n*Produto:* {title}\n*Preço:* {price}\n*Categoria:* {category}\n*Site:* {site}\n\n🔗 {link}\n\n📱 Enviado via Sistema Automático",
                "categories_filter": [],  # ["eletrônicos", "roupas", "casa"]
                "min_price": 0,
                "max_price": 10000,
                "whatsapp_api_key": "",  # Chave API WhatsApp Business
                "api_key_expires": None,  # Data de expiração da chave
                "refresh_api_key": True   # Atualizar chave automaticamente
            },
            "update_settings": {
                "interval_hours": 4,
                "start_immediately": True,
                "random_delay_minutes": 5,
                "products_per_update": 20
            },
            "affiliate_settings": {
                "amazon_tag": "",
                "default_affiliate_type": "tag",  # tag, ref, affiliate_id, etc
                "auto_detect_affiliate": True
            },
            "notification_settings": {
                "email_notifications": False,
                "email_address": "",
                "telegram_notifications": False,
                "telegram_bot_token": "",
                "telegram_chat_id": ""
            },
            "setup_completed": False,
            "output_folder": "feeds",
            "data_folder": "data"
        }
    
    def get_default_stats(self):
        """Estatísticas padrão"""
        return {
            "total_products_found": 0,
            "total_products_sent": 0,
            "total_feeds_generated": 0,
            "last_update": None,
            "next_update": None,
            "daily_stats": {},
            "site_stats": {},
            "whatsapp_stats": {
                "sent_today": 0,
                "failed_today": 0,
                "last_sent": None
            }
        }
    
    def load_config(self):
        """Carrega configurações"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            
            # Verifica se precisa atualizar estrutura
            self.update_config_structure()
            
        except Exception as e:
            self.logger.error(f"Erro ao carregar config: {e}")
            self.config = self.get_default_config()
    
    def load_stats(self):
        """Carrega estatísticas"""
        stats_file = os.path.join(self.config['data_folder'], 'stats.json')
        try:
            if os.path.exists(stats_file):
                with open(stats_file, 'r', encoding='utf-8') as f:
                    self.stats = json.load(f)
            else:
                self.stats = self.get_default_stats()
        except:
            self.stats = self.get_default_stats()
    
    def save_config(self):
        """Salva configurações"""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def save_stats(self):
        """Salva estatísticas"""
        data_folder = self.config.get('data_folder', 'data')
        os.makedirs(data_folder, exist_ok=True)
        
        stats_file = os.path.join(data_folder, 'stats.json')
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2, ensure_ascii=False, default=str)
    
    def update_config_structure(self):
        """Atualiza estrutura do config se necessário"""
        # Adiciona campos novos se não existirem
        defaults = self.get_default_config()
        
        for key in defaults:
            if key not in self.config:
                self.config[key] = defaults[key]
        
        # Salva configuração atualizada
        self.save_config()
    
    def add_custom_site(self, site_data):
        """Adiciona site personalizado"""
        site = {
            "name": site_data.get("name"),
            "url": site_data.get("url"),
            "affiliate_type": site_data.get("affiliate_type", "tag"),
            "affiliate_code": site_data.get("affiliate_code", ""),
            "categories": site_data.get("categories", []),
            "selectors": site_data.get("selectors", {
                "product": ".product",
                "title": "h2, .product-name",
                "link": "a",
                "price": ".price, .product-price",
                "image": "img"
            }),
            "enabled": site_data.get("enabled", True)
        }
        
        self.config["custom_sites"].append(site)
        self.save_config()
        return site
    
    def update_whatsapp_api_key(self, api_key, expires_in_hours=24):
        """Atualiza chave API do WhatsApp"""
        self.config["whatsapp"]["whatsapp_api_key"] = api_key
        expire_time = datetime.datetime.now() + timedelta(hours=expires_in_hours)
        self.config["whatsapp"]["api_key_expires"] = expire_time.isoformat()
        self.save_config()
        self.logger.info(f"API Key atualizada. Expira em: {expire_time}")
    
    def check_api_key_expired(self):
        """Verifica se a chave API expirou"""
        if not self.config["whatsapp"]["whatsapp_api_key"]:
            return True
        
        expire_str = self.config["whatsapp"]["api_key_expires"]
        if not expire_str:
            return True
        
        try:
            expire_time = date_parser.parse(expire_str)
            return datetime.datetime.now() > expire_time
        except:
            return True
    
    def send_whatsapp_via_api(self, phone, message):
        """Envia mensagem via API WhatsApp Business"""
        try:
            if self.check_api_key_expired():
                self.logger.error("API Key expirada ou inválida")
                return False
            
            # Aqui você implementaria a chamada real à API WhatsApp Business
            # Exemplo com requests:
            """
            api_url = "https://graph.facebook.com/v17.0/{phone-id}/messages"
            headers = {
                "Authorization": f"Bearer {self.config['whatsapp']['whatsapp_api_key']}",
                "Content-Type": "application/json"
            }
            data = {
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "text",
                "text": {"body": message}
            }
            
            response = requests.post(api_url, headers=headers, json=data)
            return response.status_code == 200
            """
            
            # Por enquanto, simulamos o envio
            self.logger.info(f"[SIMULAÇÃO] Enviando para {phone}: {message[:50]}...")
            time.sleep(1)  # Simula delay
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao enviar via API: {e}")
            return False
    
    def send_whatsapp_via_web(self, phone, message):
        """Envia via WhatsApp Web (fallback)"""
        try:
            import pywhatkit
            # Envia mensagem
            pywhatkit.sendwhatmsg_instantly(
                phone_no=phone,
                message=message,
                wait_time=20,
                tab_close=True,
                close_time=5
            )
            return True
        except Exception as e:
            self.logger.error(f"Erro WhatsApp Web: {e}")
            return False
    
    def send_whatsapp_message(self, phone, product):
        """Envia produto para WhatsApp"""
        # Verifica limites diários
        if self.stats["whatsapp_stats"]["sent_today"] >= self.config["whatsapp"]["daily_limit"]:
            self.logger.warning(f"Limite diário atingido: {self.stats['whatsapp_stats']['sent_today']}/{self.config['whatsapp']['daily_limit']}")
            return False
        
        # Formata mensagem
        message = self.format_whatsapp_message(product)
        
        # Tenta via API primeiro
        success = self.send_whatsapp_via_api(phone, message)
        
        # Fallback para WhatsApp Web
        if not success and self.config["whatsapp"].get("use_web_fallback", True):
            self.logger.info("Tentando via WhatsApp Web...")
            success = self.send_whatsapp_via_web(phone, message)
        
        if success:
            # Atualiza estatísticas
            self.stats["whatsapp_stats"]["sent_today"] += 1
            self.stats["whatsapp_stats"]["last_sent"] = datetime.datetime.now().isoformat()
            self.stats["total_products_sent"] += 1
            self.save_stats()
            
            self.logger.info(f"Mensagem enviada para {phone}")
            return True
        
        self.stats["whatsapp_stats"]["failed_today"] += 1
        self.save_stats()
        return False
    
    def format_whatsapp_message(self, product):
        """Formata mensagem para WhatsApp"""
        template = self.config["whatsapp"]["message_template"]
        
        # Substitui variáveis
        message = template.format(
            title=product.get('title', ''),
            price=product.get('price', ''),
            category=product.get('category', 'Geral'),
            site=product.get('site', ''),
            link=product.get('affiliate_link', ''),
            discount=product.get('discount', ''),
            original_price=product.get('original_price', ''),
            rating=product.get('rating', ''),
            description=product.get('description', '')[:100]
        )
        
        # Adiciona emojis baseados na categoria
        category_emojis = {
            "eletrônicos": "📱💻🎮",
            "roupas": "👕👖👗",
            "casa": "🏠🛋️🍳",
            "esportes": "⚽🏀🎾",
            "beleza": "💄💅🧴",
            "livros": "📚📖🎓"
        }
        
        category = product.get('category', '').lower()
        for cat, emoji in category_emojis.items():
            if cat in category:
                message = f"{emoji} {message}"
                break
        
        return message
    
    def scrape_site(self, site_config):
        """Raspa site específico"""
        try:
            url = site_config["url"]
            response = self.session.get(url, timeout=20)
            soup = BeautifulSoup(response.content, 'html.parser')
            products = []
            
            # Usa seletores personalizados ou padrão
            selectors = site_config.get("selectors", {})
            product_selector = selectors.get("product", ".product, .item, [data-product]")
            title_selector = selectors.get("title", "h2, h3, .title, .product-name")
            link_selector = selectors.get("link", "a, .product-link")
            price_selector = selectors.get("price", ".price, .product-price, .valor")
            image_selector = selectors.get("image", "img, .product-image")
            
            product_elements = soup.select(product_selector)
            
            for elem in product_elements[:30]:  # Limita a 30 produtos por site
                try:
                    title_elem = elem.select_one(title_selector)
                    link_elem = elem.select_one(link_selector)
                    price_elem = elem.select_one(price_selector)
                    image_elem = elem.select_one(image_selector)
                    
                    if not (title_elem and link_elem):
                        continue
                    
                    title = title_elem.text.strip()[:150]
                    link = urljoin(url, link_elem.get('href', ''))
                    price = price_elem.text.strip() if price_elem else "Preço não disponível"
                    image = image_elem.get('src', '') if image_elem else ''
                    
                    # Detecta categoria
                    category = self.detect_category(title, site_config.get("categories", []))
                    
                    # Aplica filtros de preço
                    try:
                        price_num = float(''.join(filter(str.isdigit, price)))
                        if price_num < self.config["whatsapp"]["min_price"]:
                            continue
                        if self.config["whatsapp"]["max_price"] > 0 and price_num > self.config["whatsapp"]["max_price"]:
                            continue
                    except:
                        pass
                    
                    # Aplica filtro de categorias
                    categories_filter = self.config["whatsapp"]["categories_filter"]
                    if categories_filter and category.lower() not in [c.lower() for c in categories_filter]:
                        continue
                    
                    # Adiciona tag de afiliado
                    affiliate_link = self.add_affiliate_tag(link, site_config)
                    
                    product_data = {
                        'title': title,
                        'link': link,
                        'affiliate_link': affiliate_link,
                        'price': price,
                        'image': image,
                        'category': category,
                        'site': site_config["name"],
                        'timestamp': datetime.datetime.now().isoformat(),
                        'score': self.calculate_product_score(title, price, category)
                    }
                    
                    products.append(product_data)
                    
                except Exception as e:
                    continue
            
            return products
            
        except Exception as e:
            self.logger.error(f"Erro ao raspar {site_config['name']}: {e}")
            return []
    
    def detect_category(self, title, site_categories):
        """Detecta categoria do produto"""
        title_lower = title.lower()
        
        # Mapeamento de palavras-chave para categorias
        category_keywords = {
            "celular": "Eletrônicos",
            "smartphone": "Eletrônicos",
            "notebook": "Eletrônicos",
            "computador": "Eletrônicos",
            "tv": "Eletrônicos",
            "fone": "Eletrônicos",
            "camiseta": "Roupas",
            "calça": "Roupas",
            "vestido": "Roupas",
            "sapato": "Roupas",
            "tenis": "Roupas",
            "sofá": "Casa",
            "cama": "Casa",
            "mesa": "Casa",
            "geladeira": "Eletrodomésticos",
            "fogão": "Eletrodomésticos",
            "livro": "Livros",
            "perfume": "Beleza",
            "creme": "Beleza",
            "bola": "Esportes",
            "raquete": "Esportes"
        }
        
        for keyword, category in category_keywords.items():
            if keyword in title_lower:
                return category
        
        # Retorna primeira categoria do site ou "Geral"
        return site_categories[0] if site_categories else "Geral"
    
    def calculate_product_score(self, title, price, category):
        """Calcula score do produto para ranking"""
        score = 0
        
        # Pontua por palavras-chave no título
        keywords = ["promoção", "oferta", "desconto", "black friday", "cyber monday", "liquidação"]
        for keyword in keywords:
            if keyword in title.lower():
                score += 10
        
        # Tenta extrair preço numérico
        try:
            price_num = float(''.join(filter(str.isdigit, price)))
            if price_num < 100:
                score += 5  # Produtos baratos
            elif price_num < 500:
                score += 3
        except:
            pass
        
        # Pontua por categoria popular
        popular_categories = ["Eletrônicos", "Roupas", "Smartphones"]
        if category in popular_categories:
            score += 2
        
        return score
    
    def add_affiliate_tag(self, url, site_config):
        """Adiciona tag de afiliado à URL"""
        affiliate_code = site_config.get("affiliate_code")
        affiliate_type = site_config.get("affiliate_type", "tag")
        
        if not affiliate_code:
            return url
        
        parsed = urlparse(url)
        
        # Remove tags existentes
        query = parse_qs(parsed.query)
        for key in ['tag', 'ref', 'affiliate', 'afiliado', 'partner']:
            if key in query:
                del query[key]
        
        # Adiciona nova tag
        if affiliate_type == "tag":
            query['tag'] = [affiliate_code]
        elif affiliate_type == "ref":
            query['ref'] = [affiliate_code]
        elif affiliate_type == "affiliate":
            query['affiliate'] = [affiliate_code]
        elif affiliate_type == "partner":
            query['partner'] = [affiliate_code]
        elif affiliate_type == "custom":
            # Para sites customizados, usa o parâmetro especificado
            custom_param = site_config.get("affiliate_param", "ref")
            query[custom_param] = [affiliate_code]
        
        # Reconstrói URL
        new_query = urlencode(query, doseq=True)
        return parsed._replace(query=new_query).geturl()
    
    def get_all_products(self):
        """Busca produtos de todos os sites"""
        all_products = []
        
        # Sites customizados
        for site in self.config["custom_sites"]:
            if not site.get("enabled", True):
                continue
            
            products = self.scrape_site(site)
            all_products.extend(products)
            self.logger.info(f"{site['name']}: {len(products)} produtos")
        
        # Ordena por score
        all_products.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        # Limita quantidade total
        max_products = self.config["update_settings"]["products_per_update"]
        all_products = all_products[:max_products]
        
        self.stats["total_products_found"] += len(all_products)
        return all_products
    
    def distribute_products_for_interval(self, products, interval_count):
        """Distribui produtos entre intervalos"""
        products_per_interval = self.config["whatsapp"]["products_per_interval"]
        
        # Divide produtos em lotes para cada intervalo
        distributed = []
        for i in range(0, len(products), products_per_interval):
            batch = products[i:i + products_per_interval]
            if batch:
                distributed.append(batch)
        
        # Se tiver mais intervalos que lotes, duplica alguns produtos
        while len(distributed) < interval_count and distributed:
            distributed.append(distributed[-1][:products_per_interval])
        
        # Limita ao número de intervalos
        return distributed[:interval_count]
    
    def create_feed(self, products):
        """Cria feeds RSS"""
        if not products:
            return []
        
        # Agrupa por site
        products_by_site = {}
        for product in products:
            site = product['site']
            if site not in products_by_site:
                products_by_site[site] = []
            products_by_site[site].append(product)
        
        feed_files = []
        
        for site_name, site_products in products_by_site.items():
            # Encontra URL do site
            site_url = ""
            for site in self.config["custom_sites"]:
                if site["name"] == site_name:
                    site_url = site["url"]
                    break
            
            # Cria feed
            feed = feedgenerator.Rss201rev2Feed(
                title=f"Promoções {site_name} - Sistema Automático",
                link=site_url,
                description=f"Ofertas coletadas automaticamente do {site_name}",
                language="pt-br",
                generator="Sistema Avançado de Feeds"
            )
            
            for product in site_products[:20]:
                feed.add_item(
                    title=f"🔥 {product['title'][:80]}",
                    link=product['affiliate_link'],
                    description=f'''
                    <div style="font-family: Arial, sans-serif;">
                        <h3>{product['title']}</h3>
                        <p><strong>Preço:</strong> {product['price']}</p>
                        <p><strong>Categoria:</strong> {product['category']}</p>
                        <p><a href="{product['affiliate_link']}" style="background: #25D366; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Ver Oferta</a></p>
                        {f'<img src="{product["image"]}" width="300" style="max-width:100%;">' if product['image'] else ''}
                    </div>
                    ''',
                    pubdate=datetime.datetime.now()
                )
            
            # Salva feed
            output_folder = self.config["output_folder"]
            os.makedirs(output_folder, exist_ok=True)
            
            filename = f"{site_name.lower().replace(' ', '_')}_promocoes.xml"
            filepath = os.path.join(output_folder, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                feed.write(f, 'utf-8')
            
            feed_files.append(filepath)
        
        self.stats["total_feeds_generated"] += len(feed_files)
        return feed_files
    
    def process_interval(self):
        """Processa um intervalo de tempo"""
        self.logger.info(f"=== Processando intervalo {datetime.datetime.now().strftime('%H:%M')} ===")
        
        # Reseta contador diário se necessário
        self.reset_daily_counter_if_needed()
        
        # Busca produtos
        products = self.get_all_products()
        
        if not products:
            self.logger.warning("Nenhum produto encontrado")
            return
        
        # Cria feeds
        feeds = self.create_feed(products)
        self.logger.info(f"Feeds criados: {len(feeds)}")
        
        # Envia para WhatsApp se habilitado
        if self.config["whatsapp"]["enabled"]:
            self.send_to_whatsapp(products)
        
        # Atualiza estatísticas
        self.stats["last_update"] = datetime.datetime.now().isoformat()
        next_update = datetime.datetime.now() + timedelta(
            hours=self.config["update_settings"]["interval_hours"]
        )
        self.stats["next_update"] = next_update.isoformat()
        self.save_stats()
        
        self.logger.info(f"Intervalo processado. Próximo: {next_update.strftime('%H:%M')}")
    
    def send_to_whatsapp(self, products):
        """Envia produtos para WhatsApp"""
        if not products or not self.config["whatsapp"]["phone_numbers"]:
            return
        
        # Calcula quantos produtos enviar neste intervalo
        products_per_interval = self.config["whatsapp"]["products_per_interval"]
        products_to_send = products[:products_per_interval]
        
        # Verifica limite diário
        remaining_daily = self.config["whatsapp"]["daily_limit"] - self.stats["whatsapp_stats"]["sent_today"]
        products_to_send = products_to_send[:remaining_daily]
        
        if not products_to_send:
            self.logger.info("Limite diário atingido ou sem produtos para enviar")
            return
        
        self.logger.info(f"Enviando {len(products_to_send)} produtos para WhatsApp")
        
        # Envia para cada número
        for phone in self.config["whatsapp"]["phone_numbers"]:
            for product in products_to_send:
                success = self.send_whatsapp_message(phone, product)
                if success:
                    time.sleep(2)  # Delay entre envios
                else:
                    self.logger.error(f"Falha ao enviar para {phone}")
                    break
    
    def reset_daily_counter_if_needed(self):
        """Reseta contadores diários se passou um dia"""
        now = datetime.datetime.now()
        if now.date() > self.last_reset.date():
            self.stats["whatsapp_stats"]["sent_today"] = 0
            self.stats["whatsapp_stats"]["failed_today"] = 0
            self.last_reset = now
            
            # Salva estatísticas do dia anterior
            yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            self.stats["daily_stats"][yesterday] = {
                "sent": self.stats["whatsapp_stats"]["sent_today"],
                "failed": self.stats["whatsapp_stats"]["failed_today"],
                "total_products": self.stats["total_products_found"]
            }
            
            self.save_stats()
            self.logger.info("Contadores diários resetados")
    
    def schedule_updates(self):
        """Agenda atualizações baseado no intervalo"""
        if not self.config.get("setup_completed", False):
            return
        
        interval_hours = self.config["update_settings"]["interval_hours"]
        
        # Limpa agendamentos anteriores
        schedule.clear()
        
        # Agenda a cada X horas
        schedule.every(interval_hours).hours.do(self.process_interval)
        
        # Se tem horários específicos para WhatsApp, agenda também
        if self.config["whatsapp"]["enabled"] and self.config["whatsapp"]["send_times"]:
            for send_time in self.config["whatsapp"]["send_times"]:
                schedule.every().day.at(send_time).do(self.process_interval)
        
        # Executa imediatamente se configurado
        if self.config["update_settings"]["start_immediately"]:
            self.process_interval()
        
        self.logger.info(f"Sistema agendado. Intervalo: {interval_hours}h")
        self.logger.info(f"Horários WhatsApp: {self.config['whatsapp']['send_times']}")
        
        # Loop principal do agendador
        while True:
            schedule.run_pending()
            
            # Adiciona delay aleatório se configurado
            delay = self.config["update_settings"].get("random_delay_minutes", 0)
            if delay > 0:
                time.sleep(random.randint(60, delay * 60))
            else:
                time.sleep(60)

# Inicializa sistema
system = AdvancedAffiliateSystem()

# Cria aplicação Flask
app = Flask(__name__)
CORS(app)

# Middleware
@app.before_request
def check_setup():
    allowed = ['/setup', '/api/setup', '/static/', '/favicon.ico', '/api/health']
    if any(request.path.startswith(p) for p in allowed):
        return
    if not system.config.get("setup_completed", False):
        return redirect(url_for('setup_page'))

# Rotas
@app.route('/')
def index():
    return render_template('index.html', config=system.config, stats=system.stats)

@app.route('/setup')
def setup_page():
    if system.config.get("setup_completed", False):
        return redirect(url_for('index'))
    return render_template('setup.html')

# API Routes
@app.route('/api/config', methods=['GET', 'POST'])
def config_api():
    if request.method == 'POST':
        data = request.json
        system.config.update(data)
        system.save_config()
        return jsonify({'status': 'success', 'config': system.config})
    return jsonify(system.config)

@app.route('/api/stats', methods=['GET'])
def stats_api():
    return jsonify(system.stats)

@app.route('/api/sites', methods=['GET', 'POST', 'DELETE'])
def sites_api():
    if request.method == 'POST':
        data = request.json
        site = system.add_custom_site(data)
        return jsonify({'status': 'success', 'site': site})
    
    elif request.method == 'DELETE':
        site_name = request.args.get('name')
        system.config['custom_sites'] = [
            s for s in system.config['custom_sites'] 
            if s['name'] != site_name
        ]
        system.save_config()
        return jsonify({'status': 'success'})
    
    return jsonify({'sites': system.config['custom_sites']})

@app.route('/api/whatsapp/numbers', methods=['POST'])
def whatsapp_numbers_api():
    data = request.json
    system.config['whatsapp']['phone_numbers'] = data.get('numbers', [])
    system.save_config()
    return jsonify({'status': 'success'})

@app.route('/api/whatsapp/api-key', methods=['POST'])
def whatsapp_api_key_api():
    data = request.json
    api_key = data.get('api_key')
    expires = data.get('expires_hours', 24)
    
    if api_key:
        system.update_whatsapp_api_key(api_key, expires)
        return jsonify({'status': 'success'})
    
    return jsonify({'status': 'error', 'message': 'API key required'})

@app.route('/api/process/now', methods=['POST'])
def process_now_api():
    try:
        system.process_interval()
        return jsonify({'status': 'success', 'message': 'Processamento iniciado'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/test/whatsapp', methods=['POST'])
def test_whatsapp_api():
    data = request.json
    phone = data.get('phone')
    message = data.get('message', 'Teste do sistema automático! ✅')
    
    if not phone:
        return jsonify({'status': 'error', 'message': 'Número requerido'})
    
    success = system.send_whatsapp_via_web(phone, message)
    if success:
        return jsonify({'status': 'success', 'message': 'Teste enviado'})
    else:
        return jsonify({'status': 'error', 'message': 'Falha no envio'})

@app.route('/api/feeds', methods=['GET'])
def feeds_api():
    feeds = []
    output_folder = system.config['output_folder']
    if os.path.exists(output_folder):
        for file in os.listdir(output_folder):
            if file.endswith('.xml'):
                feeds.append({
                    'name': file,
                    'url': f'/feeds/{file}',
                    'size': os.path.getsize(os.path.join(output_folder, file))
                })
    return jsonify({'feeds': feeds})

@app.route('/feeds/<filename>')
def serve_feed(filename):
    return send_from_directory(system.config['output_folder'], filename)

@app.route('/api/health', methods=['GET'])
def health_api():
    return jsonify({
        'status': 'healthy',
        'setup_completed': system.config.get('setup_completed', False),
        'whatsapp_enabled': system.config['whatsapp']['enabled'],
        'sites_count': len(system.config['custom_sites']),
        'last_update': system.stats.get('last_update')
    })

def start_scheduler():
    system.schedule_updates()

if __name__ == "__main__":
    # Cria pastas
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    os.makedirs('feeds', exist_ok=True)
    os.makedirs('data', exist_ok=True)
    
    # Inicia sistema
    print("\n" + "="*70)
    print("🤖 SISTEMA AVANÇADO DE FEEDS RSS + WHATSAPP AUTOMÁTICO")
    print("="*70)
    
    if system.is_first_run:
        print("\n🎯 CONFIGURAÇÃO INICIAL REQUERIDA")
        print("Acesse: http://localhost:5000/setup")
        print("\n📋 O que configurar:")
        print("1. Sites personalizados + códigos de afiliado")
        print("2. Números de WhatsApp para envio")
        print("3. Chave API WhatsApp Business (24h)")
        print("4. Intervalos e limites")
        print("5. Filtros e categorias")
    else:
        print(f"\n✅ Sistema configurado com {len(system.config['custom_sites'])} sites")
        print(f"📱 WhatsApp: {'Ativo' if system.config['whatsapp']['enabled'] else 'Inativo'}")
        print(f"⏰ Intervalo: {system.config['update_settings']['interval_hours']} horas")
        print(f"🔗 Feeds disponíveis em: http://localhost:5000/feeds/")
        
        # Inicia agendador
        scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
        scheduler_thread.start()
    
    print("\n🌐 Interface: http://localhost:5000")
    print("="*70 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)