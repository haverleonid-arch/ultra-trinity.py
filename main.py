# -*- coding: utf-8 -*-
import asyncio, sqlite3, os, aiohttp, subprocess
from datetime import datetime, timezone
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

API_KEY = "ac1eae60740a1e6a4e987c7577539963"
HEADERS = {"x-apisports-key": API_KEY}
BASE_URL = "https://v3.football.api-sports.io"
DB_NAME = "nexus_v5.db"
TG_TOKEN = "8603529040:AAG2ZvdFjyo4L6JlrpGVQcoksDsIQdhOl4M"
ADMIN_ID = 8301693491

BOOKMAKERS = {
    17: "Pinnacle (Smart)",
    8: "Bet365 (Classic)",
    1: "1xBet (Mass)"
}

class NexusState:
    def __init__(self):
        self.active = False
        self.threshold = 0.10
        self.last_scan = "None"
        self.matches = 0

state = NexusState()
conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), DB_NAME), check_same_thread=False)
cur = conn.cursor()
cur.execute('''CREATE TABLE IF NOT EXISTS live_tracking (
    fixture_id INTEGER, bookmaker_id INTEGER, league_id INTEGER, 
    market_id INTEGER, target TEXT, initial_odd REAL, 
    current_odd REAL, last_update TEXT, match_time TEXT, 
    PRIMARY KEY (fixture_id, bookmaker_id, market_id, target)
)''')
conn.commit()

main_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="START"), KeyboardButton(text="STOP")],
    [KeyboardButton(text="THRESHOLD: 10%"), KeyboardButton(text="THRESHOLD: 1%")], 
    [KeyboardButton(text="STATUS"), KeyboardButton(text="GITHUB UPDATE")]
], resize_keyboard=True)

