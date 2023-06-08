import discord
import logging
import logging.handlers
import json
import asyncio
import random
from discord import app_commands
from discord.ext import commands, tasks

# Get keys
with open('keys.json', 'r') as f:
	keys = json.load(f)

# Define Bot Client and Console
client = commands.Bot(command_prefix="?", case_insensitive=True, intents=discord.Intents.all())
client.remove_command('help')

# Logging settings
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
logging.getLogger('discord.http').setLevel(logging.INFO)
handler = logging.handlers.RotatingFileHandler(
	filename='rpgbot.log',
	encoding='utf-8',
	maxBytes=32 * 1024 * 1024,  # 32 MiB
	backupCount=5,
)
dt_fmt = '%d-%m-%Y %H:%M:%S'
formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Discord big doo doo butt >:(
discord.utils.setup_logging(handler=handler, formatter=formatter, level=logging.INFO, root=True)

# Define COG LIST for later
cog_list = sorted([])

# Start everything up!
async def run():
	try:
		logging.info("Booting up RPG Bot!")
		await client.start(keys["token"])
	except KeyboardInterrupt:
		await client.logout()
		
@client.event
async def setup_hook():
	# Load cogs
	for cog in cog_list:
		await client.load_extension(f'cogs.{cog[:-3]}')
		
	# All set!
	print('Hello there!')

@client.event
async def on_ready():
	game = discord.Game("Guess the Genre")
	await client.change_presence(activity=game)
	display_game.start()

### LOOPS ###
with open("config.json", 'r') as f:
	conf = json.load(f)

@tasks.loop(hours=conf['interval'])
async def display_game():
	# Load all the files needed
	with open("config.json", 'r') as f:
		conf = json.load(f)
	with open("games.json", 'r') as f:
		games = json.load(f)
	with open("completed.json", 'r') as f:
		completed = json.load(f)

	# Clear history
	with open("history.json", 'w') as f:
		json.dump({}, f, indent=4)

	# Pick a random game
	selected = random.choice(list(games.keys()))
	while selected in completed:
		selected = random.choice(list(games.keys()))

	# Prevent duplicates
	completed.append(selected)
	with open("completed.json", 'w') as f:
		json.dump(completed, f, indent=4)

	# Embed
	embed = discord.Embed(
		title=selected,
		description=f"""
**Released**: {games[selected]["release_date"]}
**Produced by**: {games[selected]["producer"]}

**__What Genre is This Game?__**
RPG - 0 votes
Roguelike - 0 votes
Not RPG - 0 votes
		""",
		color=discord.Colour.brand_green()
	)

	# Init some stuff
	channel = client.get_channel(conf['channel'])
	view = GameView()

	# Add buttons
	view.add_item(GameButton(discord.ButtonStyle.green, "RPG"))
	view.add_item(GameButton(discord.ButtonStyle.blurple, "Roguelike"))
	view.add_item(GameButton(discord.ButtonStyle.red, "Not RPG"))

	# Send
	output = await channel.send(embed=embed, view=view)
	view.response = output

class GameView(discord.ui.View):
	def __init__(self):
		with open("config.json", 'r') as f:
			conf = json.load(f)

		super().__init__(timeout=float(conf['interval']*60*60))
		self.response = None

	async def on_timeout(self) -> None:
		for item in self.children:
			item.disabled = True
		await self.response.edit(view=self)

class GameButton(discord.ui.Button):
	def __init__(self, style: discord.ButtonStyle, label: str, emoji: str = None):
		super().__init__(style=style, label=label, emoji=emoji)

	def edit_answer(self, desc: str, label: str, amount: int) -> str:
		lines = desc.split("\n")

		if label == "RPG":
			i = 4
		elif label == "Roguelike":
			i = 5
		elif label == "Not RPG":
			i = 6
		else:
			i = 2

		curr = lines[i].split(" ")[-2]
		lines[i] = lines[i].replace(curr, str(int(curr) + amount))

		return "\n".join(lines)

	async def callback(self, interaction: discord.Interaction):
		# Get embed description
		desc = interaction.message.embeds[0].description

		# Get history
		with open("history.json", 'r') as f:
			history = json.load(f)

		# Adjust the vote amount
		desc = self.edit_answer(desc, self.label, 1)

		# Check if the user answered already; if so, subtract the old count
		if history.get(str(interaction.user.id), None):
			desc = self.edit_answer(desc, history[str(interaction.user.id)], -1)

		# Set the user's history
		history[str(interaction.user.id)] = self.label
		with open("history.json", 'w') as f:
			json.dump(history, f, indent=4)

		# Edit the embed with new description
		embed = interaction.message.embeds[0]
		embed.description = desc
		await interaction.message.edit(embed=embed)

		await interaction.response.send_message(f"You voted {self.label}!", ephemeral=True)


### CHECKS ###

def is_catter():
	"""Is catter1"""
	
	def catter(interaction: discord.Interaction):
		if interaction.user.id == 260929689126699008:
			return True
		else:
			return app_commands.MissingPermissions("Only catter is allowed to use this command!")
	return app_commands.check(catter)

@client.command(name="sync")
@is_catter()
async def sync(ctx: commands.context.Context):
	synced = await client.tree.sync()
	await ctx.send(f"Synced {len(synced)} commands")

### COMMANDS ###
## COGS ##

cog_group = app_commands.Group(name='cog', description='[ADMIN] Uses the cog management menu', default_permissions=discord.permissions.Permissions.all())

@cog_group.command(name="load", description="[ADMIN] Loads a cog")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def load(interaction: discord.Interaction, cog: str):
	await interaction.response.defer(thinking=True, ephemeral=True)
	try:
		await client.load_extension(cog)
	except Exception as error:
		await interaction.followup.send("Issue loading cog!", ephemeral=True)
		raise error
	else:
		await interaction.followup.send("Cog loaded successfully", ephemeral=True)

@cog_group.command(name="unload", description="[ADMIN] Unloads a cog")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def unload(interaction: discord.Interaction, cog: str):
	await interaction.response.defer(thinking=True, ephemeral=True)
	try:
		await client.unload_extension(cog)
	except Exception as error:
		await interaction.followup.send("Issue unloading cog!", ephemeral=True)
		raise error
	else:
		await interaction.followup.send("Cog unloaded successfully", ephemeral=True)

@cog_group.command(name="reload", description="[ADMIN] Reloads a cog")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def _reload(interaction: discord.Interaction, cog: str):
	await interaction.response.defer(thinking=True, ephemeral=True)
	try:
		await client.unload_extension(cog)
		await client.load_extension(cog)
	except Exception as error:
		await interaction.followup.send("Issue reloading cog!", ephemeral=True)
		raise error
	else:
		await interaction.followup.send("Cog reloaded successfully", ephemeral=True)


@load.autocomplete('cog')
@unload.autocomplete('cog')
@_reload.autocomplete('cog')
async def autocomplete_callback(interaction: discord.Interaction, current: str):
	coglist = [
		app_commands.Choice(name=cog, value=f"cogs.{cog}")
		for cog in cog_list
		if current.lower() in cog.lower()
	]

	return coglist

## MAIN ##

@app_commands.command(name="config", description="[ADMIN] Configure the bot")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
	interval="Time (hours) between each question",
	channel="The channel to play the game in"
)
async def config(interaction: discord.Interaction, interval: int = None, channel: discord.TextChannel = None):
	""" /config <interval> <channel>"""

	with open("config.json", 'r') as f:
		conf = json.load(f)

	if interval:
		conf['interval'] = interval
	if channel:
		conf['channel'] = channel.id

	with open("config.json", 'w') as f:
		json.dump(conf, f, indent=4)

	display_game.change_interval(hours=conf['interval'])

	embed = discord.Embed(
		title="Config Menu",
		description=f"""
To change the configuration, run this same `/config` command, but with the available options. Currently:

Interval: {conf['interval']} hours
Channel: <#{conf['channel']}>
		""",
		color=discord.Colour.dark_green()
	)

	await interaction.response.send_message(embed=embed, ephemeral=True)

client.tree.add_command(cog_group)
client.tree.add_command(config)

@client.event
async def on_command_error(ctx, error):
	raise error

@client.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
	await interaction.followup.send("An error has occurred!", ephemeral=True)
	raise error

try:
	loop = asyncio.new_event_loop()
	loop.run_until_complete(run())
except KeyboardInterrupt:
	logging.info("RPGBot shutting down...")