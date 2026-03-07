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

bot = commands.Bot(command_prefix="!", intents=intents)

# ID каналов
CHANNELS = {
    'applications': 1479745873360588870,  # Канал для всех заявок
    'news': 1479458023146651689,          # Канал новостей
    'reports': 1479458060866162880        # Канал репортажей
}

# Роли с правами
ALLOWED_ROLES = ["Директор", "Заместитель Директора"]

# Google Sheets
SPREADSHEET_ID = "1zL5rRk-zny2riAdRSUl2ZiA-pK76--dGdSJObuVLZRs"
SHEET_NAME = "Ответы на форму (1)"

# Данные бота
DATA_FILE = "bot_data.json"

def load_data():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "warns": {},
            "requests": [],
            "schedule": [],
            "stats": {"news": 0, "reports": 0},
            "last_row": 0,
            "application_messages": []
        }

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def check_permissions(interaction):
    return any(role.name in ALLOWED_ROLES for role in interaction.user.roles)

# ==================== GOOGLE SHEETS ====================
def get_google_sheet():
    try:
        creds_json = os.environ.get("GOOGLE_CREDENTIALS")
        if not creds_json:
            raise Exception("GOOGLE_CREDENTIALS не найден!")
        creds_dict = json.loads(creds_json)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        print("✅ Google Sheets подключён через переменную JSON")
        return sheet
    except Exception as e:
        print(f"❌ Google ошибка: {e}")
        return None

# ==================== ПРОВЕРКА ЗАЯВОК ====================
@tasks.loop(seconds=30)
async def check_new_applications():
    sheet = get_google_sheet()
    if not sheet:
        return
    try:
        all_records = sheet.get_all_records()
        if not all_records:
            return
        data = load_data()
        last_row = data.get("last_row", 0)
        if len(all_records) > last_row:
            for i in range(last_row, len(all_records)):
                record = all_records[i]
                await send_application_to_channel(record)
            data["last_row"] = len(all_records)
            save_data(data)
            print(f"🔍 Найдено новых заявок: {len(all_records) - last_row}")
    except Exception as e:
        print(f"❌ Ошибка при проверке заявок: {e}")

async def send_application_to_channel(record):
    channel = bot.get_channel(CHANNELS["applications"])
    if not channel:
        print("❌ Канал для заявок не найден")
        return

    name = record.get("Имя Фамилия (IC)", "Не указано")
    hours = record.get("Часов в паспорте", "Не указано")
    discord_name = record.get("Имя пользователя в ДС (ivanov1234)", "Не указано")

    docs = "Не указано"
    for key in record:
        if "Паспорт" in key:
            docs = record[key]
            break

    embed = discord.Embed(
        title="📋 НОВАЯ ЗАЯВКА НА ТРУДОУСТРОЙСТВО",
        description="Кандидат подал заявку",
        color=0x3498db,
        timestamp=datetime.now()
    )
    embed.add_field(name="👤 Имя Фамилия", value=name, inline=True)
    embed.add_field(name="⏰ Часов в паспорте", value=hours, inline=True)
    embed.add_field(name="💬 Discord", value=discord_name, inline=False)

    if docs != "Не указано":
        if docs.startswith(("http://", "https://")):
            embed.add_field(name="📎 Документы", value=f"[Ссылка]({docs})", inline=False)
        else:
            embed.add_field(name="📎 Документы", value=docs, inline=False)
    else:
        embed.add_field(name="📎 Документы", value="Не прикреплены", inline=False)

    msg = await channel.send(embed=embed)

    data = load_data()
    data.setdefault("application_messages", []).append({
        "message_id": msg.id,
        "name": name,
        "discord": discord_name,
        "hours": hours,
        "docs": docs
    })
    save_data(data)
    print(f"✅ Заявка от {name} отправлена в канал заявок")

# ==================== КОМАНДЫ ====================

# Вакансии
@bot.tree.command(name="вакансии", description="Посмотреть вакансии и подать заявку")
async def vacancies(interaction: discord.Interaction):
    embed = discord.Embed(
        title="💼 РАБОТА В ТЕЛЕКОМПАНИИ",
        description="Мы ищем талантливых сотрудников!",
        color=0x3498db
    )
    embed.add_field(
        name="📹 Вакансии",
        value="• Корреспондент\n• Оператор\n• Звукорежиссёр\n• Редактор\n• Ведущий\n• Монтажёр",
        inline=False
    )
    embed.add_field(
        name="📝 Как подать заявку",
        value="Заполните Google форму, ссылка ниже",
        inline=False
    )
    view = discord.ui.View()
    button = discord.ui.Button(
        label="📋 Заполнить анкету",
        style=discord.ButtonStyle.link,
        url="https://docs.google.com/forms/d/e/1FAIpQLSdwCAGosL-YaKsqGNzpkjfWMqF8yZbtWpbpIaRrRR2J5luR2A/viewform"
    )
    view.add_item(button)
    await interaction.response.send_message(embed=embed, view=view)

