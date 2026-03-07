import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from keep_alive import keep_alive

TOKEN = os.environ["DISCORD_TOKEN"]

SERVER_ID = 1478825198957367339

CHANNELS = {
    "ss": 1479554031444689009,
    "applications": 1479581481444839537
}

SPREADSHEET_ID = "1zL5rRk-zny2riAdRSUl2ZiA-pK76--dGdSJObuVLZRs"
SHEET_NAME = "Ответы на форму (1)"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

guild_obj = discord.Object(id=SERVER_ID)

DATA_FILE = "bot_data.json"


# ================= DATA =================

def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "warns": {},
            "schedule": [],
            "stats": {"news": 0, "reports": 0},
            "last_row": 0,
            "application_messages": []
        }


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# ================= GOOGLE =================

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

        print("❌ Ошибка Google Sheets:", e)

        return None


# ================= ПРОВЕРКА ЗАЯВОК =================

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

            print(f"🔍 Новых заявок: {len(all_records)-last_row}")

            for i in range(last_row, len(all_records)):
                await send_application_to_channel(all_records[i])

            data["last_row"] = len(all_records)

            save_data(data)

    except Exception as e:

        print("Ошибка проверки:", e)


# ================= ОТПРАВКА ЗАЯВКИ =================

async def send_application_to_channel(record):

    channel = bot.get_channel(CHANNELS["ss"])

    if not channel:
        print("❌ Канал СС не найден")
        return

    name = record.get("Имя Фамилия (IC)", "Не указано")
    hours = record.get("Часов в паспорте", "Не указано")
    discord_name = record.get("Имя пользователя в ДС (ivanov1234)", "Не указано")

    docs = "Не указано"

    for key in record.keys():

        if "Паспорт" in key:
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

    if docs.startswith(("http://", "https://")):
        embed.add_field(name="📎 Документы", value=f"[Ссылка]({docs})", inline=True)
    else:
        embed.add_field(name="📎 Документы", value=docs, inline=True)

    embed.add_field(name="💬 Discord", value=discord_name, inline=False)

    embed.set_footer(text=f"Заявка получена: {datetime.now().strftime('%d.%m.%Y %H:%M')}")

    msg = await channel.send(embed=embed)

    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    await msg.add_reaction("📞")
    await msg.add_reaction("📋")

    data = load_data()

    data["application_messages"].append({
        "message_id": msg.id,
        "name": name,
        "discord": discord_name,
        "hours": hours,
        "docs": docs
    })

    save_data(data)

    print(f"✅ Заявка от {name} отправлена")


# ================= РЕАКЦИИ =================

@bot.event
async def on_raw_reaction_add(payload):

    if payload.user_id == bot.user.id:
        return

    if payload.channel_id != CHANNELS["ss"]:
        return

    channel = bot.get_channel(payload.channel_id)

    message = await channel.fetch_message(payload.message_id)

    if message.author.id != bot.user.id:
        return

    guild = bot.get_guild(payload.guild_id)

    user = guild.get_member(payload.user_id)

    data = load_data()

    application_data = None

    for app in data["application_messages"]:
        if app["message_id"] == payload.message_id:
            application_data = app
            break

    if not application_data:
        return

    embed = message.embeds[0]

    results_channel = bot.get_channel(CHANNELS["applications"])

    emoji = str(payload.emoji)

    if emoji == "✅":

        embed.color = 0x2ecc71
        embed.title = "✅ ЗАЯВКА ПРИНЯТА"

        await message.edit(embed=embed)

        if results_channel:

            await results_channel.send(
                f"✅ **Заявка принята**\n"
                f"👤 {application_data['name']}\n"
                f"👨‍💼 Администратор: {user.mention}"
            )

    elif emoji == "❌":

        embed.color = 0xe74c3c
        embed.title = "❌ ЗАЯВКА ОТКЛОНЕНА"

        await message.edit(embed=embed)

        if results_channel:

            await results_channel.send(
                f"❌ **Заявка отклонена**\n"
                f"👤 {application_data['name']}\n"
                f"👨‍💼 Администратор: {user.mention}"
            )

    elif emoji == "📞":

        await channel.send(f"📞 {user.mention} свяжется с кандидатом")

    elif emoji == "📋":

        embed.color = 0xf1c40f
        embed.title = "📋 ЗАЯВКА В РАССМОТРЕНИИ"

        await message.edit(embed=embed)

        await channel.send(f"📋 Заявка взята в рассмотрение {user.mention}")

    await message.remove_reaction(payload.emoji, user)


# ================= КОМАНДА ПРОВЕРКИ =================

@bot.tree.command(name="проверить_заявки", description="Проверить заявки")
async def check_now(interaction: discord.Interaction):

    await interaction.response.send_message("🔄 Проверяю заявки...", ephemeral=True)

    await check_new_applications()

    await interaction.followup.send("✅ Проверка завершена", ephemeral=True)


# ================= READY =================

@bot.event
async def on_ready():

    print(f"Бот запущен как {bot.user}")

    check_new_applications.start()

    synced = await bot.tree.sync(guild=guild_obj)

    print(f"Команд синхронизировано: {len(synced)}")


# ================= START =================

keep_alive()

bot.run(TOKEN)
