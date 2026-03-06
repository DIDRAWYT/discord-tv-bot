import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from keep_alive import keep_alive

# ================= НАСТРОЙКИ =================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix='!', intents=intents)

# ================= КАНАЛЫ И РОЛИ =================
CHANNELS = {
    'ss': 1479554031444689009,
    'schedule': 1478826477880344586,
    'news': 1479458023146651689,
    'reports': 1479458060866162880,
    'applications': 1479581481444839537
}

ALLOWED_ROLES = ['Директор', 'Заместитель Директора']

# ================= GOOGLE SHEETS =================
SPREADSHEET_ID = '1zL5rRk-zny2riAdRSUl2ZiA-pK76--dGdSJObuVLZRs'
SHEET_NAME = 'Ответы на форму (1)'

DATA_FILE = 'bot_data.json'

def load_data():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {
            'warns': {},
            'requests': [],
            'schedule': [],
            'stats': {'news': 0, 'reports': 0},
            'last_row': 0
        }

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def check_permissions(interaction):
    user_roles = [role.name for role in interaction.user.roles]
    return any(role in ALLOWED_ROLES for role in user_roles)

def get_google_sheet():
    try:
        scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n","\n")
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        return sheet
    except Exception as e:
        print(f"❌ Ошибка подключения к Google Sheets: {e}")
        return None

# ================= ПРОВЕРКА ЗАЯВОК =================
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
        last_row = data.get('last_row', 0)
        if len(all_records) > last_row:
            print(f"🔍 Новых заявок: {len(all_records) - last_row}")
            for i in range(last_row, len(all_records)):
                record = all_records[i]
                await send_application_to_channel(record)
            data['last_row'] = len(all_records)
            save_data(data)
    except Exception as e:
        print(f"❌ Ошибка при проверке заявок: {e}")

async def send_application_to_channel(record):
    channel = bot.get_channel(CHANNELS['ss'])
    if not channel:
        print("❌ Канал не найден")
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
        title="📋 НОВАЯ ЗАЯВКА НА ТРУДОУСТРОЙСТВО",
        description="Кто-то хочет работать в телекомпании!",
        color=0x3498db,
        timestamp=datetime.now()
    )
    embed.add_field(name="👤 Имя Фамилия", value=name, inline=True)
    embed.add_field(name="⏰ Часов в паспорте", value=hours, inline=True)
    if docs.startswith(("http://","https://")):
        embed.add_field(name="📎 Документы", value=f"[Ссылка]({docs})", inline=True)
    else:
        embed.add_field(name="📎 Документы", value=docs, inline=True)
    embed.add_field(name="💬 Discord", value=discord_name, inline=False)
    msg = await channel.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    await msg.add_reaction("📞")
    await msg.add_reaction("📋")
    print(f"✅ Заявка от {name} отправлена")

# ================= SLASH-КОМАНДЫ =================
@bot.event
async def on_ready():
    print(f'✅ Бот запущен как {bot.user}')
    check_new_applications.start()
    try:
        guild = discord.Object(id=1478825198957367339)  # <-- вставь сюда свой ID сервера
        synced = await bot.tree.sync(guild=guild)
        print(f"✅ Команд синхронизировано: {len(synced)}")
    except Exception as e:
        print(e)
    print("✅ Бот готов")

guild_obj = discord.Object(id=1478825198957367339)  # <-- вставь сюда свой ID сервера

