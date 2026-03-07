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

bot = commands.Bot(command_prefix='!', intents=intents)

# ==================== КАНАЛЫ ====================

APPLICATIONS_CHANNEL_ID = 1479745873360588870  # Заявки
NEWS_CHANNEL_ID = 1479458023146651689         # Новости
REPORTS_CHANNEL_ID = 1479458060866162880     # Репортажи

# Роли админов
ALLOWED_ROLES = ['Директор', 'Заместитель Директора']

# Google Sheets
SPREADSHEET_ID = '1zL5rRk-zny2riAdRSUl2ZiA-pK76--dGdSJObuVLZRs'
SHEET_NAME = 'Ответы на форму (1)'

DATA_FILE = 'bot_data.json'

# ==================== ЗАГРУЗКА / СОХРАНЕНИЕ ====================

def load_data():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            'warns': {}, 
            'requests': [], 
            'schedule': [], 
            'stats': {'news': 0, 'reports': 0},
            'last_row': 0,
            'application_messages': []
        }

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def check_permissions(interaction):
    user_roles = [role.name for role in interaction.user.roles]
    return any(role in ALLOWED_ROLES for role in user_roles)

# ==================== GOOGLE SHEETS ====================

def get_google_sheet():
    """Подключение к Google Sheets через чистый JSON из переменной окружения"""
    try:
        creds_json = os.environ.get('GOOGLE_CREDENTIALS')
        if not creds_json:
            print("❌ GOOGLE_CREDENTIALS не найден")
            return None

        creds_dict = json.loads(creds_json)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        print("✅ Google Sheets подключён через переменную JSON")
        return sheet
    except Exception as e:
        print(f"Google ошибка: {e}")
        return None

# ==================== ПРОВЕРКА НОВЫХ ЗАЯВОК ====================

@tasks.loop(seconds=30)
async def check_new_applications():
    sheet = get_google_sheet()
    if not sheet:
        return
    try:
        records = sheet.get_all_records()
        if not records:
            return
        data = load_data()
        last_row = data.get('last_row', 0)
        if len(records) > last_row:
            print(f"🔍 Найдено новых заявок: {len(records) - last_row}")
            for i in range(last_row, len(records)):
                await send_application_to_channel(records[i])
            data['last_row'] = len(records)
            save_data(data)
    except Exception as e:
        print(f"❌ Ошибка при проверке заявок: {e}")

# ==================== ОТПРАВКА ЗАЯВКИ ====================

