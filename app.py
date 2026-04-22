# app.py - Instagram DOX API без API ключей, полный сбор данных
# Деплой на Vercel: готовый рабочий код

import os
import re
import json
import time
import requests
import hashlib
import random
from datetime import datetime
from flask import Flask, request, jsonify
from flask_caching import Cache

app = Flask(__name__)
cache = Cache(app, config={'CACHE_TYPE': 'simple', 'CACHE_DEFAULT_TIMEOUT': 300})

# ============================================================
# РОТАЦИЯ USER-AGENT ДЛЯ ОБХОДА БЛОКИРОВОК
# ============================================================
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
]

def get_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0'
    }

# ============================================================
# ОСНОВНОЙ ПАРСИНГ INSTAGRAM (БЕЗ API КЛЮЧЕЙ)
# ============================================================
def extract_json_from_html(html):
    """Извлечение JSON данных из HTML страницы"""
    patterns = [
        r'window\._sharedData\s*=\s*({.*?});</script>',
        r'<script type="application/json">([^<]+)</script>',
        r'window\.__additionalDataLoaded\s*\(\s*[\'"]feed[\'"]\s*,\s*({.*?})\s*\);'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                continue
    return None

def parse_instagram_profile(username):
    """Полный парсинг профиля Instagram с извлечением всех данных"""
    url = f'https://www.instagram.com/{username}/'
    
    session = requests.Session()
    session.headers.update(get_headers())
    
    # Первый запрос для получения cookies
    try:
        resp = session.get('https://www.instagram.com/', timeout=10)
        resp.raise_for_status()
    except:
        pass
    
    # Основной запрос профиля
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code != 200:
            return None
    except:
        return None
    
    html = resp.text
    
    # Проверка на блокировку
    if 'login' in html.lower() and 'challenge' in html.lower():
        return {'error': 'instagram_blocked', 'message': 'Требуется решение CAPTCHA'}
    
    json_data = extract_json_from_html(html)
    if not json_data:
        return None
    
    # Навигация по структуре JSON
    user_data = None
    try:
        if 'entry_data' in json_data:
            user_data = json_data['entry_data']['ProfilePage'][0]['graphql']['user']
        elif 'graphql' in json_data:
            user_data = json_data['graphql']['user']
        elif 'user' in json_data:
            user_data = json_data['user']
    except (KeyError, IndexError, TypeError):
        return None
    
    if not user_data:
        return None
    
    # Извлечение мета-тегов из HTML
    meta_data = {}
    meta_patterns = {
        'description': r'<meta name="description" content="([^"]+)"',
        'keywords': r'<meta name="keywords" content="([^"]+)"',
        'author': r'<meta name="author" content="([^"]+)"'
    }
    
    for key, pattern in meta_patterns.items():
        match = re.search(pattern, html)
        if match:
            meta_data[key] = match.group(1)
    
    # Извлечение ссылок из биографии
    bio = user_data.get('biography', '')
    extracted_links = re.findall(r'https?://[^\s]+', bio)
    
    # Формирование результата
    result = {
        'username': user_data.get('username'),
        'user_id': user_data.get('id'),
        'full_name': user_data.get('full_name'),
        'bio': bio,
        'bio_links': extracted_links,
        'external_url': user_data.get('external_url'),
        'followers_count': user_data.get('edge_followed_by', {}).get('count', 0),
        'following_count': user_data.get('edge_follow', {}).get('count', 0),
        'posts_count': user_data.get('edge_owner_to_timeline_media', {}).get('count', 0),
        'is_private': user_data.get('is_private', False),
        'is_verified': user_data.get('is_verified', False),
        'is_business': user_data.get('is_business_account', False),
        'business_category': user_data.get('business_category_name'),
        'business_email': user_data.get('business_email'),
        'business_phone': user_data.get('business_phone_number'),
        'profile_pic_url': user_data.get('profile_pic_url_hd', user_data.get('profile_pic_url', '')),
        'profile_pic_url_small': user_data.get('profile_pic_url'),
        'connected_fb_page': user_data.get('connected_fb_page'),
        'fb_page_id': user_data.get('fbid'),
        'has_ar_effects': user_data.get('has_ar_effects', False),
        'has_clips': user_data.get('has_clips', False),
        'has_guides': user_data.get('has_guides', False),
        'is_joined_recently': user_data.get('is_joined_recently', False),
        'account_type': user_data.get('account_type'),
        'category': user_data.get('category'),
        'category_enum': user_data.get('category_enum'),
        'city': user_data.get('city'),
        'city_id': user_data.get('city_id'),
        'address_street': user_data.get('address_street'),
        'zip': user_data.get('zip'),
        'latitude': user_data.get('latitude'),
        'longitude': user_data.get('longitude'),
        'public_email': user_data.get('public_email'),
        'public_phone_country_code': user_data.get('public_phone_country_code'),
        'public_phone_number': user_data.get('public_phone_number'),
        'contact_phone_number': user_data.get('contact_phone_number'),
        'page_name': user_data.get('page_name'),
        'show_business_category': user_data.get('show_business_category', False),
        'show_conversion_edit_entry': user_data.get('show_conversion_edit_entry', False),
        'show_insights_terms': user_data.get('show_insights_terms', False),
        'translations': user_data.get('translations', []),
        'description': meta_data.get('description', ''),
        'keywords': meta_data.get('keywords', ''),
        'author': meta_data.get('author', '')
    }
    
    return result

# ============================================================
# ПОИСК ПО ДРУГИМ СОЦСЕТЯМ (OSINT)
# ============================================================
def search_username_across_platforms(username):
    """Поиск username на 20+ платформах"""
    platforms = {
        'twitter': f'https://twitter.com/{username}',
        'tiktok': f'https://tiktok.com/@{username}',
        'youtube': f'https://youtube.com/@{username}',
        'github': f'https://github.com/{username}',
        'telegram': f'https://t.me/{username}',
        'vk': f'https://vk.com/{username}',
        'facebook': f'https://facebook.com/{username}',
        'reddit': f'https://reddit.com/user/{username}',
        'pinterest': f'https://pinterest.com/{username}',
        'snapchat': f'https://snapchat.com/add/{username}',
        'discord': f'https://discord.com/users/{username}',
        'twitch': f'https://twitch.tv/{username}',
        'patreon': f'https://patreon.com/{username}',
        'medium': f'https://medium.com/@{username}',
        'quora': f'https://quora.com/profile/{username}',
        'linkedin': f'https://linkedin.com/in/{username}',
        'instagram': f'https://instagram.com/{username}',
        'tumblr': f'https://{username}.tumblr.com',
        'flickr': f'https://flickr.com/people/{username}',
        'behance': f'https://behance.net/{username}',
        'dribbble': f'https://dribbble.com/{username}',
        'soundcloud': f'https://soundcloud.com/{username}',
        'spotify': f'https://open.spotify.com/user/{username}',
        'steam': f'https://steamcommunity.com/id/{username}',
        'xbox': f'https://xboxgamertag.com/search/{username}',
        'psn': f'https://psnprofiles.com/{username}',
        'hackernews': f'https://news.ycombinator.com/user?id={username}',
        'keybase': f'https://keybase.io/{username}',
        'pastebin': f'https://pastebin.com/u/{username}',
        'codepen': f'https://codepen.io/{username}',
        'replit': f'https://replit.com/@{username}',
        'gitlab': f'https://gitlab.com/{username}',
        'bitbucket': f'https://bitbucket.org/{username}',
        'periscope': f'https://periscope.tv/{username}',
        'vine': f'https://vine.co/{username}',
        'ello': f'https://ello.co/{username}',
        'mastodon': f'https://mastodon.social/@{username}'
    }
    
    found = []
    headers = get_headers()
    
    for platform, url in platforms.items():
        try:
            resp = requests.head(url, timeout=3, headers=headers, allow_redirects=True)
            if resp.status_code == 200:
                found.append({'platform': platform, 'url': url, 'status': 'active'})
            elif resp.status_code == 302 or resp.status_code == 301:
                found.append({'platform': platform, 'url': url, 'status': 'redirects'})
        except:
            continue
    
    return found

# ============================================================
# АНАЛИЗ EMAIL (HIBP STYLE)
# ============================================================
def check_email_breaches(email):
    """Проверка email в публичных утечках (без API ключа)"""
    # Используем публичные API без ключа
    services = [
        f'https://scylla.so/search?q={email}',
        f'https://leak-lookup.com/api/search?query={email}'
    ]
    
    breaches = []
    for service in services:
        try:
            resp = requests.get(service, timeout=5, headers=get_headers())
            if resp.status_code == 200:
                breaches.append({'source': service.split('/')[2], 'found': True})
        except:
            continue
    
    return breaches

# ============================================================
# ОСНОВНОЙ API ЭНДПОИНТ
# ============================================================
@app.route('/api/dox', methods=['GET'])
@cache.cached(query_string=True)
def full_dox():
    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'Missing username parameter', 'usage': '/api/dox?username=xxx'}), 400
    
    # Очистка username
    username = re.sub(r'[^a-zA-Z0-9_.]', '', username.strip().lower())
    if not username or len(username) < 2:
        return jsonify({'error': 'Invalid username (min 2 chars)'}), 400
    
    result = {
        'query': {
            'username': username,
            'timestamp': datetime.utcnow().isoformat(),
            'timestamp_unix': int(time.time())
        },
        'instagram': {},
        'social_media': [],
        'email_breaches': [],
        'statistics': {
            'platforms_found': 0,
            'data_completeness': 0
        }
    }
    
    # Парсинг Instagram
    ig_data = parse_instagram_profile(username)
    if ig_data:
        result['instagram'] = ig_data
        
        # Если есть email в бизнес-аккаунте
        if ig_data.get('business_email'):
            result['email_breaches'] = check_email_breaches(ig_data['business_email'])
        if ig_data.get('public_email'):
            result['email_breaches'] = check_email_breaches(ig_data['public_email'])
    
    # Поиск по другим платформам
    result['social_media'] = search_username_across_platforms(username)
    result['statistics']['platforms_found'] = len(result['social_media'])
    
    # Расчет completeness
    completeness = 0
    if ig_data and ig_data.get('followers_count', 0) > 0:
        completeness += 25
    if ig_data and ig_data.get('business_email'):
        completeness += 25
    if ig_data and ig_data.get('external_url'):
        completeness += 15
    if len(result['social_media']) > 3:
        completeness += 20
    if ig_data and ig_data.get('business_phone'):
        completeness += 15
    result['statistics']['data_completeness'] = min(completeness, 100)
    
    return jsonify(result)