# Проверить заявки вручную
@bot.tree.command(name="проверить_заявки", description="Принудительно проверить новые заявки")
async def check_now(interaction: discord.Interaction):
    if not check_permissions(interaction):
        await interaction.response.send_message("❌ Нет прав", ephemeral=True)
        return
    await interaction.response.send_message("🔄 Проверяю заявки...", ephemeral=True)
    await check_new_applications()
    await interaction.followup.send("✅ Проверка завершена", ephemeral=True)

# Новости
@bot.tree.command(name="новости", description="Отправить новость")
@app_commands.describe(заголовок="Заголовок новости", текст="Текст новости")
async def news(interaction: discord.Interaction, заголовок: str, текст: str):
    if not check_permissions(interaction):
        await interaction.response.send_message("❌ Нет прав", ephemeral=True)
        return
    channel = bot.get_channel(CHANNELS["news"])
    if channel:
        embed = discord.Embed(title=f"📰 {заголовок}", description=текст, color=0x3498db, timestamp=datetime.now())
        embed.set_footer(text=f"От {interaction.user.display_name}")
        await channel.send(embed=embed)
        data = load_data()
        data["stats"]["news"] = data["stats"].get("news", 0) + 1
        save_data(data)
        await interaction.response.send_message("✅ Новость опубликована", ephemeral=True)

# Репортаж
@bot.tree.command(name="репортаж", description="Отправить репортаж")
@app_commands.describe(место="Откуда репортаж", текст="Текст репортажа")
async def report(interaction: discord.Interaction, место: str, текст: str):
    if not check_permissions(interaction):
        await interaction.response.send_message("❌ Нет прав", ephemeral=True)
        return
    channel = bot.get_channel(CHANNELS["reports"])
    if channel:
        embed = discord.Embed(title=f"🎥 РЕПОРТАЖ ИЗ {место}", description=текст, color=0xe67e22, timestamp=datetime.now())
        embed.set_footer(text=f"Корреспондент: {interaction.user.display_name}")
        await channel.send(embed=embed)
        data = load_data()
        data["stats"]["reports"] = data["stats"].get("reports", 0) + 1
        save_data(data)
        await interaction.response.send_message("✅ Репортаж опубликован", ephemeral=True)

# Выговор с выдачей роли
@bot.tree.command(name="выговор", description="Выдать выговор сотруднику и дать роль Выговор")
@app_commands.describe(сотрудник="Сотрудник", причина="Причина выговора")
async def warn(interaction: discord.Interaction, сотрудник: discord.Member, причина: str):
    if not check_permissions(interaction):
        await interaction.response.send_message("❌ Нет прав", ephemeral=True)
        return

    data = load_data()
    uid = str(сотрудник.id)
    data.setdefault("warns", {}).setdefault(uid, [])
    
    warn_data = {
        "id": len(data["warns"][uid]) + 1,
        "reason": причина,
        "moderator": interaction.user.name,
        "date": str(datetime.now())
    }
    data["warns"][uid].append(warn_data)
    save_data(data)

    # ==================== ВЫДАЧА РОЛИ ====================
    role = discord.utils.get(interaction.guild.roles, name="Выговор")
    if role:
        try:
            await сотрудник.add_roles(role, reason=f"Выговор №{warn_data['id']} выдан {interaction.user}")
        except Exception as e:
            print(f"❌ Не удалось выдать роль: {e}")
    else:
        print("❌ Роль 'Выговор' не найдена на сервере")

    await interaction.response.send_message(
        f"✅ Выговор №{warn_data['id']} выдан {сотрудник.mention} и роль 'Выговор' назначена",
        ephemeral=True
    )

# Выговоры
@bot.tree.command(name="выговоры", description="Показать выговоры сотрудника")
@app_commands.describe(сотрудник="Сотрудник")
async def check_warns(interaction: discord.Interaction, сотрудник: discord.Member):
    if not check_permissions(interaction):
        await interaction.response.send_message("❌ Нет прав", ephemeral=True)
        return
    data = load_data()
    uid = str(сотрудник.id)
    warns = data.get("warns", {}).get(uid, [])
    if not warns:
        await interaction.response.send_message(f"✅ У {сотрудник.mention} нет выговоров", ephemeral=True)
        return
    embed = discord.Embed(title=f"📋 Выговоры: {сотрудник.display_name}", color=0xf1c40f)
    for warn in warns[-5:]:
        embed.add_field(name=f"Выговор №{warn['id']} от {warn['date'][:10]}", value=f"Причина: {warn['reason']}\nМодератор: {warn['moderator']}", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== ЗАПУСК ====================
@bot.event
async def on_ready():
    print(f"✅ Бот запущен: {bot.user}")
    check_new_applications.start()

    try:
        await bot.tree.clear_commands()  # удаляем старые команды
        synced = await bot.tree.sync()
        print(f"✅ Команд загружено: {len(synced)}")
        for cmd in synced:
            print(f"   - /{cmd.name}")
    except Exception as e:
        print(f"❌ Ошибка синхронизации: {e}")

keep_alive()
TOKEN = os.environ.get("DISCORD_TOKEN")

if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ Токен не найден")

