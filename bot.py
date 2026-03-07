import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

TOKEN = os.environ["DISCORD_TOKEN"]

SERVER_ID = 1478825198957367339

CHANNELS = {
    "ss": 1479554031444689009,
    "applications": 1479581481444839537
}

ROLE_WARN = "Выговор"

SPREADSHEET_ID = "1zL5rRk-zny2riAdRSUl2ZiA-pK76--dGdSJObuVLZRs"
SHEET_NAME = "Ответы на форму (1)"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

guild_obj = discord.Object(id=SERVER_ID)

DATA_FILE = "bot_data.json"

# ================= ДАННЫЕ =================

def load_data():
    try:
        with open(DATA_FILE,"r",encoding="utf-8") as f:
            return json.load(f)
    except:
        return {
            "warns":{},
            "schedule":[],
            "stats":{"news":0,"reports":0},
            "last_row":0,
            "application_messages":[],
            "interviews":[]
        }

def save_data(data):
    with open(DATA_FILE,"w",encoding="utf-8") as f:
        json.dump(data,f,ensure_ascii=False,indent=4)

# ================= GOOGLE =================

def get_google_sheet():

    try:
        scope=[
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]

        creds_dict=json.loads(os.environ["GOOGLE_CREDENTIALS"])
        creds_dict["private_key"]=creds_dict["private_key"].replace("\\n","\n")

        creds=ServiceAccountCredentials.from_json_keyfile_dict(creds_dict,scope)

        client=gspread.authorize(creds)

        sheet=client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

        return sheet

    except Exception as e:

        print("Ошибка Google:",e)

        return None

# ================= ПРОВЕРКА ЗАЯВОК =================

@tasks.loop(seconds=30)
async def check_new_applications():

    sheet=get_google_sheet()

    if not sheet:
        return

    try:

        records=sheet.get_all_records()

        data=load_data()

        last_row=data["last_row"]

        if len(records)>last_row:

            print("Новые заявки:",len(records)-last_row)

            for i in range(last_row,len(records)):

                await send_application_to_channel(records[i])

            data["last_row"]=len(records)

            save_data(data)

    except Exception as e:

        print("Ошибка проверки:",e)

# ================= ОТПРАВКА ЗАЯВКИ =================

async def send_application_to_channel(record):

    channel=bot.get_channel(CHANNELS["ss"])

    if not channel:
        print("Канал СС не найден")
        return

    name=record.get("Имя Фамилия (IC)","Не указано")
    hours=record.get("Часов в паспорте","Не указано")
    discord_name=record.get("Имя пользователя в ДС (ivanov1234)","Не указано")

    docs="Не указано"

    for key in record.keys():

        if "Паспорт" in key:

            docs=record[key]

            break

    embed=discord.Embed(
        title="📋 НОВАЯ ЗАЯВКА НА ТРУДОУСТРОЙСТВО",
        description="Кто-то хочет работать в телекомпании!",
        color=0x3498db,
        timestamp=datetime.now()
    )

    embed.add_field(name="👤 Имя Фамилия",value=name,inline=True)
    embed.add_field(name="⏰ Часов в паспорте",value=hours,inline=True)

    if docs.startswith(("http://","https://")):
        embed.add_field(name="📎 Документы",value=f"[Ссылка]({docs})",inline=True)
    else:
        embed.add_field(name="📎 Документы",value=docs,inline=True)

    embed.add_field(name="💬 Discord",value=discord_name,inline=False)

    msg=await channel.send(embed=embed)

    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    await msg.add_reaction("📞")
    await msg.add_reaction("📋")

    data=load_data()

    data["application_messages"].append({
        "message_id":msg.id,
        "name":name,
        "discord":discord_name,
        "hours":hours,
        "docs":docs
    })

    save_data(data)

# ================= РЕАКЦИИ =================

