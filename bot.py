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

CHANNELS = {
    'ss': 1479554031444689009,
    'schedule': 1478826477880344586,
    'news': 1479458023146651689,
    'reports': 1479458060866162880,
    'applications': 1479581481444839537
}

ALLOWED_ROLES = ['Директор', 'Заместитель Директора']

SPREADSHEET_ID = '1zL5rRk-zny2riAdRSUl2ZiA-pK76--dGdSJObuVLZRs'
SHEET_NAME = 'Ответы на форму (1)'

DATA_FILE = 'bot_data.json'

# ================= ДАННЫЕ =================

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

# ================= GOOGLE SHEETS =================

def get_google_sheet():
    try:

        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]

        creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])

        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

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

    if docs and docs.startswith(("http://", "https://")):
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

        embed = message.embeds[0]

        if str(payload.emoji) == "✅":

            embed.color = 0x2ecc71
            embed.title = "✅ ЗАЯВКА ПРИНЯТА"

            await message.edit(embed=embed)

            await channel.send(f"✅ Заявка принята {user.mention}")

        elif str(payload.emoji) == "❌":

            embed.color = 0xe74c3c
            embed.title = "❌ ЗАЯВКА ОТКЛОНЕНА"

            await message.edit(embed=embed)

            await channel.send(f"❌ Заявка отклонена {user.mention}")

        elif str(payload.emoji) == "📞":

            await channel.send(f"📞 {user.mention} свяжется с кандидатом")

        elif str(payload.emoji) == "📋":

            embed.color = 0xf1c40f
            embed.title = "📋 ЗАЯВКА В РАССМОТРЕНИИ"

            await message.edit(embed=embed)

            await channel.send(f"📋 Заявка рассматривается {user.mention}")

        await message.remove_reaction(payload.emoji, user)

    except Exception as e:
        print(f"Ошибка реакции: {e}")

# ================= ЗАПУСК =================

@bot.event
async def on_ready():
    print(f'✅ Бот запущен как {bot.user}')

    check_new_applications.start()

    try:
        guild = discord.Object(id=1478825198957367339)
        synced = await bot.tree.sync(guild=guild)
        print(f"✅ Команд синхронизировано: {len(synced)}")
    except Exception as e:
        print(e)

    print("✅ Бот готов")

@bot.command()
async def sync(ctx):

    if ctx.author.guild_permissions.administrator:

        await bot.tree.sync()

        await ctx.send("✅ Команды синхронизированы")

    else:

        await ctx.send("❌ Нет прав")

# ================= ЗАПУСК СЕРВЕРА =================

keep_alive()

TOKEN = os.environ["DISCORD_TOKEN"]

bot.run(TOKEN)


