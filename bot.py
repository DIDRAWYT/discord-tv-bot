import discord
from discord.ext import commands, tasks
import json
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from keep_alive import keep_alive

# ==================== НАСТРОЙКИ ====================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Канал, куда уходят все заявки
APPLICATIONS_CHANNEL_ID = 1479745873360588870

# Google Sheets
SPREADSHEET_ID = '1zL5rRk-zny2riAdRSUl2ZiA-pK76--dGdSJObuVLZRs'
SHEET_NAME = 'Ответы на форму (1)'

DATA_FILE = 'bot_data.json'

# ==================== ЗАГРУЗКА ДАННЫХ ====================
def load_data():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {'last_row': 0, 'application_messages': []}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ==================== GOOGLE SHEETS ====================
def get_google_sheet():
    try:
        creds_json = os.environ.get('GOOGLE_CREDENTIALS')
        if creds_json:
            creds_dict = json.loads(creds_json)
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_name('google-key.json', scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        print("✅ Google Sheets подключён")
        return sheet
    except Exception as e:
        print("Google ошибка:", e)
        return None

# ==================== ПРОВЕРКА НОВЫХ ЗАЯВОК ====================
@tasks.loop(seconds=30)
async def check_new_applications():
    sheet = get_google_sheet()
    if not sheet:
        return
    try:
        records = sheet.get_all_records()
        data = load_data()
        last_row = data.get('last_row', 0)
        if len(records) > last_row:
            print(f"🔍 Найдено новых заявок: {len(records) - last_row}")
            for i in range(last_row, len(records)):
                await send_application_to_channel(records[i])
            data['last_row'] = len(records)
            save_data(data)
    except Exception as e:
        print("Ошибка проверки заявок:", e)

# ==================== ОТПРАВКА В КАНАЛ ====================
async def send_application_to_channel(record):
    channel = bot.get_channel(APPLICATIONS_CHANNEL_ID)
    if not channel:
        print("❌ Канал заявок не найден")
        return

    name = record.get('Имя Фамилия (IC)', 'Не указано')
    hours = record.get('Часов в паспорте', 'Не указано')
    discord_name = record.get('Имя пользователя в ДС (ivanov1234)', 'Не указано')

    # Собираем все документы
    docs = []
    for key, value in record.items():
        if 'Паспорт' in key and value:
            docs.append(value)
    docs_text = "\n".join(docs) if docs else "Не прикреплены"

    embed = discord.Embed(
        title="📋 НОВАЯ ЗАЯВКА",
        description="Новая заявка на трудоустройство",
        color=0x3498db,
        timestamp=datetime.now()
    )
    embed.add_field(name="👤 Имя Фамилия", value=name, inline=False)
    embed.add_field(name="⏰ Часов в паспорте", value=hours, inline=False)
    embed.add_field(name="📎 Документы", value=docs_text, inline=False)
    embed.add_field(name="💬 Discord", value=discord_name, inline=False)
    embed.set_footer(text=f"Заявка получена: {datetime.now().strftime('%d.%m.%Y %H:%M')}")

    msg = await channel.send(embed=embed)

    # Сохраняем ID сообщения
    data = load_data()
    data.setdefault('application_messages', []).append({
        'message_id': msg.id,
        'name': name,
        'discord': discord_name,
        'hours': hours,
        'docs': docs_text
    })
    save_data(data)
    print(f"✅ Заявка от {name} отправлена в канал заявок")

# ==================== ЗАПУСК ====================
@bot.event
async def on_ready():
    print(f"Бот запущен: {bot.user}")
    check_new_applications.start()

TOKEN = os.environ.get('DISCORD_TOKEN')
keep_alive()

if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ Токен не найден")
