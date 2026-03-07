# ==================== КОМАНДЫ ====================

# /вакансии
@bot.tree.command(name="вакансии", description="Посмотреть вакансии и подать заявку")
async def vacancies(interaction: discord.Interaction):
    embed = discord.Embed(
        title="💼 РАБОТА В ТЕЛЕКОМПАНИИ",
        description="Мы ищем сотрудников!",
        color=0x3498db
    )
    embed.add_field(name="Открытые вакансии", value="• Корреспондент\n• Оператор\n• Звукорежиссёр\n• Редактор\n• Ведущий\n• Монтажёр", inline=False)
    embed.add_field(name="Как подать заявку", value="1. Нажмите кнопку ниже\n2. Заполните анкету", inline=False)
    view = discord.ui.View()
    button = discord.ui.Button(label="📋 Заполнить анкету", style=discord.ButtonStyle.link,
                               url="https://docs.google.com/forms/d/e/1FAIpQLSdwCAGosL-YaKsqGNzpkjfWMqF8yZbtWpbpIaRrRR2J5luR2A/viewform")
    view.add_item(button)
    await interaction.response.send_message(embed=embed, view=view)

# /новости
@bot.tree.command(name="новости", description="Отправить новость")
@app_commands.describe(заголовок="Заголовок новости", текст="Текст новости")
async def news(interaction: discord.Interaction, заголовок: str, текст: str):
    if not check_permissions(interaction):
        await interaction.response.send_message("❌ Нет прав", ephemeral=True)
        return
    channel = bot.get_channel(1479458023146651689)
    if channel:
        embed = discord.Embed(title=f"📰 {заголовок}", description=текст, color=0x3498db, timestamp=datetime.now())
        embed.set_footer(text=f"От {interaction.user.display_name}")
        await channel.send(embed=embed)
        data = load_data()
        data['stats']['news'] = data['stats'].get('news', 0) + 1
        save_data(data)
        await interaction.response.send_message("✅ Новость опубликована", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Канал не найден", ephemeral=True)

# /репортаж
@bot.tree.command(name="репортаж", description="Отправить репортаж")
@app_commands.describe(место="Место", текст="Текст репортажа")
async def report(interaction: discord.Interaction, место: str, текст: str):
    if not check_permissions(interaction):
        await interaction.response.send_message("❌ Нет прав", ephemeral=True)
        return
    channel = bot.get_channel(1479458060866162880)
    if channel:
        embed = discord.Embed(title=f"🎥 РЕПОРТАЖ ИЗ {место}", description=текст, color=0xe67e22, timestamp=datetime.now())
        embed.set_footer(text=f"Корреспондент: {interaction.user.display_name}")
        await channel.send(embed=embed)
        data = load_data()
        data['stats']['reports'] = data['stats'].get('reports', 0) + 1
        save_data(data)
        await interaction.response.send_message("✅ Репортаж опубликован", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Канал не найден", ephemeral=True)

# /интервью
@bot.tree.command(name="интервью", description="Записаться на интервью")
@app_commands.describe(имя="Имя Фамилия", контакт="Discord или телефон")
async def interview(interaction: discord.Interaction, имя: str, контакт: str):
    channel = bot.get_channel(APPLICATIONS_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="📞 ЗАПИСЬ НА ИНТЕРВЬЮ",
            description=f"{имя} хочет пройти интервью",
            color=0x9b59b6,
            timestamp=datetime.now()
        )
        embed.add_field(name="Контакт", value=контакт, inline=False)
        await channel.send(embed=embed)
        await interaction.response.send_message("✅ Вы записаны на интервью", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Канал заявок не найден", ephemeral=True)

# /статистика
@bot.tree.command(name="статистика", description="Посмотреть статистику новостей и репортажей")
async def statistics(interaction: discord.Interaction):
    data = load_data()
    embed = discord.Embed(title="📊 СТАТИСТИКА", color=0x1abc9c)
    embed.add_field(name="Новости", value=data['stats'].get('news',0), inline=True)
    embed.add_field(name="Репортажи", value=data['stats'].get('reports',0), inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# /добавить_в_расписание
@bot.tree.command(name="добавить_в_расписание", description="Добавить событие в расписание")
@app_commands.describe(дата="Дата события", пользователь="Пользователь", тема="Тема")
async def add_schedule(interaction: discord.Interaction, дата: str, пользователь: str, тема: str):
    if not check_permissions(interaction):
        await interaction.response.send_message("❌ Нет прав", ephemeral=True)
        return
    data = load_data()
    data.setdefault('schedule', []).append({'date': дата, 'user': пользователь, 'topic': тема})
    save_data(data)
    await interaction.response.send_message("✅ Событие добавлено в расписание", ephemeral=True)

# /расписание
@bot.tree.command(name="расписание", description="Показать расписание")
async def show_schedule(interaction: discord.Interaction):
    data = load_data()
    if not data.get('schedule'):
        await interaction.response.send_message("📅 Расписание пусто", ephemeral=True)
        return
    embed = discord.Embed(title="📅 РАСПИСАНИЕ", color=0x3498db)
    for i, item in enumerate(data['schedule'][-10:],1):
        embed.add_field(name=f"{i}. {item['date']}", value=f"**{item['user']}**\n{item['topic']}", inline=False)
    await interaction.response.send_message(embed=embed)
