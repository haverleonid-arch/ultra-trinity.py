# -*- coding: utf-8 -*-
import requests
import sqlite3
import time
from datetime import datetime, timezone

# --- ЖЕСТКАЯ КОНФИГУРАЦИЯ ---
API_KEY = "ac1eae60740a1e6a4e987c7577539963"
HEADERS = {"x-apisports-key": API_KEY}
BASE_URL = "https://v3.football.api-sports.io"
DB_NAME = "radar_nexus.db"
DROP_THRESHOLD = 0.10  # 10% падения кэфа = Инсайдерский прогруз

# --- ТЕЛЕГРАМ КОНФИГУРАЦИЯ ---
TG_TOKEN = "8603529040:AAG2ZvdFjyo4L6JlrpGVQcoksDsIQdhOl4M"
TG_CHAT_ID = "8301693491"

# --- МАТРИЦА БУКМЕКЕРОВ ---
BOOKMAKERS = {
    17: "Pinnacle (Smart Money)",
    8: "Bet365 (World Classic)",
    1: "1xBet (Mass Market)"
}

class DropOddsRadar:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME)
        self.cursor = self.conn.cursor()
        self._init_db()

    def _init_db(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS live_tracking (
                fixture_id INTEGER,
                bookmaker_id INTEGER,
                league_id INTEGER,
                match_time TEXT,
                home_team TEXT,
                away_team TEXT,
                initial_odd_1 REAL,
                initial_odd_2 REAL,
                current_odd_1 REAL,
                current_odd_2 REAL,
                last_update TEXT,
                PRIMARY KEY (fixture_id, bookmaker_id)
            )
        ''')
        self.conn.commit()

    def send_tg_alert(self, match_time, home, away, bookmaker_id, target, initial, current, drop_percent):
        bm_name = BOOKMAKERS.get(bookmaker_id, f"ID {bookmaker_id}")
        
        msg = (
            f" <b>�АНОМАЛИЯ SMART MONEY</b> \n\n"
            f"�⚽️ <i>{home} — {away}</i>\n"
            f" <b>�Начало:</b> {match_time} (UTC)\n\n"
            f" <b>�Прогруз на:</b> {target}\n"
            f" <b>�Радар:</b> {bm_name}\n"
            f" <b>�Обвал:</b> {initial} ➔ {current} (<b>-{drop_percent:.1f}%</b>)\n\n"
            f"⚡️ <i>MATH-TRINITY NEXUS</i>"
        )
        
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        payload = {
            "chat_id": TG_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code != 200:
                print(f"Ошибка отправки TG: {resp.text}")
        except Exception as e:
            print(f"Сбой сети при отправке TG: {e}")

    def scan_upcoming_matches(self):
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Запрос расписания на {today_str}...")
        
        try:
            resp = requests.get(f"{BASE_URL}/fixtures?date={today_str}&timezone=Europe/London", headers=HEADERS, timeout=15).json()
            fixtures = resp.get('response', [])
        except Exception as e:
            print(f"Ошибка получения расписания: {e}")
            return []
        
        now = datetime.now(timezone.utc)
        upcoming = []
        
        for f in fixtures:
            if f['fixture']['status']['short'] == 'NS':
                match_time = datetime.fromtimestamp(f['fixture']['timestamp'], tz=timezone.utc)
                time_diff = (match_time - now).total_seconds() / 3600
                
                if 0 < time_diff <= 12:
                    upcoming.append(f)
        return upcoming

    def track_odds(self, fixtures):
        if not fixtures:
            print("Нет матчей в активном окне.")
            return

        print(f"В радаре {len(fixtures)} матчей. Сканирование Матрицы Букмекеров...")
        
        for f in fixtures:
            f_id = f['fixture']['id']
            match_time = f['fixture']['date']
            home_team = f['teams']['home']['name']
            away_team = f['teams']['away']['name']
            league_id = f['league']['id']

            try:
                odds_resp = requests.get(f"{BASE_URL}/odds?fixture={f_id}", headers=HEADERS, timeout=10).json()
                odds_data = odds_resp.get('response', [])
                if not odds_data: continue

                all_bookmakers = odds_data[0].get('bookmakers', [])
                for bm_id in BOOKMAKERS.keys():
                    bm = next((b for b in all_bookmakers if b['id'] == bm_id), None)
                    if not bm: continue
                        
                    bets = bm.get('bets', [])
                    mw = next((b for b in bets if b['id'] == 1), None)
                    if mw:
                        values = mw.get('values', [])
                        odd_1 = next((float(v['odd']) for v in values if v['value'] == 'Home'), 0.0)
                        odd_2 = next((float(v['odd']) for v in values if v['value'] == 'Away'), 0.0)
                        if odd_1 > 0 and odd_2 > 0:
                            self._analyze_drop(f_id, bm_id, league_id, match_time, home_team, away_team, odd_1, odd_2)
            except Exception as e:
                print(f"Сбой парсинга фикстуры {f_id}: {e}")
            time.sleep(0.2)

    def _analyze_drop(self, f_id, bm_id, league_id, match_time, home_team, away_team, odd_1, odd_2):
        now_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self.cursor.execute("SELECT initial_odd_1, initial_odd_2 FROM live_tracking WHERE fixture_id = ? AND bookmaker_id = ?", (f_id, bm_id))
        row = self.cursor.fetchone()

        if not row:
            self.cursor.execute('''
                INSERT INTO live_tracking (fixture_id, bookmaker_id, league_id, match_time, home_team, away_team, initial_odd_1, initial_odd_2, current_odd_1, current_odd_2, last_update)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (f_id, bm_id, league_id, match_time, home_team, away_team, odd_1, odd_2, odd_1, odd_2, now_str))
            self.conn.commit()
        else:
            init_1, init_2 = row
            drop_1 = (init_1 - odd_1) / init_1 if init_1 > 0 else 0
            drop_2 = (init_2 - odd_2) / init_2 if init_2 > 0 else 0

            self.cursor.execute('''
                UPDATE live_tracking SET current_odd_1 = ?, current_odd_2 = ?, last_update = ? WHERE fixture_id = ? AND bookmaker_id = ?
            ''', (odd_1, odd_2, now_str, f_id, bm_id))
            self.conn.commit()

            if drop_1 >= DROP_THRESHOLD:
                print(f"[!] ALERT: {home_team} П1 (-{drop_1*100:.1f}%)")
                self.send_tg_alert(match_time, home_team, away_team, bm_id, "П1 (Хозяева)", init_1, odd_1, drop_1*100)
                self.cursor.execute("UPDATE live_tracking SET initial_odd_1 = ? WHERE fixture_id = ? AND bookmaker_id = ?", (odd_1, f_id, bm_id))
                self.conn.commit()
            elif drop_2 >= DROP_THRESHOLD:
                print(f"[!] ALERT: {away_team} П2 (-{drop_2*100:.1f}%)")
                self.send_tg_alert(match_time, home_team, away_team, bm_id, "П2 (Гости)", init_2, odd_2, drop_2*100)
                self.cursor.execute("UPDATE live_tracking SET initial_odd_2 = ? WHERE fixture_id = ? AND bookmaker_id = ?", (odd_2, f_id, bm_id))
                self.conn.commit()

if __name__ == "__main__":
    radar = DropOddsRadar()
    matches = radar.scan_upcoming_matches()
    radar.track_odds(matches)