async def send_application_to_channel(record):
    channel = bot.get_channel(APPLICATIONS_CHANNEL_ID)
    if not channel:
        print("❌ Канал заявок не найден")
        return

    name = record.get('Имя Фамилия (IC)', 'Не указано')
    hours = record.get('Часов в паспорте', 'Не указано')
    discord_name = record.get('Имя пользователя в ДС (ivanov1234)', 'Не указано')
    
    docs = 'Не указано'
    for key in record.keys():
        if 'Паспорт' in key:
            docs = record[key]
            break

    embed = discord.Embed(
        title="📋 НОВАЯ ЗАЯВКА",
        description="Поступила новая заявка на трудоустройство",
        color=0x3498db,
        timestamp=datetime.now()
    )
    embed.add_field(name="👤 Имя Фамилия", value=name, inline=True)
    embed.add_field(name="⏰ Часов в паспорте", value=hours, inline=True)
    embed.add_field(name="💬 Discord", value=discord_name, inline=False)
    embed.add_field(name="📎 Документы", value=docs if docs else "Не прикреплены", inline=False)
    embed.set_footer(text=f"Заявка получена: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    
    await channel.send(embed=embed)
    print(f"✅ Заявка от {name} отправлена в канал заявок")

# ==================== КОМАНДЫ ====================

# /вакансии
@bot.tree.command(name="вакансии", description="Посмотреть вакансии")
async def vacancies(interaction: discord.Interaction):
    embed = discord.Embed(title="💼 Вакансии", description="Открытые вакансии телекомпании", color=0x3498db)
    embed.add_field(name="Список", value="• Корреспондент\n• Оператор\n• Звукорежиссёр\n• Редактор\n• Ведущий\n• Монтажёр", inline=False)
    embed.add_field(name="Как подать", value="Заполните анкету по кнопке ниже", inline=False)
    view = discord.ui.View()
    button = discord.ui.Button(label="📋 Заполнить анкету", style=discord.ButtonStyle.link,
                               url="https://docs.google.com/forms/d/e/1FAIpQLSdwCAGosL-YaKsqGNzpkjfWMqF8yZbtWpbpIaRrRR2J5luR2A/viewform")
    view.add_item(button)
    await interaction.response.send_message(embed=embed, view=view)

# /новости
@bot.tree.command(name="новости", description="Опубликовать новость")
@app_commands.describe(заголовок="Заголовок", текст="Текст")
async def news(interaction: discord.Interaction, заголовок: str, текст: str):
    if not check_permissions(interaction):
        await interaction.response.send_message("❌ Нет прав", ephemeral=True)
        return
    channel = bot.get_channel(NEWS_CHANNEL_ID)
    if channel:
        embed = discord.Embed(title=f"📰 {заголовок}", description=текст, color=0x3498db, timestamp=datetime.now())
        embed.set_footer(text=f"От {interaction.user.display_name}")
        await channel.send(embed=embed)
        data = load_data()
        data['stats']['news'] = data['stats'].get('news',0)+1
        save_data(data)
        await interaction.response.send_message("✅ Новость опубликована", ephemeral=True)

# /репортаж
@bot.tree.command(name="репортаж", description="Опубликовать репортаж")
@app_commands.describe(место="Место", текст="Текст")
async def report(interaction: discord.Interaction, место: str, текст: str):
    if not check_permissions(interaction):
        await interaction.response.send_message("❌ Нет прав", ephemeral=True)
        return
    channel = bot.get_channel(REPORTS_CHANNEL_ID)
    if channel:
        embed = discord.Embed(title=f"🎥 Репортаж из {место}", description=текст, color=0xe67e22, timestamp=datetime.now())
        embed.set_footer(text=f"Корреспондент: {interaction.user.display_name}")
        await channel.send(embed=embed)
        data = load_data()
        data['stats']['reports'] = data['stats'].get('reports',0)+1
        save_data(data)
        await interaction.response.send_message("✅ Репортаж опубликован", ephemeral=True)

# /интервью
@bot.tree.command(name="интервью", description="Записаться на интервью")
@app_commands.describe(имя="Имя Фамилия", контакт="Discord/телефон")
async def interview(interaction: discord.Interaction, имя: str, контакт: str):
    channel = bot.get_channel(APPLICATIONS_CHANNEL_ID)
    if channel:
        embed = discord.Embed(title="📞 Запись на интервью", description=f"{имя} хочет пройти интервью", color=0x9b59b6, timestamp=datetime.now())
        embed.add_field(name="Контакт", value=контакт, inline=False)
        await channel.send(embed=embed)
        await interaction.response.send_message("✅ Вы записаны на интервью", ephemeral=True)

# /статистика
@bot.tree.command(name="статистика", description="Статистика новостей и репортажей")
async def statistics(interaction: discord.Interaction):
    data = load_data()
    embed = discord.Embed(title="📊 Статистика", color=0x1abc9c)
    embed.add_field(name="Новости", value=data['stats'].get('news',0), inline=True)
    embed.add_field(name="Репортажи", value=data['stats'].get('reports',0), inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# /добавить_в_расписание
@bot.tree.command(name="добавить_в_расписание", description="Добавить событие")
@app_commands.describe(дата="Дата", пользователь="Пользователь", тема="Тема")
async def add_schedule(interaction: discord.Interaction, дата: str, пользователь: str, тема: str):
    if not check_permissions(interaction):
        await interaction.response.send_message("❌ Нет прав", ephemeral=True)
        return
    data = load_data()
    data.setdefault('schedule',[]).append({'date': дата, 'user': пользователь, 'topic': тема})
    save_data(data)
    await interaction.response.send_message("✅ Событие добавлено", ephemeral=True)

# /расписание
@bot.tree.command(name="расписание", description="Показать расписание")
async def show_schedule(interaction: discord.Interaction):
    data = load_data()
    if not data.get('schedule'):
        await interaction.response.send_message("📅 Расписание пусто", ephemeral=True)
        return
    embed = discord.Embed(title="📅 Расписание", color=0x3498db)
    for i, item in enumerate(data['schedule'][-10:],1):
        embed.add_field(name=f"{i}. {item['date']}", value=f"**{item['user']}**\n{item['topic']}", inline=False)
    await interaction.response.send_message(embed=embed)



# ==================== ВЫГОВОРЫ ====================

@bot.tree.command(name="выговор", description="Выдать выговор сотруднику")
@app_commands.describe(сотрудник="Сотрудник", причина="Причина выговора")
async def warn(interaction: discord.Interaction, сотрудник: discord.Member, причина: str):
    if not check_permissions(interaction):
        await interaction.response.send_message("❌ Нет прав", ephemeral=True)
        return

    data = load_data()
    user_id = str(сотрудник.id)

    if user_id not in data['warns']:
        data['warns'][user_id] = []

    warn_data = {
        'id': len(data['warns'][user_id]) + 1,
        'reason': причина,
        'moderator': interaction.user.display_name,
        'date': str(datetime.now())
    }

    data['warns'][user_id].append(warn_data)
    save_data(data)

    await interaction.response.send_message(f"✅ Выговор №{warn_data['id']} выдан {сотрудник.mention}", ephemeral=True)


@bot.tree.command(name="выговоры", description="Показать выговоры сотрудника")
@app_commands.describe(сотрудник="Сотрудник")
async def check_warns(interaction: discord.Interaction, сотрудник: discord.Member):
    if not check_permissions(interaction):
        await interaction.response.send_message("❌ Нет прав", ephemeral=True)
        return

    data = load_data()
    user_id = str(сотрудник.id)

    if user_id not in data['warns'] or not data['warns'][user_id]:
        await interaction.response.send_message(f"✅ У {сотрудник.mention} нет выговоров", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"📋 Выговоры: {сотрудник.display_name}",
        color=0xf1c40f
    )

    for warn in data['warns'][user_id][-5:]:
        embed.add_field(
            name=f"Выговор №{warn['id']} от {warn['date'][:10]}",
            value=f"Причина: {warn['reason']}\nМодератор: {warn['moderator']}",
            inline=False
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== ЗАПУСК ====================

@bot.event
async def on_ready():
    print(f"✅ Бот запущен: {bot.user}")
    check_new_applications.start()
    try:
        synced = await bot.tree.sync()
        print(f"✅ Команд загружено: {len(synced)}")
    except Exception as e:
        print(f"❌ Ошибка синхронизации: {e}")

keep_alive()
TOKEN = os.environ.get('DISCORD_TOKEN')
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ Токен не найден")


