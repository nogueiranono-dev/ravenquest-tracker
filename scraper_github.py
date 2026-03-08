#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
import sys
import requests

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

def save_to_supabase(players):
    if not players:
        return False
    
    now = datetime.now().isoformat()
    
    # Prepara dados
    players_data = [{
        'rank': p['rank'],
        'name': p['name'],
        'level': p['level'],
        'exp': p['exp'],
        'updated_at': now
    } for p in players]
    
    history_data = [{
        'player_name': p['name'],
        'rank': p['rank'],
        'level': p['level'],
        'exp': p['exp'],
        'recorded_at': now
    } for p in players]
    
    # Insere players via POST simples
    url = f"{SUPABASE_URL}/rest/v1/players"
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json'
    }
    
    # Tenta limpar primeiro (ignora erro)
    try:
        requests.delete(url, headers={**headers, 'Prefer': 'return=minimal'}, timeout=10)
    except:
        pass
    
    # Insere novo
    try:
        r = requests.post(url, headers=headers, json=players_data, timeout=30)
        print(f"Players insert: {r.status_code}")
        if r.status_code >= 400:
            print(f"Error: {r.text[:200]}")
            return False
    except Exception as e:
        print(f"Players error: {e}")
        return False
    
    # Insere history
    try:
        r = requests.post(f"{SUPABASE_URL}/rest/v1/history", headers=headers, json=history_data, timeout=30)
        print(f"History insert: {r.status_code}")
    except Exception as e:
        print(f"History error: {e}")
    
    return True

def parse_exp(v):
    if not v: 
        return 0
    s = str(v).strip().upper().replace(',', '.').replace(' ', '').replace('.', '')
    mult = {'B': 1e9, 'M': 1e6, 'K': 1e3}
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

def scrape():
    print("Iniciando scraper...")
    
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.binary_location = '/usr/bin/chromium-browser'
    
    driver = webdriver.Chrome(service=Service('/usr/bin/chromedriver'), options=options)
    driver.get('https://ravenquest.io/pt/leaderboard/game/legacy')
    time.sleep(30)
    
    rows = driver.find_elements(By.CSS_SELECTOR, ".table.legacy-level .tbody .tr, .table .tbody .tr")
    print(f"Encontradas {len(rows)} linhas")
    
    players = []
    for idx, row in enumerate(rows[:50]):
        try:
            cells = row.find_elements(By.CSS_SELECTOR, ".td")
            if len(cells) < 4:
                continue
            
            rank = int(cells[0].text) if cells[0].text.strip().isdigit() else idx + 1
            name = cells[1].text.strip()
            level = int(re.search(r'\d+', cells[2].text).group()) if re.search(r'\d+', cells[2].text) else 0
            exp = parse_exp(cells[3].text)
            
            if name:
                players.append({'rank': rank, 'name': name, 'level': level, 'exp': exp})
                print(f"#{rank} {name}")
        except:
            pass
    
    driver.quit()
    return players

if __name__ == "__main__":
    players = scrape()
    print(f"Total: {len(players)}")
    
    if players and save_to_supabase(players):
        print("OK!")
        sys.exit(0)
    else:
        print("Falha")
        sys.exit(1)