@app.route('/api/basic', methods=['GET'])
def basic_info():
    """Упрощенный эндпоинт - только базовая информация"""
    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'Missing username'}), 400
    
    username = re.sub(r'[^a-zA-Z0-9_.]', '', username.strip().lower())
    ig_data = parse_instagram_profile(username)
    
    if not ig_data:
        return jsonify({'error': 'Profile not found or private'}), 404
    
    return jsonify({
        'username': ig_data.get('username'),
        'full_name': ig_data.get('full_name'),
        'followers': ig_data.get('followers_count'),
        'following': ig_data.get('following_count'),
        'posts': ig_data.get('posts_count'),
        'is_private': ig_data.get('is_private'),
        'is_verified': ig_data.get('is_verified'),
        'bio': ig_data.get('bio'),
        'external_url': ig_data.get('external_url'),
        'profile_pic': ig_data.get('profile_pic_url')
    })

@app.route('/api/contacts', methods=['GET'])
def contacts():
    """Эндпоинт для получения контактных данных"""
    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'Missing username'}), 400
    
    username = re.sub(r'[^a-zA-Z0-9_.]', '', username.strip().lower())
    ig_data = parse_instagram_profile(username)
    
    if not ig_data:
        return jsonify({'error': 'Profile not found'}), 404
    
    return jsonify({
        'username': username,
        'email': ig_data.get('business_email') or ig_data.get('public_email'),
        'phone': ig_data.get('business_phone') or ig_data.get('public_phone_number'),
        'address': {
            'street': ig_data.get('address_street'),
            'city': ig_data.get('city'),
            'zip': ig_data.get('zip'),
            'latitude': ig_data.get('latitude'),
            'longitude': ig_data.get('longitude')
        },
        'external_url': ig_data.get('external_url'),
        'bio_links': ig_data.get('bio_links', [])
    })

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'name': 'Instagram DOX API',
        'version': '2.0',
        'description': 'Получение данных Instagram без API ключей',
        'endpoints': {
            '/api/dox?username=xxx': 'Полный DOX отчет (все данные)',
            '/api/basic?username=xxx': 'Базовая информация о профиле',
            '/api/contacts?username=xxx': 'Контактные данные (email, phone, address)',
            '/api/health': 'Проверка статуса API'
        },
        'example': 'https://your-domain.vercel.app/api/dox?username=durov',
        'note': 'Для бизнес-аккаунтов доступны email и телефон'
    })

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'operational',
        'timestamp': datetime.utcnow().isoformat(),
        'cache_enabled': True
    })

# ============================================================
# ЗАПУСК (локальный или Vercel)
# ============================================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
