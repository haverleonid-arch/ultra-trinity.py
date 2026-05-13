# -*- coding: utf-8 -*-
import asyncio, sqlite3, os, aiohttp, subprocess
from datetime import datetime, timezone
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

# --- CONFIG ---
API_KEY = "ac1eae60740a1e6a4e987c7577539963"
HEADERS = {"x-apisports-key": API_KEY}
BASE_URL = "https://v3.football.api-sports.io"
DB_NAME = "nexus_v6.db"
TG_TOKEN = "8603529040:AAG2ZvdFjyo4L6JlrpGVQcoksDsIQdhOl4M"
ADMIN_ID = 8301693491

BOOKMAKERS = {
    17: "Pinnacle (Smart Money)",
    8: "Bet365 (World Classic)",
    1: "1xBet (Mass Market)"
}

class NexusState:
    def __init__(self):
        self.active = False
        self.threshold = 0.10
        self.last_scan = "Ожидание..."
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

# --- TITAN UI KEYBOARD ---
main_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🟢 АКТИВИРОВАТЬ РАДАР"), KeyboardButton(text="🛑 ОСТАНОВИТЬ")],
    [KeyboardButton(text="🛡 БОЕВОЙ ПОРОГ (10%)"), KeyboardButton(text="🧪 ТЕСТ ПОРОГ (1%)")], 
    [KeyboardButton(text="📊 ДАШБОРД СТАТУСА"), KeyboardButton(text="📡 ТЕСТОВЫЙ СИГНАЛ")],
    [KeyboardButton(text="🔄 СИНХРОНИЗАЦИЯ С GITHUB")]
], resize_keyboard=True)

bot = Bot(token=TG_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def c_start(m: Message):
    if m.from_user.id == ADMIN_ID:
        msg = (
            "🧬 <b>MATH-TRINITY NEXUS [V6.0 TITAN]</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📡 <b>Сенсоры активны:</b>\n"
            "┣ 1x2 (Классика)\n"
            "┣ Asian Handicap (Smart Money)\n"
            "┗ Asian Totals (Инсайды)\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🚀 <i>CI/CD Протокол: ПОДКЛЮЧЕН</i>"
        )
        await m.answer(msg, reply_markup=main_kb, parse_mode="HTML")

@dp.message(F.text == "🟢 АКТИВИРОВАТЬ РАДАР")
async def b_start(m: Message):
    if m.from_user.id == ADMIN_ID:
        state.active = True
        await m.answer("⚡️ <b>СИСТЕМА ЗАПУЩЕНА</b>\nРадар начал сканирование линии.", parse_mode="HTML")

@dp.message(F.text == "🛑 ОСТАНОВИТЬ")
async def b_stop(m: Message):
    if m.from_user.id == ADMIN_ID:
        state.active = False
        await m.answer("📴 <b>СИСТЕМА ПРИОСТАНОВЛЕНА</b>\nПарсинг API прекращен.", parse_mode="HTML")

@dp.message(F.text == "🛡 БОЕВОЙ ПОРОГ (10%)")
async def b_t10(m: Message):
    if m.from_user.id == ADMIN_ID:
        state.threshold = 0.10
        await m.answer("🛡 Установлен <b>БОЕВОЙ ФИЛЬТР (10%)</b>.\n<i>Отслеживаем только крупные вливания капитала.</i>", parse_mode="HTML")

@dp.message(F.text == "🧪 ТЕСТ ПОРОГ (1%)")
async def b_t1(m: Message):
    if m.from_user.id == ADMIN_ID:
        state.threshold = 0.01
        await m.answer("🧪 Установлен <b>ТЕСТОВЫЙ ФИЛЬТР (1%)</b>.\n<i>Сверхчувствительный режим (возможен спам).</i>", parse_mode="HTML")

@dp.message(F.text == "📊 ДАШБОРД СТАТУСА")
async def b_status(m: Message):
    if m.from_user.id == ADMIN_ID:
        s = "🟢 В АКТИВНОМ ПОИСКЕ" if state.active else "🛑 РЕЖИМ СНА"
        msg = (
            "📊 <b>NEXUS ТЕЛЕМЕТРИЯ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💠 Статус: <b>{s}</b>\n"
            f"🎯 Фильтр дропа: <b>{state.threshold*100}%</b>\n"
            f"⏱ Последний пинг: <b>{state.last_scan}</b>\n"
            f"⚽️ Матчей в трекинге: <b>{state.matches}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        await m.answer(msg, parse_mode="HTML")

@dp.message(F.text == "📡 ТЕСТОВЫЙ СИГНАЛ")
async def b_test_signal(m: Message):
    if m.from_user.id == ADMIN_ID:
        msg = (
            "⚠️ <b>[TEST] SHARP SIGNAL DETECTED</b> ⚠️\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚽️ <b>Real Madrid - Barcelona</b>\n"
            "🎯 Маркет: <b>ASIAN HANDICAP</b>\n"
            "📌 Исход: <b>Home -0.75</b>\n"
            "🏢 Радар: <b>Pinnacle (Smart Money)</b>\n"
            "📉 Прогруз: 2.10 ➔ 1.85 (<b>-11.9%</b>)\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "<i>Это искусственный сигнал для проверки связи.</i>"
        )
        await m.answer(msg, parse_mode="HTML")

@dp.message(F.text == "🔄 СИНХРОНИЗАЦИЯ С GITHUB")
async def b_update(m: Message):
    if m.from_user.id == ADMIN_ID:
        await m.answer("⏳ <b>ИНИЦИАЛИЗАЦИЯ CI/CD ПРОТОКОЛА...</b>\n<i>Подгрузка архитектуры из облака. Сервер перезагрузится через 3 секунды.</i>", parse_mode="HTML")
        try:
            subprocess.run(["git", "fetch", "--all"], cwd="/root/ultra-trinity", check=True)
            subprocess.run(["git", "reset", "--hard", "origin/main"], cwd="/root/ultra-trinity", check=True)
            subprocess.Popen(["systemctl", "restart", "nexus.service"])
        except Exception as e:
            await m.answer(f"❌ <b>ОШИБКА ОБНОВЛЕНИЯ:</b>\n<code>{e}</code>", parse_mode="HTML")

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
            m_name = markets.get(market_id, str(market_id))
            msg = (
                f"🚨 <b>SHARP SIGNAL DETECTED</b> 🚨\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚽️ <b>{home} - {away}</b>\n"
                f"🎯 Маркет: <b>{m_name}</b>\n"
                f"📌 Исход: <b>{target}</b>\n"
                f"🏢 Радар: <b>{BOOKMAKERS.get(bm_id, bm_id)}</b>\n"
                f"📉 Прогруз: {initial_odd} ➔ {current_odd} (<b>-{drop*100:.1f}%</b>)\n"
                f"━━━━━━━━━━━━━━━━━━━━━━"
            )
            await bot.send_message(ADMIN_ID, msg, parse_mode="HTML")
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
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
