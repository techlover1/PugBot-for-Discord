# Pickup Game Bot for use with discord
# Modified by: Alex Laswell for use with Fortress Forever
# Based on: 
#	PugBot-for-Discord by techlover1 https://github.com/techlover1/PugBot-for-Discord

# Imports
from datetime import timedelta
from random import shuffle
from random import choice
import asyncio
import config
import discord
import requests
import time
import valve.rcon

# All of these are set in the config file
adminRoleID = config.adminRoleID
adminRoleMention = config.adminRoleMention
blueteamChannelID = config.blueteamChannelID
cmdprefix = config.cmdprefix
discordServerID = config.discordServerID
maps = config.maps
mapprefix = config.mapprefix
playerRoleID = config.playerRoleID
poolRoleID = config.poolRoleID
quotes = config.quotes
redteamChannelID = config.redteamChannelID
requestChannelID = config.requestChannelID
rconPW = config.rconPW
serverID = config.serverID
serverPW = config.serverPW
server_address  = config.server_address
singleChannelID = config.singleChannelID
sizeOfTeams = config.sizeOfTeams
sizeOfGame = config.sizeOfGame
sizeOfMapPool = config.sizeOfMapPool
token = config.token 

# Begin by creating the client and server object
client = discord.Client()
server = client.get_server(id=discordServerID)

# Globals 
chosenMap = {}
lastMap = {}
mapPicks = {}
lastRedTeam = []
lastBlueTeam = []
lasttime = time.time()
players = []
starter = []
starttime = time.time()
pickupRunning = False
randomteams = False	
selectionMode = False
		
# Setup an RCON connection 
rcon = valve.rcon.RCON(server_address, rconPW)
rcon.connect()
rcon.authenticate()

# get the old pickup information, if it exists
try: 
	with open('lastgameinfo') as infile:
		lastRedTeam = infile.readline().split(",")
		lastBlueTeam = infile.readline().split(",")
		selector = infile.readline()
		mappa = infile.readline()
		lastMap.update({selector:mappa})
		lasttime = float(infile.readline())
except IOError as error:
	lastRedTeam = []
	lastBlueTeam = []
	lastMap = {}
	lasttime = time.time()
	
# Send a rich embeded messages instead of a plain ones

## channel ##
async def send_emb_message_to_channel(colour, embstr, message):
	emb = (discord.Embed(description=embstr, colour=colour))
	emb.set_author(name=client.user.name, icon_url=client.user.avatar_url)
	await client.send_message(message.channel, embed=emb )
	
## user ##	
async def send_emb_message_to_user(colour, embstr, message):
	emb = (discord.Embed(description=embstr, colour=colour))
	emb.set_author(name=client.user.name, icon_url=client.user.avatar_url)
	await client.send_message(message.author, embed=emb )
	
# Cycle through a user's roles to determine if they have admin access
# returns True if they do have access
async def user_has_access(author):
	for r in author.roles:
		if (adminRoleID == r.id): return True
	return False

# Check to make sure all added players are still present
# returns: 	True is someone is missing
# 			False if all members confirm ready
async def someone_is_afk(players, maps, message):
	# message the channel so the users know what is going on
	await send_emb_message_to_channel(0x00ff00, "The pickup is full!! All players must verify they are still here. This will take no more than 10 minutes, but should just be a few. Lookout for my PM and reply ASAP!" , message)
	await client.change_presence(game=discord.Game(name='Check for AFK Players'))
	# for every player in the queue
	for p in players:
		# need to verify they are all still here before starting things
		emb = (discord.Embed(description="AFK CHECK - The pickup is about to begin. You must reply to this message within the next 2 minutes or you will be removed from the pickup due to inactivity.", colour=0xff0000))
		emb.set_author(name=client.user.name, icon_url=client.user.avatar_url)
		await client.send_message(p, embed=emb )
		# wait two minutes (120s) for a reply
		inputobj = await client.wait_for_message(timeout=120, author=p)
		# wait_for_message returns 'None' if asyncio.TimeoutError thrown
		if(inputobj == None): 
			removed = True
			players.remove(p)		# remove from players list
			mapPicks.pop(p, None)		# remove this players nomination if they had one
			await send_emb_message_to_channel(0xff0000, p.mention + " has been removed from the pickup due to inactivity." , message)
			return True
		await send_emb_message_to_channel(0x00ff00, p.mention + " has checked in." , message)
	return False