bot = Bot(token=TG_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def c_start(m: Message):
    if m.from_user.id == ADMIN_ID:
        await m.answer("[NEXUS V5.0 ONLINE]\nMarkets: 1x2, Asian Handicap, Asian Totals.\nCI/CD Protocol: ACTIVE", reply_markup=main_kb)

@dp.message(F.text == "START")
async def b_start(m: Message):
    if m.from_user.id == ADMIN_ID:
        state.active = True
        await m.answer("[+] Radar STARTED.")

@dp.message(F.text == "STOP")
async def b_stop(m: Message):
    if m.from_user.id == ADMIN_ID:
        state.active = False
        await m.answer("[-] Radar STOPPED.")

@dp.message(F.text == "THRESHOLD: 10%")
async def b_t10(m: Message):
    if m.from_user.id == ADMIN_ID:
        state.threshold = 0.10
        await m.answer("[*] Threshold: 10% (Live Mode).")

@dp.message(F.text == "THRESHOLD: 1%")
async def b_t1(m: Message):
    if m.from_user.id == ADMIN_ID:
        state.threshold = 0.01
        await m.answer("[*] Threshold: 1% (Test Mode).")

@dp.message(F.text == "STATUS")
async def b_status(m: Message):
    if m.from_user.id == ADMIN_ID:
        s = "ACTIVE" if state.active else "STOPPED"
        await m.answer(f"[STATUS]\nState: {s}\nDrop: {state.threshold*100}%\nScan: {state.last_scan}\nTrack: {state.matches}")

@dp.message(F.text == "GITHUB UPDATE")
async def b_update(m: Message):
    if m.from_user.id == ADMIN_ID:
        await m.answer("[*] PULLING REPOSITORY FROM GITHUB...\nServer will restart in 3 seconds.")
        try:
            subprocess.run(["git", "fetch", "--all"], cwd="/root/ultra-trinity", check=True)
            subprocess.run(["git", "reset", "--hard", "origin/main"], cwd="/root/ultra-trinity", check=True)
            subprocess.Popen(["systemctl", "restart", "nexus.service"])
        except Exception as e:
            await m.answer(f"[!] UPDATE FAILED: {e}")

async def check_odds(f_id, bm_id, l_id, m_t, home, away, market_id, target, current_odd):
    now = datetime.now(timezone.utc).strftime("%H:%M:%S")
    cur.execute("SELECT initial_odd FROM live_tracking WHERE fixture_id=? AND bookmaker_id=? AND market_id=? AND target=?", (f_id, bm_id, market_id, target))
    row = cur.fetchone()
    
    if not row:
        cur.execute("INSERT INTO live_tracking VALUES (?,?,?,?,?,?,?,?,?)", (f_id, bm_id, l_id, market_id, target, current_odd, current_odd, now, m_t))
        conn.commit()
    else:
        initial_odd = row[0]
        drop = (initial_odd - current_odd) / initial_odd if initial_odd > 0 else 0
        cur.execute("UPDATE live_tracking SET current_odd=?, last_update=? WHERE fixture_id=? AND bookmaker_id=? AND market_id=? AND target=?", (current_odd, now, f_id, bm_id, market_id, target))
        
        if drop >= state.threshold:
            markets = {1: "1x2", 5: "ASIAN HANDICAP", 3: "ASIAN TOTALS"}
            msg = f"[SHARP SIGNAL]\nMatch: {home} - {away}\nMarket: {markets.get(market_id, str(market_id))}\nTarget: {target}\nRadar: {BOOKMAKERS.get(bm_id, bm_id)}\nDrop: {initial_odd} -> {current_odd} (-{drop*100:.1f}%)"
            await bot.send_message(ADMIN_ID, msg)
            cur.execute("UPDATE live_tracking SET initial_odd=? WHERE fixture_id=? AND bookmaker_id=? AND market_id=? AND target=?", (current_odd, f_id, bm_id, market_id, target))
        conn.commit()

async def scanner():
    while True:
        if state.active:
            state.last_scan = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
            async with aiohttp.ClientSession() as s:
                try:
                    async with s.get(f"{BASE_URL}/fixtures?date={datetime.now(timezone.utc).strftime('%Y-%m-%d')}&timezone=Europe/London", headers=HEADERS) as r:
                        fxt = (await r.json()).get('response', [])
                    active = [f for f in fxt if f['fixture']['status']['short']=='NS' and 0 < (datetime.fromtimestamp(f['fixture']['timestamp'], tz=timezone.utc)-datetime.now(timezone.utc)).total_seconds()/3600 <= 12]
                    state.matches = len(active)
                    
                    for f in active:
                        if not state.active: break
                        f_id, home, away = f['fixture']['id'], f['teams']['home']['name'], f['teams']['away']['name']
                        l_id, m_t = f['league']['id'], f['fixture']['date']
                        
                        async with s.get(f"{BASE_URL}/odds?fixture={f_id}", headers=HEADERS) as orp:
                            odz = (await orp.json()).get('response', [{}])[0].get('bookmakers', [])
                            for bm in odz:
                                if bm['id'] not in BOOKMAKERS.keys(): continue
                                
                                # 1x2 (ID: 1)
                                mw = next((b for b in bm.get('bets', []) if b['id']==1), None)
                                if mw:
                                    for v in mw.get('values', []):
                                        if v['value'] in ['Home', 'Away'] and float(v['odd']) > 0:
                                            await check_odds(f_id, bm['id'], l_id, m_t, home, away, 1, v['value'], float(v['odd']))
                                
                                # Asian Handicap (ID: 5)
                                ah = next((b for b in bm.get('bets', []) if b['id']==5), None)
                                if ah:
                                    for v in ah.get('values', []):
                                        if float(v['odd']) > 0:
                                            await check_odds(f_id, bm['id'], l_id, m_t, home, away, 5, str(v['value']), float(v['odd']))

                                # Asian Totals (ID: 3)
                                at = next((b for b in bm.get('bets', []) if b['id']==3), None)
                                if at:
                                    for v in at.get('values', []):
                                        if float(v['odd']) > 0:
                                            await check_odds(f_id, bm['id'], l_id, m_t, home, away, 3, f"TOTAL {v['value']}", float(v['odd']))

                        await asyncio.sleep(0.35)
                except: pass
        await asyncio.sleep(60)

async def main():
    asyncio.create_task(scanner())
    print("NEXUS V5.0 CI/CD DAEMON RUNNING...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
