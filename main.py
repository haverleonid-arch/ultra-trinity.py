# -*- coding: utf-8 -*-
import requests
import sqlite3
import time
import os
from datetime import datetime, timezone

# --- CONFIG ---
API_KEY = "ac1eae60740a1e6a4e987c7577539963"
HEADERS = {"x-apisports-key": API_KEY}
BASE_URL = "https://v3.football.api-sports.io"
DB_NAME = "radar_nexus.db"
DROP_THRESHOLD = 0.10

# --- TELEGRAM ---
TG_TOKEN = "8603529040:AAG2ZvdFjyo4L6JlrpGVQcoksDsIQdhOl4M"
TG_CHAT_ID = "8301693491"

BOOKMAKERS = {
    17: "Pinnacle (Smart Money)",
    8: "Bet365 (World Classic)",
    1: "1xBet (Mass Market)"
}

class DropOddsRadar:
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(__file__), DB_NAME)
        self.conn = sqlite3.connect(self.db_path)
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
            f"!!! SHARP SIGNAL DETECTED !!!\n\n"
            f"Match: {home} - {away}\n"
            f"Start: {match_time} (UTC)\n\n"
            f"Target: {target}\n"
            f"Radar: {bm_name}\n"
            f"Drop: {initial} -> {current} (-{drop_percent:.1f}%)\n\n"
            f"System: MATH-TRINITY NEXUS"
        )
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        payload = {"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "HTML"}
        try:
            requests.post(url, json=payload, timeout=10)
        except:
            pass

    def scan_upcoming_matches(self):
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] SCANNING: {today_str}")
        try:
            resp = requests.get(f"{BASE_URL}/fixtures?date={today_str}&timezone=Europe/London", headers=HEADERS, timeout=15).json()
            return resp.get('response', [])
        except:
            return []

    def track_odds(self, fixtures):
        if not fixtures: return
        now = datetime.now(timezone.utc)
        for f in fixtures:
            if f['fixture']['status']['short'] != 'NS': continue
            m_time = datetime.fromtimestamp(f['fixture']['timestamp'], tz=timezone.utc)
            if not (0 < (m_time - now).total_seconds() / 3600 <= 12): continue

            f_id = f['fixture']['id']
            try:
                res = requests.get(f"{BASE_URL}/odds?fixture={f_id}", headers=HEADERS, timeout=10).json()
                data = res.get('response', [])
                if not data: continue
                bms = data[0].get('bookmakers', [])
                for bm_id in BOOKMAKERS.keys():
                    bm = next((b for b in bms if b['id'] == bm_id), None)
                    if not bm: continue
                    mw = next((b for b in bm.get('bets', []) if b['id'] == 1), None)
                    if mw:
                        vals = mw.get('values', [])
                        o1 = next((float(v['odd']) for v in vals if v['value'] == 'Home'), 0.0)
                        o2 = next((float(v['odd']) for v in vals if v['value'] == 'Away'), 0.0)
                        if o1 > 0 and o2 > 0:
                            self._analyze_drop(f_id, bm_id, f['league']['id'], f['fixture']['date'], f['teams']['home']['name'], f['teams']['away']['name'], o1, o2)
            except:
                pass
            time.sleep(0.3)

    def _analyze_drop(self, f_id, bm_id, league_id, match_time, home, away, o1, o2):
        now_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self.cursor.execute("SELECT initial_odd_1, initial_odd_2 FROM live_tracking WHERE fixture_id = ? AND bookmaker_id = ?", (f_id, bm_id))
        row = self.cursor.fetchone()
        if not row:
            self.cursor.execute("INSERT INTO live_tracking VALUES (?,?,?,?,?,?,?,?,?,?,?)", (f_id, bm_id, league_id, match_time, home, away, o1, o2, o1, o2, now_str))
        else:
            i1, i2 = row
            d1, d2 = (i1-o1)/i1 if i1>0 else 0, (i2-o2)/i2 if i2>0 else 0
            self.cursor.execute("UPDATE live_tracking SET current_odd_1=?, current_odd_2=?, last_update=? WHERE fixture_id=? AND bookmaker_id=?", (o1, o2, now_str, f_id, bm_id))
            if d1 >= DROP_THRESHOLD:
                self.send_tg_alert(match_time, home, away, bm_id, "HOME (P1)", i1, o1, d1*100)
                self.cursor.execute("UPDATE live_tracking SET initial_odd_1=? WHERE fixture_id=? AND bookmaker_id=?", (o1, f_id, bm_id))
            elif d2 >= DROP_THRESHOLD:
                self.send_tg_alert(match_time, home, away, bm_id, "AWAY (P2)", i2, o2, d2*100)
                self.cursor.execute("UPDATE live_tracking SET initial_odd_2=? WHERE fixture_id=? AND bookmaker_id=?", (o2, f_id, bm_id))
        self.conn.commit()

if __name__ == "__main__":
    radar = DropOddsRadar()
    radar.track_odds(radar.scan_upcoming_matches())
