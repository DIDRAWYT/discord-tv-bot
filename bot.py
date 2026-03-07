import discord
from discord.ext import commands, tasks
from discord import app_commands
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
intents.reactions = True

bot = commands.Bot(command_prefix='!', intents=intents)

# ID каналов
CHANNELS = {
    'ss': 1479554031444689009,           # Канал "Для СС"
    'applications': 1479581481444839537 # Канал для результатов
}

# Роли для админки
ALLOWED_ROLES = ['Директор', 'Заместитель Директора']

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

def check_permissions(interaction):
    return any(role.name in ALLOWED_ROLES for role in interaction.user.roles)

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

# ==================== ОТПРАВКА В КАНАЛ СС ====================
async def send_application_to_channel(record):
    channel = bot.get_channel(CHANNELS['ss'])
    if not channel:
        print("❌ Канал СС не найден")
        return

    name = record.get('Имя Фамилия (IC)', 'Не указано')
    hours = record.get('Часов в паспорте', 'Не указано')
    discord_name = record.get('Имя пользователя в ДС (ivanov1234)', 'Не указано')

    # Сбор всех документов
    docs = []
    for key, value in record.items():
        if 'Паспорт' in key and value:
            docs.append(value)
    docs_text = "\n".join(docs) if docs else "Не прикреплены"

    embed = discord.Embed(
        title="📋 НОВАЯ ЗАЯВКА НА ТРУДОУСТРОЙСТВО",
        description="Кто-то хочет работать в телекомпании!",
        color=0x3498db,
        timestamp=datetime.now()
    )
    embed.add_field(name="👤 Имя Фамилия", value=name, inline=True)
    embed.add_field(name="⏰ Часов в паспорте", value=hours, inline=True)
    embed.add_field(name="📎 Документы", value=docs_text, inline=False)
    embed.add_field(name="💬 Discord", value=discord_name, inline=False)
    embed.set_footer(text=f"Заявка получена: {datetime.now().strftime('%d.%m.%Y %H:%M')}")

    msg = await channel.send(embed=embed)
    for emoji in ["✅", "❌", "📞", "📋"]:
        await msg.add_reaction(emoji)

    data = load_data()
    data.setdefault('application_messages', []).append({
        'message_id': msg.id,
        'name': name,
        'discord': discord_name,
        'hours': hours,
        'docs': docs_text
    })
    save_data(data)
    print(f"✅ Заявка от {name} отправлена в канал СС")

# ==================== ОБРАБОТКА РЕАКЦИЙ ====================
@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return
    if payload.channel_id != CHANNELS['ss']:
        return
    try:
        channel = bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        if message.author.id != bot.user.id:
            return
        guild = bot.get_guild(payload.guild_id)
        user = guild.get_member(payload.user_id)

        data = load_data()
        application_data = None
        for app in data.get('application_messages', []):
            if app['message_id'] == payload.message_id:
                application_data = app
                break
        if not application_data:
            return

        original_embed = message.embeds[0]
        results_channel = bot.get_channel(CHANNELS['applications'])

        if str(payload.emoji) == "✅":
            original_embed.color = 0x2ecc71
            original_embed.title = "✅ ЗАЯВКА ПРИНЯТА"
            await message.edit(embed=original_embed)

            if results_channel:
                embed = discord.Embed(
                    title="✅ ЗАЯВКА ПРИНЯТА",
                    color=0x2ecc71,
                    timestamp=datetime.now()
                )
                embed.add_field(name="👤 Имя Фамилия", value=application_data['name'], inline=True)
                embed.add_field(name="⏰ Часов в паспорте", value=application_data['hours'], inline=True)
                embed.add_field(name="📎 Документы", value=application_data['docs'], inline=False)
                embed.add_field(name="💬 Discord", value=application_data['discord'], inline=False)
                embed.add_field(name="✅ Решение", value=f"Принято: {user.mention}", inline=True)
                embed.add_field(name="📅 Дата решения", value=datetime.now().strftime('%d.%m.%Y %H:%M'), inline=True)
                await results_channel.send(embed=embed)

            await channel.send(f"✅ Заявка принята администратором {user.mention}")

        elif str(payload.emoji) == "❌":
            original_embed.color = 0xe74c3c
            original_embed.title = "❌ ЗАЯВКА ОТКЛОНЕНА"
            await message.edit(embed=original_embed)

            if results_channel:
                embed = discord.Embed(
                    title="❌ ЗАЯВКА ОТКЛОНЕНА",
                    color=0xe74c3c,
                    timestamp=datetime.now()
                )
                embed.add_field(name="👤 Имя Фамилия", value=application_data['name'], inline=True)
                embed.add_field(name="⏰ Часов в паспорте", value=application_data['hours'], inline=True)
                embed.add_field(name="📎 Документы", value=application_data['docs'], inline=False)
                embed.add_field(name="💬 Discord", value=application_data['discord'], inline=False)
                embed.add_field(name="❌ Решение", value=f"Отклонено: {user.mention}", inline=True)
                embed.add_field(name="📅 Дата решения", value=datetime.now().strftime('%d.%m.%Y %H:%M'), inline=True)
                await results_channel.send(embed=embed)

            await channel.send(f"❌ Заявка отклонена администратором {user.mention}")

        elif str(payload.emoji) == "📞":
            await channel.send(f"📞 {user.mention} свяжется с кандидатом")

        elif str(payload.emoji) == "📋":
            original_embed.color = 0xf1c40f
            original_embed.title = "📋 ЗАЯВКА В РАССМОТРЕНИИ"
            await message.edit(embed=original_embed)
            await channel.send(f"📋 Заявка взята в рассмотрение администратором {user.mention}")

        await message.remove_reaction(payload.emoji, user)

    except Exception as e:
        print("Ошибка:", e)

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