# Check to see if the map nominated is an alias
async def mapname_is_alias(msg, mpname):
	if(len(mpname) < 4): 
		await send_emb_message_to_channel(0xff0000, msg.author.mention + " that alias is not long enough. You must use at least 4-letter words for the mapname", msg)
		return "TOOSHORT"
	for m in maps:
		mstr = str(m)
		# trim off the 'FF_' if it exists
		if(mstr.startswith(mapprefix)): 
			mstr = mstr[3:]
		# now check if the mapname matches
		if(mstr.startswith(mpname)): 
			return m
	return "INVALID"
	
async def remove_from_pool(msg, redTeam, blueTeam, poolRoleID):
	await asyncio.sleep(300)
	role = discord.utils.get(msg.server.roles, id=poolRoleID)
	for p in redTeam:
		await client.remove_roles(p, role)
	for p in blueTeam:
		await client.remove_roles(p, role)
		
		
# Every time we receive a message
@client.event
async def on_message(msg):
	global chosenMap
	global lastBlueTeam
	global lastMap
	global lastRedTeam
	global lasttime
	global mapPicks
	global pickupRunning
	global players
	global sizeOfGame
	global sizeOfTeams
	global selectionMode
	global starter
	global starttime
	global randomteams
	
	# the bot handles authorizing access to the pickup channel
	if msg.channel.id == requestChannelID: 
		if(msg.content.startswith(cmdprefix + "pug")):
			role = discord.utils.get(msg.server.roles, id=playerRoleID)
			while True:
				try:
					await client.add_roles(msg.author, role)
					await send_emb_message_to_user(0x00ff00, "Successfully added role {0}".format(role.name), msg)					
				except discord.Forbidden:
					continue
				break
				
	if(msg.channel.id != singleChannelID): return	# only listen the the specified channel
	
	if msg.author == client.user: return			# talking to yourself isn't cool...even for bots
	
	# Add - Adds the msg.author to the current pickup
	if(msg.content.startswith(cmdprefix + "add")):
		# there must be an active pickup
		if(pickupRunning):
			# one can only add if:
			# 	they are not already added
			# 	we are not already selecting teams
			if(msg.author in players):
				await send_emb_message_to_channel(0xff0000, msg.author.mention + " you have already added to this pickup", msg)
			elif(selectionMode):
				await send_emb_message_to_channel(0xff0000, msg.author.mention + " you cannot add once the pickup has begun", msg)
			elif(len(players) == sizeOfGame):
				await send_emb_message_to_channel(0xff0000, msg.author.mention + " sorry, the game is currently full\nYou will have to wait until the next one starts", msg)
			else:	# all clear to add them				
				# add to pool for easier notification
				role = discord.utils.get(msg.server.roles, id=poolRoleID)
				await client.add_roles(msg.author, role)
				players.append(msg.author)
				await send_emb_message_to_channel(0x00ff00, msg.author.mention + " you have been added to the pickup.\nThere are currently " + str(len(players)) + "/" + str(sizeOfGame) + " Players in the pickup", msg)
				await client.change_presence(game=discord.Game(name='Pickup (' + str(len(players)) + '/' + str(sizeOfGame) + ') ' + cmdprefix + 'add'))
			
			# each time someone adds, we need to check to see if the pickup is full
			if(len(players) == sizeOfGame):				
				# confirm everyone is still here if it has been over an hour
				elapsedtime = time.time() - starttime
				td = timedelta(seconds=elapsedtime)
				if(td.total_seconds() > 3600):
					if(await someone_is_afk(players, maps, msg)): return			
								
				# do we have the right amount of map nominations
				if(len(mapPicks) < sizeOfMapPool):
					# need to build the list of maps
					mapStr = ""
					for k in mapPicks:
						mapStr = mapStr + str(mapPicks[k]) + " (" + k.mention + ")\n"
					await send_emb_message_to_channel(0xff0000, "Players must nominate more maps before we can proceed\nCurrently Nominated Maps (" + str(len(mapPicks)) + "/" + str(sizeOfMapPool) + ")\n" + mapStr, msg)
				while(len(mapPicks) < sizeOfMapPool):
					async def needMapPicks(msg):						
						# check function for advance filtering
						async def check(msg):
							return msg.content.startswith(cmdprefix + 'nominate')
						
						# wait until someone nominates another map
						await client.wait_for_message(check=check)
					await client.change_presence(game=discord.Game(name='ON HOLD ' + cmdprefix + 'nominate maps'))
					await needMapPicks(msg)

				inputobj = 0			# used to manipulate the objects from messages
				selectionMode = True	# keep people from changing the queue once the game has begun
				shuffle(players) 		# shuffle the player pool
				caps = []
				redTeam = []
				blueTeam = []
												
				# Map Selection
				await client.change_presence(game=discord.Game(name='Map Selection'))
				selector, mappa = choice(list(mapPicks.items()))
				lastMap.update({selector:mappa})
				await send_emb_message_to_channel(0x00ff00, "The map has been selected!\n" + str(mappa) + " (" + selector.mention + ")", msg)
				chosenMap.update({selector:mappa})
				
				# captains should be chosen by an admin
				emb = (discord.Embed(description="The pickup is full, the map has been selected, and all members are present.\n\n" + starter[0].mention + " please select one of the options below", colour=0x00ff00))
				emb.set_author(name=client.user.name, icon_url=client.user.avatar_url)
				emb.add_field(name=cmdprefix + 'captains @Player1 @Player2', value='to manually select the captains', inline=False)
				emb.add_field(name=cmdprefix + 'shuffle', value='to randomize the captains', inline=False)
				emb.add_field(name=cmdprefix + 'random', value='to randomize the teams', inline=False)
				await client.send_message(msg.channel, embed=emb )
				await client.change_presence(game=discord.Game(name='Selecting Captains'))

				# wait until the game starter makes a decision				
				async def pickCaptains(msg, caps, players):
					inputobj = await client.wait_for_message(author=msg.server.get_member(starter[0].id))
					# switch on choice
					if(inputobj.content.startswith(cmdprefix + "captains")):
						# catch any errors if they do not mention two players
						try:
							# check for duplicate user
							if(inputobj.mentions[0] == inputobj.mentions[1]):
								await client.send_message(msg.channel, embed=emb )
								return False
							else:
								caps.append(inputobj.mentions[0])
								caps.append(inputobj.mentions[1])
								return False
						except(IndexError):
							await client.send_message(msg.channel, embed=emb )
							return False
					elif(inputobj.content.startswith(cmdprefix + "shuffle")):
						caps.append(players[0])
						caps.append(players[1])
						return False
					elif(inputobj.content.startswith(cmdprefix + "random")):
						caps.append(players[0])
						caps.append(players[1])
						return True
					else:
						await client.send_message(msg.channel, embed=emb )
				while(len(caps) < 2):
					randomteams = await pickCaptains(msg, caps, players)
				
				# set up the initial teams
				shuffle(caps)	# shuffle the captains so the first guy doesn't always pick first
				if(randomteams):
					for i in range(0, sizeOfTeams):
						redTeam.append(players[i])
						blueTeam.append(players[i+sizeOfTeams])
				else:
					redTeam = [caps[0]]
					blueTeam = [caps[1]]
					players.remove(caps[0])
					players.remove(caps[1])
				
				# Begin the pickup
				await send_emb_message_to_channel(0x00ff00, "The Pickup is Beginning!\n" + caps[0].mention + " vs " + caps[1].mention, msg)
								
				# Switch off picking until the teams are all full
				await client.change_presence(game=discord.Game(name='Team Selection'))
				while(len(redTeam) < sizeOfTeams and len(blueTeam) < sizeOfTeams):
					# RED TEAM PICKS
					async def redTeamPicks(msg):
						plyrStr = ""
						for p in players:
							plyrStr += p.mention + "\n"
						await send_emb_message_to_channel(0x00ff00, caps[0].mention + " type @player to pick. Available players are:\n\n" + plyrStr, msg)
					
						# check for a pick and catch it if they don't mention an available player
						while True:
							try:
								inputobj = await client.wait_for_message(author=msg.server.get_member(caps[0].id))
								picked = inputobj.mentions[0]
							except(IndexError):
								continue
							break

						# If the player is in players and they are not already picked, add to the team
						if(picked in players):
							if(picked not in redTeam and picked not in blueTeam):
								redTeam.append(picked)
								players.remove(picked)
								await send_emb_message_to_channel(0x00ff00, picked.mention + " has been added to the Red Team", msg)
							else:
								await send_emb_message_to_channel(0xff0000, picked.mention + " is already on a team", msg)
								await redTeamPicks(msg)
						else:
							await send_emb_message_to_channel(0xff0000, picked.mention + " is not in this pickup", msg)
							await redTeamPicks(msg)
				
						
					# BLUE TEAM PICKS
					async def blueTeamPicks(msg):
						plyrStr = ""
						for p in players:
							plyrStr += p.mention + "\n"
						await send_emb_message_to_channel(0x00ff00, caps[1].mention + " type @player to pick. Available players are:\n\n" + plyrStr, msg)
					
						# check for a pick and catch it if they don't mention an available player
						while True:
							try:
								inputobj = await client.wait_for_message(author=msg.server.get_member(caps[1].id))
								picked = inputobj.mentions[0]
							except(IndexError):
								continue
							break

						# If the player is in players and they are not already picked, add to the team
						if(picked in players):
							if(picked not in redTeam and picked not in blueTeam):
								blueTeam.append(picked)
								players.remove(picked)
								await send_emb_message_to_channel(0x00ff00, picked.mention + " has been added to the Blue Team", msg)
							else:
								await send_emb_message_to_channel(0xff0000, picked.mention + " is already on a team", msg)
								await blueTeamPicks(msg)
						else:
							await send_emb_message_to_channel(0xff0000, picked.mention + " is not in this pickup", msg)
							await blueTeamPicks(msg)
					await redTeamPicks(msg)
					await blueTeamPicks(msg)
			
				# send the server information to all of the players in a direct message
				# while looping, set up a way to mention all members
				redTeamMention = []
				blueTeamMention = []				
				emb = (discord.Embed(title="connect " + serverID + " " + serverPW, colour=0x00ff00))
				emb.set_author(name=client.user.name, icon_url=client.user.avatar_url)
				for p in redTeam:
					await client.send_message(p, embed=emb )
					redTeamMention.append(p.mention)	# so we can mention all the members of the red team
				for p in blueTeam:
					await client.send_message(p, embed=emb )
					blueTeamMention.append(p.mention)	# so we can mention all the members of the blue team
				
				# Display the game information
				embstr = "The teams and map have been selected"
				emb = (discord.Embed(title=embstr, colour=0x00ff00))
				emb.set_author(name=client.user.name, icon_url=client.user.avatar_url)
				emb.add_field(name='Red Team', value="\n".join(map(str, redTeamMention)))		# Red Team information
				emb.add_field(name='Blue Team', value="\n".join(map(str, blueTeamMention)))		# Blue Team information				
				emb.add_field(name='Map', value=str(mappa) + " (" + selector.mention + ")")		# Display the map information
				await client.send_message(msg.channel, embed=emb )
				await client.change_presence(game=discord.Game(name='GLHF'))
				
				# change the map in the server to the chosen map
				while True:
					try:
						rcon.execute('changelevel ' + mappa)
					except:
						continue
					break
					
				# move the players to their respective voice channels
				for p in redTeam:
					try:
						await client.move_member(p, client.get_channel(redteamChannelID))
					except(InvalidArgument, HTTPException, Forbidden):
						continue				
				for p in blueTeam:
					try:
						await client.move_member(p, client.get_channel(blueteamChannelID))
					except(InvalidArgument, HTTPException, Forbidden):
						continue
				
				# Save all the information for !last
				lastRedTeam = []
				lastBlueTeam = []
				for p in redTeam:
					lastRedTeam.append(p.name)
				for p in blueTeam:
					lastBlueTeam.append(p.name)
				lasttime = time.time()
				
				# save this data to a file so we can access it later
				with open('lastgameinfo', 'w') as outfile:
					outfile.write(",".join(map(str, lastRedTeam)) + "\n")
					outfile.write(",".join(map(str, lastBlueTeam)) + "\n")
					outfile.write(str(selector.name) + "\n")
					outfile.write(str(mappa) + "\n")
					outfile.write(str(lasttime))
				
				# schedule a background task to remove the players from the pool
				# this is so we can still notify them all for a few minutes
				client.loop.create_task(remove_from_pool(msg, redTeam, blueTeam, poolRoleID))
					
				# Reset so we can play another one
				mapPicks = {}
				captains = []				
				players = []
				starter = []
				redTeam = []
				blueTeam = []
				redTeammention = []
				blueTeammention = []
				selectionMode = False
				pickupRunning = False
				await client.change_presence(game=discord.Game(name='GLHF'))
		else:
			await send_emb_message_to_channel(0xff0000, msg.author.mention + " you cannot use this command, there is no pickup running right now. Use " + adminRoleMention + " to request an admin start one for you", msg)
			
	# Commands - Prints the commands menu
	if(msg.content.startswith(cmdprefix + "commands")):
		emb = (discord.Embed(title="Player Commands:", description="FF Pickup Bot Commands accessible by all users", colour=0x00AE86))
		emb.set_author(name=client.user.name, icon_url=client.user.default_avatar_url)
		emb.add_field(name=cmdprefix + 'add', value='Adds yourself to the current pickup', inline=False)
		emb.add_field(name=cmdprefix + 'commands', value='Prints this command menu', inline=False)
		emb.add_field(name=cmdprefix + 'hawking', value='Displays a random quote from the late Dr. S. W. Hawking', inline=False)
		emb.add_field(name=cmdprefix + 'journals', value='Displays a link to 55 papers written by Dr. Hawking in a peer-reviewed journal', inline=False)
		emb.add_field(name=cmdprefix + 'demos', value='Provides you with a link to the currently stored demos', inline=False)
		emb.add_field(name=cmdprefix + 'last', value='Displays information about the last pickup that was played', inline=False)
		emb.add_field(name=cmdprefix + 'map', value='Show the chosen map for the current pickup', inline=False)
		emb.add_field(name=cmdprefix + 'maps', value='Show the nominated maps for the current pickup', inline=False)
		emb.add_field(name=cmdprefix + 'maplist', value='Provides you with a list of all the maps that are available for nomination', inline=False)
		emb.add_field(name=cmdprefix + 'nominate', value='Nominate the specified map', inline=False)
		emb.add_field(name=cmdprefix + 'nominated', value='Show the nominated maps for the current pickup', inline=False)
		emb.add_field(name=cmdprefix + 'records', value='Provides you with a link to the All Time Records', inline=False)
		emb.add_field(name=cmdprefix + 'remove', value='Removes yourself from the pickup', inline=False)		
		emb.add_field(name=cmdprefix + 'sendinfo', value='Sends you the server IP and password', inline=False)
		emb.add_field(name=cmdprefix + 'teams', value='Displays current pickup info', inline=False)
		await client.send_message(msg.author, embed=emb)
		if (await user_has_access(msg.author)):
			emb = (discord.Embed(title="Admin Commands:", description="These commands are accessible only by the game admins", colour=0x00AE86))
			emb.set_author(name=client.user.name, icon_url=client.user.default_avatar_url)
			emb.add_field(name=cmdprefix + 'end', value='End the current pickup (even if you did not start it)', inline=False)
			emb.add_field(name=cmdprefix + 'pickup', value='Start a new pickup game', inline=False)
			emb.add_field(name=cmdprefix + 'players <numberOfPlayers>', value='Change the number of players and the size of the teams', inline=False)
			emb.add_field(name=cmdprefix + 'remove @player', value='Removes the player you specified from the pickup', inline=False)
			emb.add_field(name=cmdprefix + 'transfer @admin', value='Give your pickup to another admin (Game Starter Only)', inline=False)
			await client.send_message(msg.author, embed=emb)
			
	# Demos - Provides the msg.author with a link to the currently stored demos via direct message
	if(msg.content.startswith(cmdprefix + "demos")): await send_emb_message_to_user(0x00AE86, "SourceTV demos can be found here: http://www.ffpickup.com/?p=demos", msg)
		
	# End - End the current pickup
	if(msg.content.startswith(cmdprefix + "end")):
		# there must be an active pickup
		if(pickupRunning):
			# admin command
			if (await user_has_access(msg.author)):
				mapPicks.clear()
				del players[:]
				del starter[:]
				selectionMode = False
				pickupRunning = False
				await send_emb_message_to_channel(0x00ff00, "The pickup has been ended by an admin", msg)
				await client.change_presence(game=discord.Game(name=''))
			else:
				await send_emb_message_to_channel(0xff0000, msg.author.mention + " you do not have access to this command", msg)
		else:
			await send_emb_message_to_channel(0xff0000, msg.author.mention + " you cannot use this command, there is no pickup running right now. Use " + adminRoleMention + " to request an admin start one for you", msg)
	
	# Hawking - Displays a random quote from The Great Dr. Hawking
	if(msg.content.startswith(cmdprefix + "hawking")):
		quote, source = choice(list(quotes.items()))
		emb = (discord.Embed(description=quote, colour=0x5e7750))
		emb.set_author(name="Dr. Stephen William Hawking, 1942-2018", icon_url=client.user.avatar_url)
		emb.add_field(name='Source:', value=source, inline=False)
		await client.send_message(msg.channel, embed=emb )
		
	# Journals - 	Displays a link to 55 papers in Physical Review D and Physical Review Letters
	#				Gathered together and made public by the American Physical Society 
	if(msg.content.startswith(cmdprefix +  "journals")):		
		emb = (discord.Embed(description='''To mark the passing of Stephen Hawking, the American Physical Society have gathered together and made free to read his 55 papers in the peer-reviewed, scientific journals Physical Review D and Physical Review Letters.''', colour=0x5e7750))
		emb.set_author(name="Dr. Stephen William Hawking, 1942-2018", icon_url=client.user.avatar_url)
		emb.add_field(name='Link:', value='https://journals.aps.org/collections/stephen-hawking', inline=False)
		await client.send_message(msg.channel, embed=emb)
		
	# Last - Displays information about the last pickup that was played
	if(msg.content.startswith(cmdprefix + "last")):
		# we have to send these as multiple embed messages
		# if we try to send more than 2000 characters discord raises a 400 request error
		
		# set up the timedelta
		elapsedtime = time.time() - lasttime
		td = timedelta(seconds=elapsedtime)
		td = td - timedelta(microseconds=td.microseconds)
		# get the last map and the player who nominated it
		lmstr = ""
		for k in lastMap: lmstr = str(lastMap[k]) + " (" + str(k) + ")\n"
		emb = (discord.Embed(title="Last Pickup was " + str(td) + " ago on " + lmstr, colour=0x00ff00))
		emb.set_author(name=client.user.name, icon_url=client.user.avatar_url)
		await client.send_message(msg.channel, embed=emb )
		emb1 = (discord.Embed(title="Red Team:\n" + "\n".join(map(str, lastRedTeam)), colour=0xff0000))
		emb1.set_author(name=client.user.name, icon_url=client.user.avatar_url)
		await client.send_message(msg.channel, embed=emb1 )
		emb2 = (discord.Embed(title="Blue Team:\n" + "\n".join(map(str, lastBlueTeam)), colour=0x0000ff))
		emb2.set_author(name=client.user.name, icon_url=client.user.avatar_url)
		await client.send_message(msg.channel, embed=emb2 )
				
	# Map (but not maps or maplist) - Show the chosen map for the current pickup
	if (msg.content.startswith(cmdprefix + "map") and not msg.content.startswith(cmdprefix + "maps") and not msg.content.startswith(cmdprefix + "maplist")):
		# there must be an active pickup
		if(pickupRunning):
			# only allow if pickup selection has already begun
			if(selectionMode):
				for k in chosenMap:
					mapStr = str(chosenMap[k]) + " (" + k.mention + ")\n"
				await send_emb_message_to_channel(0x00ff00, "The map for this pickup is " + mapStr, msg)				
			else:
				await send_emb_message_to_channel(0xff0000, msg.author.mention + " you cannot see the map until the pickup has begun", msg)
		else:
			await send_emb_message_to_channel(0xff0000, msg.author.mention + " you cannot use this command, there is no pickup running right now. Use " + adminRoleMention + " to request an admin start one for you", msg)
			
	# Maps or Nominated - Show the nominated maps for the current pickup
	if (msg.content.startswith(cmdprefix + "maps") or msg.content.startswith(cmdprefix + "nominated")):
		# there must be an active pickup
		if(pickupRunning):
			# need to build the list of maps
			mapStr = ""
			for k in mapPicks:
				mapStr = mapStr + str(mapPicks[k]) + " (" + k.mention + ")\n"			
			await send_emb_message_to_channel(0x00ff00, "Current Maps (" + str(len(mapPicks)) + "/" + str(sizeOfMapPool) + ")\n" + mapStr, msg)
		else:
			await send_emb_message_to_channel(0xff0000, msg.author.mention + " you cannot use this command, there is no pickup running right now. Use " + adminRoleMention + " to request an admin start one for you", msg)
			
	# Maplist - Provides the msg.author with a list of all the maps that are available for nomination via direct message
	if (msg.content.startswith(cmdprefix + "maplist")): await send_emb_message_to_user(0x00ff00, "Currently, you may nominate any of the following maps:\n" + "\n".join(map(str, maps)), msg)
			
	# Nominate (but not nominated) - Nominate the specified map
	if(msg.content.startswith(cmdprefix + "nominate") and not msg.content.startswith(cmdprefix + "nominated")):
		# there must be an active pickup
		if(pickupRunning):
			# only allow if pickup has not already begun
			if(selectionMode):
				await send_emb_message_to_channel(0xff0000, msg.author.mention + " you cannot nominate maps once the pickup has begun", msg)
			else:
				# must also be added to the current pickup
				if(msg.author in players):
					message = msg.content.split()
					# make sure the user provided a map
					if(len(message) > 1):
						# check to see if the provided map is an alias
						atom = await mapname_is_alias(msg, message[1])
						if(atom == "TOOSHORT"): return
						elif(atom == "INVALID"): atom = message[1]
						# only allow maps that exist on server and only put in list once
						if(atom in maps and atom not in mapPicks):
							# only allow a certain number of maps
							if(len(mapPicks) < sizeOfMapPool or msg.author in mapPicks):
								# users may only nominate one map
								mapPicks.update({msg.author:atom})
								await send_emb_message_to_channel(0x00ff00, msg.author.mention + " has nominated " + atom, msg)
							else:
								# need to build the list of maps
								mapStr = ""
								for k in mapPicks:
									mapStr = mapStr + str(mapPicks[k]) + " (" + k.mention + ")\n"
								emb = (discord.Embed(description=msg.author.mention + " there is already more than " + str(sizeOfMapPool) + " maps nominated", colour=0xff0000))
								emb.set_author(name=client.user.name, icon_url=client.user.avatar_url)
								emb.add_field(name='Current Maps', value=mapStr, inline=False)
								await client.send_message(msg.channel, embed=emb )							
						else:
							await send_emb_message_to_channel(0xff0000, msg.author.mention + " that map is not in my !maplist or has already been nominated. Please make another selection", msg)
							await send_emb_message_to_user(0x00ff00, "Currently, you may nominate any of the following maps:\n" + "\n".join(map(str, maps)), msg)
					else:
						await send_emb_message_to_user(0xff0000, msg.author.mention + " you must provide a mapname. " + cmdprefix + "nominate <mapname>", msg)
				else:
					await send_emb_message_to_channel(0xff0000, msg.author.mention + " you cannot use this command, you must be added to the pickup to nominate maps", msg)
		else:
			await send_emb_message_to_channel(0xff0000, msg.author.mention + " you cannot use this command, there is no pickup running right now. Use " + adminRoleMention + " to request an admin start one for you", msg)
			
	# Pickup - Start a new pickup game
	if(msg.content.startswith(cmdprefix + "pickup")):
		# admin command
		if (await user_has_access(msg.author)):
			# only start one if there is not already one running	
			if(pickupRunning):
				await send_emb_message_to_channel(0xff0000, "There is already a pickup running. " + cmdprefix + "teams to see the game details", msg)
			else:
				pickupRunning = True
				starter.append(msg.author)
				await send_emb_message_to_channel(0x00ff00, "A pickup has been started. " + cmdprefix + "add to join up.", msg)
				await client.change_presence(game=discord.Game(name='Pickup (' + str(len(players)) + '/' + str(sizeOfGame) + ') ' + cmdprefix + 'add'))
				starttime = time.time()
		else:
			await send_emb_message_to_channel(0xff0000, msg.author.mention + " you do not have access to this command", msg)
			
	# Players - Change the number of players and the size of the teams
	if(msg.content.startswith(cmdprefix + "players")):
		# there must be an active pickup
		if(pickupRunning):
			# admin command
			if (await user_has_access(msg.author)):
				if(selectionMode):
					await send_emb_message_to_channel(0xff0000, msg.author.mention + " you cannot change the sizes once the pickup has begun", msg)
				else:
					message = msg.content.split()
					if(len(message) == 1):
						await send_emb_message_to_user(0xff0000, "You must provide a new size " + cmdprefix + "setplayers <numberOfPlayers>", msg)
					else:
						# make sure the msg.author is giving an integer value
						while True:
							try:
								sz = int(message[1])
								if(sz == 0):
									# zero players? Just end it then
									await send_emb_message_to_channel(0xff0000, msg.author.mention + " you cannot change to zero players, please use " + cmdprefix + "end instead", msg)
								elif((sz % 2) == 0):
									# even number
									if(sz < len(players)):
										# do not lower sizes if more players have added already
										await send_emb_message_to_channel(0xff0000, msg.author.mention + " the player pool is too big to change to that value", msg)
									else:
										sizeOfTeams = int(sz/2)
										sizeOfGame = int(sz)
										await send_emb_message_to_channel(0x00ff00, msg.author.mention + " the size of the game has been changed to " + str(sz), msg)
								else:
									# odd number
									await send_emb_message_to_channel(0xff0000, msg.author.mention + " the size of the teams must be even", msg)
							except(ValueError):
								continue
							break
			else:
				await send_emb_message_to_channel(0xff0000, msg.author.mention + " you do not have access to this command", msg)
		else:
			await send_emb_message_to_channel(0xff0000, msg.author.mention + " you cannot use this command, there is no pickup running right now. Use " + adminRoleMention + " to request an admin start one for you", msg)
			
	# Records - Provides msg.author with a link to the All Time Records
	if(msg.content.startswith(cmdprefix + "records")): await send_emb_message_to_user(0x00ff00, "All-time Records (work in progress): http://parser.ffpickup.com/v2/records/", msg)		
		
	# Remove - Removes msg.author and their map nomination from the pickup
	if (msg.content.startswith(cmdprefix + "remove")):
		# there must be an active pickup
		if(pickupRunning):
			if(selectionMode is False):
				try:
					idleUser = msg.mentions[0]
					# must be an admin to remove someone other than yourself
					if(await user_has_access(msg.author)):
						if(idleUser in players):
							players.remove(idleUser)		# remove from players list
							mapPicks.pop(idleUser, None)	# remove this players nomination if they had one
							await send_emb_message_to_channel(0x00ff00, idleUser.mention + " you have been removed from the pickup by " + msg.author.mention + " (admin)", msg)
						else:
							await send_emb_message_to_channel(0x00ff00, msg.author.mention + " that user is not added to the pickup", msg)
					else:
						await send_emb_message_to_channel(0xff0000, msg.author.mention + " you do not have access to this command", msg)
				except(IndexError):
					# no user mentioned so check if the author is in pickup 
					if(msg.author in players):
						players.remove(msg.author)		# remove from players list
						mapPicks.pop(msg.author, None)	# remove this players nomination if they had one
						await send_emb_message_to_channel(0x00ff00, msg.author.mention + " you have been removed from the pickup", msg)
					else:
						await send_emb_message_to_channel(0x00ff00, msg.author.mention + " no worries, you never even added", msg)
			else:	
				# selectionMode is True
				await send_emb_message_to_channel(0xff0000, msg.author.mention + " you cannot use !remove once the pickup has begun", msg)
		else:
			await send_emb_message_to_channel(0xff0000, msg.author.mention + " you cannot use this command, there is no pickup running right now. Use " + adminRoleMention + " to request an admin start one for you", msg)
	
	# Sendinfo - Sends msg.author the server IP and password via direct message
	if(msg.content.startswith(cmdprefix + "sendinfo")): await send_emb_message_to_user(0x00ff00, "connect " + serverID + " " + serverPW, msg)
		
	# Teams - Displays current pickup information
	if(msg.content.startswith(cmdprefix + "teams")):
		# there must be an active pickup
		if(pickupRunning):
			if(len(players) < 1):
				await send_emb_message_to_channel(0x00ff00, "The pickup is empty right now. " + cmdprefix + "add to join", msg)					
			elif(len(players) > 0):
				plyrStr = ""
				for p in players:
					plyrStr += p.mention + "\n"
				await send_emb_message_to_channel(0x00ff00, "Players:\n" + plyrStr, msg)
		else:
			await send_emb_message_to_channel(0xff0000, msg.author.mention + " you cannot use this command, there is no pickup running right now. Use " + adminRoleMention + " to request an admin start one for you", msg)
			
	# Transfer - Give your pickup to another admin (Game Starter Only)
	if (msg.content.startswith(cmdprefix + "transfer")):
		# there must be an active pickup
		if(pickupRunning):
			# admin command
			if (await user_has_access(msg.author)):
				# make sure this admin owns this pickup
				if(starter[0] == msg.author):
					# check for a pick and catch it if they don't mention an available player				
					while True:
						try:
							newCap = msg.mentions[0]
						except(IndexError):
							await send_emb_message_to_channel(0x00ff00, msg.author.mention + " you must type !transfer @nameOfAdmin to transfer your pickup.", msg)
							newCap = msg.author
						break
					if(newCap == msg.author): return	# break out if they did not specify a user
					if(await user_has_access(newCap)):
						starter = []
						starter.append(newCap)
						await send_emb_message_to_channel(0x00ff00, msg.author.mention + " your pickup has successfully been transfered to " + msg.mentions[0].mention, msg)
					else:
						await send_emb_message_to_channel(0xff0000, msg.author.mention + " you can only transfer your pickup to another admin", msg)
				else:
					await send_emb_message_to_channel(0x00ff00, msg.author.mention + " no worries, this pickup does not belong to you, it belongs to " + starter[0].mention, msg)
			else:
				await send_emb_message_to_channel(0xff0000, msg.author.mention + " you do not have access to this command", msg)
		else:
			await send_emb_message_to_channel(0xff0000, msg.author.mention + " you cannot use this command, there is no pickup running right now. Use " + adminRoleMention + " to request an admin start one for you", msg)			
	
# Run the bot
client.run(token)
		