@bot.event
async def on_raw_reaction_add(payload):

    if payload.user_id==bot.user.id:
        return

    if payload.channel_id!=CHANNELS["ss"]:
        return

    channel=bot.get_channel(payload.channel_id)

    message=await channel.fetch_message(payload.message_id)

    if message.author.id!=bot.user.id:
        return

    guild=bot.get_guild(payload.guild_id)

    user=guild.get_member(payload.user_id)

    data=load_data()

    application_data=None

    for app in data["application_messages"]:

        if app["message_id"]==payload.message_id:

            application_data=app

            break

    if not application_data:
        return

    embed=message.embeds[0]

    results_channel=bot.get_channel(CHANNELS["applications"])

    emoji=str(payload.emoji)

    if emoji=="✅":

        embed.title="✅ ЗАЯВКА ПРИНЯТА"
        embed.color=0x2ecc71

        await message.edit(embed=embed)

        if results_channel:

            await results_channel.send(
                f"✅ **Заявка принята**\n"
                f"👤 {application_data['name']}\n"
                f"Администратор: {user.mention}"
            )

    elif emoji=="❌":

        embed.title="❌ ЗАЯВКА ОТКЛОНЕНА"
        embed.color=0xe74c3c

        await message.edit(embed=embed)

        if results_channel:

            await results_channel.send(
                f"❌ **Заявка отклонена**\n"
                f"👤 {application_data['name']}\n"
                f"Администратор: {user.mention}"
            )

    elif emoji=="📞":

        await channel.send(f"📞 {user.mention} свяжется с кандидатом")

    elif emoji=="📋":

        embed.title="📋 ЗАЯВКА В РАССМОТРЕНИИ"
        embed.color=0xf1c40f

        await message.edit(embed=embed)

        await channel.send(f"📋 Заявка взята в рассмотрение {user.mention}")

# ================= КОМАНДЫ =================

@bot.tree.command(name="новости",description="Отправить новость",guild=guild_obj)
async def news(interaction:discord.Interaction,заголовок:str,текст:str):

    embed=discord.Embed(
        title=f"📰 {заголовок}",
        description=текст,
        color=0x3498db,
        timestamp=datetime.now()
    )

    embed.set_footer(text=f"Автор: {interaction.user}")

    await interaction.channel.send(embed=embed)

    await interaction.response.send_message("Новость отправлена",ephemeral=True)

@bot.tree.command(name="репортаж",description="Сделать репортаж",guild=guild_obj)
async def report(interaction:discord.Interaction,место:str,текст:str):

    embed=discord.Embed(
        title=f"🎥 РЕПОРТАЖ ИЗ {место}",
        description=текст,
        color=0xe67e22,
        timestamp=datetime.now()
    )

    await interaction.channel.send(embed=embed)

    await interaction.response.send_message("Репортаж отправлен",ephemeral=True)

@bot.tree.command(name="выговор",description="Выдать выговор",guild=guild_obj)
async def warn(interaction:discord.Interaction,пользователь:discord.Member,причина:str):

    data=load_data()

    user_id=str(пользователь.id)

    if user_id not in data["warns"]:
        data["warns"][user_id]=[]

    warn_id=len(data["warns"][user_id])+1

    data["warns"][user_id].append({
        "id":warn_id,
        "reason":причина,
        "moderator":interaction.user.name,
        "date":str(datetime.now())
    })

    save_data(data)

    role=discord.utils.get(interaction.guild.roles,name=ROLE_WARN)

    if role:
        await пользователь.add_roles(role)

    await interaction.response.send_message(
        f"⚠ Выговор №{warn_id} выдан {пользователь.mention}"
    )

@bot.tree.command(name="выговоры",description="Посмотреть выговоры",guild=guild_obj)
async def warns(interaction:discord.Interaction,пользователь:discord.Member):

    data=load_data()

    user_id=str(пользователь.id)

    if user_id not in data["warns"]:

        await interaction.response.send_message("Выговоров нет")

        return

    text=""

    for w in data["warns"][user_id]:

        text+=f"№{w['id']} | {w['reason']} | {w['moderator']}\n"

    await interaction.response.send_message(text)

@bot.tree.command(name="расписание",description="Показать расписание",guild=guild_obj)
async def schedule(interaction:discord.Interaction):

    data=load_data()

    if not data["schedule"]:

        await interaction.response.send_message("Расписание пусто")

        return

    embed=discord.Embed(title="📅 Расписание",color=0x3498db)

    for item in data["schedule"]:

        embed.add_field(name=item["date"],value=item["topic"],inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="записаться",description="Записаться на интервью",guild=guild_obj)
async def interview(interaction:discord.Interaction,дата:str,время:str):

    data=load_data()

    data["interviews"].append({
        "user":interaction.user.name,
        "date":дата,
        "time":время
    })

    save_data(data)

    await interaction.response.send_message(
        f"Вы записаны на интервью {дата} {время}"
    )

@bot.tree.command(name="проверить_заявки",description="Проверить заявки",guild=guild_obj)
async def check_now(interaction:discord.Interaction):

    await interaction.response.send_message("Проверяю...",ephemeral=True)

    await check_new_applications()

    await interaction.followup.send("Готово",ephemeral=True)

# ================= READY =================

@bot.event
async def on_ready():

    print("Бот запущен как",bot.user)

    check_new_applications.start()

    synced=await bot.tree.sync(guild=guild_obj)

    print("Команд синхронизировано:",len(synced))

# ================= СТАРТ =================

bot.run(TOKEN)
