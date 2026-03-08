#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RavenQuest Legacy Tracker - Scraper Corrigido
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import os
import re
import time
import traceback
import sys
import tempfile
import shutil
import requests

# CONFIGURAÇÃO
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://SEU-PROJETO.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'SUA-SERVICE-ROLE-KEY-AQUI')

CONFIG = {
    'top': 50,
    'url': 'https://ravenquest.io/pt/leaderboard/game/legacy',
    'debug': True,
    'max_retries': 3
}

def supabase_request(method, endpoint, data=None):
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'resolution=merge-duplicates'
    }
    
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, timeout=30)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        return response.json() if response.text else []
    except Exception as e:
        print(f"[ERRO Supabase] {e}")
        return None

def save_players_batch(players):
    if not players:
        return False
    
    now = datetime.now().isoformat()
    players_data = [{'rank': p['rank'], 'name': p['name'], 'level': p['level'], 'exp': p['exp'], 'updated_at': now} for p in players]
    history_data = [{'player_name': p['name'], 'rank': p['rank'], 'level': p['level'], 'exp': p['exp'], 'recorded_at': now} for p in players]
    
    print(f"[INFO] Salvando {len(players_data)} jogadores...")
    result = supabase_request('POST', 'players', players_data)
    if result is None:
        return False
    
    supabase_request('POST', 'history', history_data)
    print(f"[OK] {len(players_data)} jogadores salvos")
    return True

def parse_exp(v):
    if not v: 
        return 0
    s = str(v).strip().upper().replace(',', '.').replace(' ', '').replace('.', '')
    mult = {'B': 1e9, 'M': 1e6, 'K': 1e3, 'BIL': 1e9, 'MIL': 1e6}
    for k, m in mult.items():
        if k in s:
            try: 
                return int(float(s.replace(k, '').replace(',', '.')) * m)
            except: 
                return 0
    try: 
        return int(float(s))
    except: 
        return 0

def fmt_exp(n):
    if n >= 1e9: return f"{n/1e9:.2f}B"
    if n >= 1e6: return f"{n/1e6:.2f}M"
    if n >= 1e3: return f"{n/1e3:.2f}K"
    return str(n)

def scrape():
    print("=" * 70)
    print("RAVENQUEST LEGACY TRACKER")
    print(f"Início: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 70)
    
    driver = None
    user_data_dir = None
    
    try:
        print("[INFO] Iniciando navegador...")
        user_data_dir = tempfile.mkdtemp(prefix='chrome_rq_')
        
        options = Options()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument(f'--user-data-dir={user_data_dir}')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        options.add_argument('--log-level=3')
        
        service = Service()
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(45)

        print(f"[INFO] Acessando: {CONFIG['url']}")
        driver.get(CONFIG['url'])
        
        print("[INFO] Aguardando 30s para renderização...")
        time.sleep(30)

        # SELETORES CORRETOS PARA RAVENQUEST
        selectors = [
            ".table.legacy-level .tbody .tr",
            ".table .tbody .tr",
            ".legacy-level .tr",
        ]
        
        rows = []
        for selector in selectors:
            try:
                wait = WebDriverWait(driver, 10)
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                rows = driver.find_elements(By.CSS_SELECTOR, selector)
                if len(rows) >= 10:
                    print(f"[OK] Tabela: {selector} ({len(rows)} linhas)")
                    break
            except:
                continue
        
        if not rows:
            print("[ERRO] Tabela não encontrada")
            return []

        # EXTRAÇÃO DOS DADOS
        players = []
        for idx, row in enumerate(rows[:CONFIG['top']]):
            try:
                cells = row.find_elements(By.CSS_SELECTOR, ".td")
                if len(cells) < 4:
                    continue
                
                rank_text = cells[0].text.strip()
                name = cells[1].text.strip()
                level_text = cells[2].text.strip()
                exp_text = cells[3].text.strip()
                
                # Rank
                rank = idx + 1
                if rank_text.isdigit():
                    rank = int(rank_text)
                
                # Level
                level_match = re.search(r'(\d+)', level_text)
                level = int(level_match.group(1)) if level_match else 0
                
                # XP
                exp = parse_exp(exp_text)
                
                if name and level > 0:
                    players.append({
                        'rank': rank,
                        'name': name,
                        'level': level,
                        'exp': exp
                    })
                    print(f"[OK] #{rank} {name} (Lv{level}, {fmt_exp(exp)})")
                    
            except Exception as e:
                print(f"[ERRO] Linha {idx}: {e}")

        print(f"[OK] Total: {len(players)} jogadores")
        return players

    except Exception as e:
        print(f"[ERRO GRAVE] {e}")
        traceback.print_exc()
        return []
        
    finally:
        if driver:
            driver.quit()
        if user_data_dir and os.path.exists(user_data_dir):
            shutil.rmtree(user_data_dir, ignore_errors=True)

if __name__ == "__main__":
    try:
        # Testa conexão
        test = supabase_request('GET', 'players?limit=1')
        if test is None:
            print("[ERRO] Não conectou ao Supabase")
            sys.exit(1)
        
        players = scrape()
        if players and save_players_batch(players):
            print("[OK] Concluído!")
            sys.exit(0)
        else:
            print("[ERRO] Falha")
            sys.exit(1)
            
    except Exception as e:
        print(f"[ERRO CRÍTICO] {e}")
        sys.exit(1)