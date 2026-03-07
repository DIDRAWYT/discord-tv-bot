import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import base64
from keep_alive import keep_alive

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# ID каналов
CHANNELS = {
    'ss': 1479554031444689009,
    'schedule': 1478826477880344586,
    'news': 1479458023146651689,
    'reports': 1479458060866162880,
    'applications': 1479581481444839537
}

ALLOWED_ROLES = ['Директор', 'Заместитель Директора']
WARN_ROLE = "Выговор"

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
            'schedule': [],
            'last_row': 0,
            'application_messages': []
        }


def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def check_permissions(interaction):
    roles = [r.name for r in interaction.user.roles]
    return any(r in ALLOWED_ROLES for r in roles)


# ================= GOOGLE =================

def get_google_sheet():

    try:

        creds_json = os.environ.get('GOOGLE_CREDENTIALS')

        if creds_json:

            creds_dict = json.loads(creds_json)

            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ]

            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

        else:

            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ]

            creds = ServiceAccountCredentials.from_json_keyfile_name('google-key.json', scope)

        client = gspread.authorize(creds)

        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

        print("✅ Google Sheets подключён")

        return sheet

    except Exception as e:

        print("Google ошибка:", e)

        return None

# ================= ЗАЯВКИ =================

@tasks.loop(seconds=30)
async def check_new_applications():

    sheet = get_google_sheet()

    if not sheet:
        return

    try:

        all_records = sheet.get_all_records()

        data = load_data()

        last_row = data.get("last_row", 0)

        if len(all_records) > last_row:

            for i in range(last_row, len(all_records)):

                record = all_records[i]

                await send_application_to_channel(record)

            data['last_row'] = len(all_records)

            save_data(data)

    except Exception as e:
        print("Ошибка проверки:", e)


async def send_application_to_channel(record):

    channel = bot.get_channel(CHANNELS['ss'])

    if not channel:
        print("Канал СС не найден")
        return

    name = record.get('Имя Фамилия (IC)', 'Не указано')
    hours = record.get('Часов в паспорте', 'Не указано')
    discord_name = record.get('Имя пользователя в ДС (ivanov1234)', 'Не указано')

    docs = "Не указано"

    for key in record.keys():
        if "Паспорт" in key:
            docs = record[key]

    embed = discord.Embed(
        title="НОВАЯ ЗАЯВКА",
        color=0x3498db,
        timestamp=datetime.now()
    )

    embed.add_field(name="Имя", value=name)
    embed.add_field(name="Часы", value=hours)
    embed.add_field(name="Discord", value=discord_name)

    msg = await channel.send(embed=embed)

    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    await msg.add_reaction("📋")
    await msg.add_reaction("📞")

    data = load_data()

    data['application_messages'].append({
        "message_id": msg.id,
        "name": name,
        "hours": hours,
        "discord": discord_name,
        "docs": docs
    })

    save_data(data)


# ================= РЕАКЦИИ =================

@bot.event
async def on_raw_reaction_add(payload):

    if payload.user_id == bot.user.id:
        return

    if payload.channel_id != CHANNELS['ss']:
        return

    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)

    guild = bot.get_guild(payload.guild_id)
    user = guild.get_member(payload.user_id)

    data = load_data()

    app = None

    for a in data['application_messages']:
        if a['message_id'] == payload.message_id:
            app = a

    if not app:
        return

    results_channel = bot.get_channel(CHANNELS['applications'])

    emoji = str(payload.emoji)

    embed = discord.Embed(
        timestamp=datetime.now()
    )

    embed.add_field(name="Имя", value=app['name'])
    embed.add_field(name="Часы", value=app['hours'])
    embed.add_field(name="Discord", value=app['discord'])

    if emoji == "✅":

        embed.title = "ЗАЯВКА ПРИНЯТА"
        embed.color = 0x2ecc71
        embed.add_field(name="Решение", value=f"Принял {user.mention}")

        await message.edit(embed=embed)

        if results_channel:
            await results_channel.send(embed=embed)

    elif emoji == "❌":

        embed.title = "ЗАЯВКА ОТКЛОНЕНА"
        embed.color = 0xe74c3c
        embed.add_field(name="Решение", value=f"Отклонил {user.mention}")

        await message.edit(embed=embed)

        if results_channel:
            await results_channel.send(embed=embed)

    elif emoji == "📋":

        await channel.send(f"{user.mention} взял заявку на рассмотрение")

    elif emoji == "📞":

        await channel.send(f"{user.mention} проведет интервью")

    await message.remove_reaction(payload.emoji, user)


# ================= КОМАНДЫ =================

@bot.tree.command(name="новости")
async def news(interaction: discord.Interaction, текст: str):

    if not check_permissions(interaction):
        return await interaction.response.send_message("Нет прав")

    channel = bot.get_channel(CHANNELS['news'])

    embed = discord.Embed(
        title="НОВОСТИ",
        description=текст,
        color=0x3498db
    )

    await channel.send(embed=embed)

    await interaction.response.send_message("Новость отправлена", ephemeral=True)


@bot.tree.command(name="репортаж")
async def report(interaction: discord.Interaction, текст: str):

    if not check_permissions(interaction):
        return await interaction.response.send_message("Нет прав")

    channel = bot.get_channel(CHANNELS['reports'])

    embed = discord.Embed(
        title="РЕПОРТАЖ",
        description=текст,
        color=0xe67e22
    )

    await channel.send(embed=embed)

    await interaction.response.send_message("Репортаж отправлен", ephemeral=True)


@bot.tree.command(name="выговор")
async def warn(interaction: discord.Interaction, пользователь: discord.Member, причина: str):

    if not check_permissions(interaction):
        return await interaction.response.send_message("Нет прав")

    role = discord.utils.get(interaction.guild.roles, name=WARN_ROLE)

    if role:
        await пользователь.add_roles(role)

    await interaction.response.send_message(
        f"{пользователь.mention} получил выговор\nПричина: {причина}"
    )


# ================= SYNC =================

@bot.command()
async def sync(ctx):

    if ctx.author.guild_permissions.administrator:

        synced = await bot.tree.sync()

        await ctx.send(f"Синхронизировано {len(synced)} команд")


# ================= READY =================

@bot.event
async def on_ready():

    print("Бот запущен:", bot.user)

    check_new_applications.start()

    synced = await bot.tree.sync()

    print("Команд:", len(synced))


keep_alive()

TOKEN = os.environ.get("DISCORD_TOKEN")

bot.run(TOKEN)