# ===== /вакансии =====
@bot.tree.command(name="вакансии", description="Посмотреть вакансии и подать заявку", guild=guild_obj)
async def vacancies(interaction: discord.Interaction):
    embed = discord.Embed(
        title="💼 РАБОТА В ТЕЛЕКОМПАНИИ",
        description="Мы ищем талантливых сотрудников!",
        color=0x3498db
    )
    embed.add_field(
        name="📹 Открытые вакансии",
        value="• Корреспондент\n• Оператор\n• Звукорежиссёр\n• Редактор\n• Ведущий\n• Монтажёр",
        inline=False
    )
    embed.add_field(
        name="📝 Как подать заявку",
        value="1. Нажмите кнопку ниже\n2. Заполните анкету\n3. Заявка появится у администрации",
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

# ===== /проверить_заявки =====
@bot.tree.command(name="проверить_заявки", description="Принудительно проверить новые заявки", guild=guild_obj)
async def check_now(interaction: discord.Interaction):
    if not check_permissions(interaction):
        await interaction.response.send_message("❌ Нет прав", ephemeral=True)
        return
    await interaction.response.send_message("🔄 Проверяю заявки...", ephemeral=True)
    await check_new_applications()
    await interaction.followup.send("✅ Проверка завершена", ephemeral=True)

# ===== /новости =====
@bot.tree.command(name="новости", description="Отправить новость", guild=guild_obj)
@app_commands.describe(заголовок="Заголовок новости", текст="Текст новости")
async def news(interaction: discord.Interaction, заголовок: str, текст: str):
    if not check_permissions(interaction):
        await interaction.response.send_message("❌ Нет прав", ephemeral=True)
        return
    channel = bot.get_channel(CHANNELS['news'])
    if channel:
        embed = discord.Embed(title=f"📰 {заголовок}", description=текст, color=0x3498db, timestamp=datetime.now())
        embed.set_footer(text=f"От {interaction.user.display_name}")
        await channel.send(embed=embed)
        data = load_data()
        data['stats']['news'] += 1
        save_data(data)
        await interaction.response.send_message("✅ Новость опубликована", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Канал не найден", ephemeral=True)

# ===== /репортаж =====
@bot.tree.command(name="репортаж", description="Отправить репортаж", guild=guild_obj)
@app_commands.describe(место="Откуда репортаж", текст="Текст репортажа")
async def report(interaction: discord.Interaction, место: str, текст: str):
    if not check_permissions(interaction):
        await interaction.response.send_message("❌ Нет прав", ephemeral=True)
        return
    channel = bot.get_channel(CHANNELS['reports'])
    if channel:
        embed = discord.Embed(title=f"🎥 РЕПОРТАЖ ИЗ {место}", description=текст, color=0xe67e22, timestamp=datetime.now())
        embed.set_footer(text=f"Корреспондент: {interaction.user.display_name}")
        await channel.send(embed=embed)
        data = load_data()
        data['stats']['reports'] += 1
        save_data(data)
        await interaction.response.send_message("✅ Репортаж опубликован", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Канал не найден", ephemeral=True)

# ===== /выговор =====
@bot.tree.command(name="выговор", description="Выдать выговор сотруднику", guild=guild_obj)
@app_commands.describe(сотрудник="Сотрудник", причина="Причина выговора")
async def warn(interaction: discord.Interaction, сотрудник: discord.Member, причина: str):
    if not check_permissions(interaction):
        await interaction.response.send_message("❌ Нет прав", ephemeral=True)
        return
    data = load_data()
    user_id = str(сотрудник.id)
    if user_id not in data['warns']:
        data['warns'][user_id] = []
    warn_data = {'id': len(data['warns'][user_id])+1, 'reason': причина, 'moderator': interaction.user.name, 'date': str(datetime.now())}
    data['warns'][user_id].append(warn_data)
    save_data(data)
    await interaction.response.send_message(f"✅ Выговор №{warn_data['id']} выдан {сотрудник.mention}", ephemeral=True)

# ===== /выговоры =====
@bot.tree.command(name="выговоры", description="Показать выговоры сотрудника", guild=guild_obj)
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
    embed = discord.Embed(title=f"📋 Выговоры: {сотрудник.display_name}", color=0xf1c40f)
    for warn in data['warns'][user_id][-5:]:
        embed.add_field(name=f"Выговор №{warn['id']} от {warn['date'][:10]}", value=f"Причина: {warn['reason']}\nМодератор: {warn['moderator']}", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ===== /расписание =====
@bot.tree.command(name="расписание", description="Показать расписание", guild=guild_obj)
async def show_schedule(interaction: discord.Interaction):
    data = load_data()
    if not data['schedule']:
        await interaction.response.send_message("📅 Расписание пусто", ephemeral=True)
        return
    embed = discord.Embed(title="📅 РАСПИСАНИЕ", color=0x3498db)
    for i, item in enumerate(data['schedule'][-10:], 1):
        embed.add_field(name=f"{i}. {item['date']}", value=f"**{item['user']}**\n{item['topic']}", inline=False)
    await interaction.response.send_message(embed=embed)

# ================= РЕАКЦИИ =================
@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return
    if payload.channel_id != CHANNELS['ss']:
        return
    try:
        channel = bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        guild = bot.get_guild(payload.guild_id)
        user = guild.get_member(payload.user_id)
        original_embed = message.embeds[0]
        results_channel = bot.get_channel(CHANNELS['applications'])
        if str(payload.emoji) == "✅":
            original_embed.color = 0x2ecc71
            original_embed.title = "✅ ЗАЯВКА ПРИНЯТА"
            await message.edit(embed=original_embed)
            if results_channel:
                result_embed = discord.Embed(title="✅ ЗАЯВКА ПРИНЯТА", color=0x2ecc71, timestamp=datetime.now())
                for field in original_embed.fields:
                    result_embed.add_field(name=field.name, value=field.value, inline=field.inline)
                result_embed.add_field(name="Решение принял", value=user.mention, inline=True)
                result_embed.add_field(name="Дата решения", value=datetime.now().strftime('%d.%m.%Y %H:%M'), inline=True)
                if original_embed.description:
                    result_embed.description = original_embed.description
                result_embed.set_footer(text=f"ID заявки: {message.id}")
                await results_channel.send(embed=result_embed)
            await channel.send(f"✅ Заявка принята администратором {user.mention}")
        elif str(payload.emoji) == "❌":
            original_embed.color = 0xe74c3c
            original_embed.title = "❌ ЗАЯВКА ОТКЛОНЕНА"
            await message.edit(embed=original_embed)
            if results_channel:
                result_embed = discord.Embed(title="❌ ЗАЯВКА ОТКЛОНЕНА", color=0xe74c3c, timestamp=datetime.now())
                for field in original_embed.fields:
                    result_embed.add_field(name=field.name, value=field.value, inline=field.inline)
                result_embed.add_field(name="Решение принял", value=user.mention, inline=True)
                result_embed.add_field(name="Дата решения", value=datetime.now().strftime('%d.%m.%Y %H:%M'), inline=True)
                if original_embed.description:
                    result_embed.description = original_embed.description
                result_embed.set_footer(text=f"ID заявки: {message.id}")
                await results_channel.send(embed=result_embed)
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
        print(f"Ошибка реакции: {e}")

# ================= ЗАПУСК =================
keep_alive()
TOKEN = os.environ["DISCORD_TOKEN"]
bot.run(TOKEN)
