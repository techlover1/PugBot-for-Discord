# Import important stuff
import discord
import config
from random import shuffle

# Create the client object
client = discord.Client()

# Set the things from the config file
admins = config.admins
cmdprefix = config.cmdprefix
teamsize = config.teamsize
pugsize = config.pugsize

picking = False
entered = []

# When the bot recieves a message
@client.event
async def on_message(msg):
    global picking
    global entered

    # Don't reply to self
    if msg.author == client.user:
        return

    # Ping
    if (msg.content.startswith(cmdprefix + "ping")):
        await client.send_message(msg.channel, "pong!")

    # About
    if (msg.content.startswith(cmdprefix + "about")):
        await client.send_message(msg.channel, "PugBot version (beta 0.1.0) Written by NightFury\nhttps://github.com/techlover1/PugBot-for-Discord\nType !help for commands")

    # Help
    if (msg.content.startswith(cmdprefix + "help")):
        await client.send_message(msg.channel, "```Available Commands:\nabout - Print information about the bot\nadd - Join the queue\n"
                                  + "help - Print this screen\nping - Test bot functionality\nqueue - Print players currently in the queue\nremove - Leave the queue```")

    # Add
    if (msg.content.startswith(cmdprefix + "add")):

        # If in the picking phase, don't allow !add
        if (picking):
            await client.send_message(msg.channel, msg.author.mention + " You cannot use this command in the picking phase")

        # If the user is already in the queue, tell them
        elif (msg.author in entered):
            await client.send_message(msg.channel, msg.author.mention + " You are already in the queue")

        # If the pug is full lets get this party started
        elif (len(entered) == (pugsize - 1)):
            entered.append(msg.author)

            picking = True

            # Set the captains
            shuffle(entered)
            captains = [entered[0], entered[1]]
            team1 = [captains[0]]
            team2 = [captains[1]]
            entered.remove(team1[0])
            entered.remove(team2[0])

            # Send the starting message
            startingMsg = "PUG Starting!\nCaptains are " + captains[0].mention + " and " + captains[1].mention + \
                "\n" + captains[0].mention + " will have first pick"
            await client.send_message(msg.channel, startingMsg)

            # While teams are not full let captains take turns picking players
            while(len(team1) < teamsize and len(team2) < teamsize):

                async def team1func(msg):
                    inputobj = 0
                    await client.send_message(msg.channel, captains[0].mention + " Type @player to pick. Available players are:\n" + ("\n".join(map(str, entered))))

                    # This block of code checks for a pick from captain1 and
                    # catches the exception if they send a message that doesn't contain a mention
                    while True:
                        try:
                            inputobj = await client.wait_for_message(author=msg.server.get_member(captains[0].id))
                            team1add = inputobj.mentions[0]
                        except(IndexError):
                            continue
                        break

                    # If the pick isn't on a team, add to team1
                    if(team1add in entered and team1add not in team1 and team1add not in team2):
                        team1.append(team1add)
                        entered.remove(team1add)
                        await client.send_message(msg.channel, team1add.mention + " Added to your team")

                    # If the pick is already on a team, tell captain1 and let them pick again
                    elif(team1add in entered and team1add in team1 or team1add in team2):
                        await client.send_message(msg.channel, team1add.mention + " Is already on a team")
                        await team1func(msg)

                    # If the pick isn't in the queue, tell captain1 and let them pick again
                    elif(team1add not in entered):
                        await client.send_message(msg.channel, team1add.mention + " Is not in the queue")
                        await team1func(msg)

                    # This probably shouldn't even be here, but whatever
                    else:
                        await client.send_message(msg.channel, "Unknown error")
                        await team1func(msg)

                # Same as above, but for team2
                async def team2func(msg):
                    inputobj = 0
                    await client.send_message(msg.channel, captains[1].mention + " Type @player to pick. Available players are:\n" + ("\n".join(map(str, entered))))

                    while True:
                        try:
                            inputobj = await client.wait_for_message(author=msg.server.get_member(captains[1].id))
                            team2add = inputobj.mentions[0]
                        except(IndexError):
                            continue
                        break

                    if(team2add in entered and team2add not in team1 and team2add not in team2):
                        team2.append(team2add)
                        entered.remove(team2add)
                        await client.send_message(msg.channel, team2add.mention + " Added to your team")

                    elif(team2add in entered and team2add in team1 or team2add in team2):
                        await client.send_message(msg.channel, team2add.mention + " Is already on a team")
                        await team2func(msg)

                    elif(team2add not in entered):
                        await client.send_message(msg.channel, team2add.mention + " Is not in the queue")
                        await team2func(msg)

                    else:
                        await client.send_message(msg.channel, "Unknown error")
                        await team2func(msg)

                await team1func(msg)
                await team2func(msg)

            # Setup a way to mention the teams
            team1mention = []
            team2mention = []
            for i in team1:
                team1mention.append(i.mention)
            for i in team2:
                team2mention.append(i.mention)

            # Send a message containg the teams, GLHF!
            await client.send_message(msg.channel, "Team 1 is: " + "\n".join(map(str, team1mention)) + "\nTeam2 is: " + "\n".join(map(str, team2mention)) + "\n GLHF!")

            # Reset to allow for anotherone
            entered = []
            captains = []
            team1 = []
            team2 = []
            team1mention = []
            team2mention = []
            picking = False

        # Add player to queue if the queue isn't full
        else:
            entered.append(msg.author)
            await client.send_message(msg.channel, msg.author.mention + " You successfuly entered into the queue. " + str(len(entered)) + " Players in queue")

    # Queue
    if (msg.content.startswith(cmdprefix + "queue") and len(entered) < 1):
        await client.send_message(msg.channel, "The queue is currently empty")
    if (msg.content.startswith(cmdprefix + "queue") and len(entered) > 0):
        await client.send_message(msg.channel, "Players in queue:\n" + "\n".join(map(str, entered)))

    # Remove
    if (msg.content.startswith(cmdprefix + "remove")):
        if(picking is True):
            await client.send_message(msg.channel, msg.author.mention + " You cannot use this command in the picking phase")
        elif(msg.author in entered):
            entered.remove(msg.author)
            await client.send_message(msg.channel, msg.author.mention + " You successfuly left the queue. " + str(len(entered)) + " Currently in queue")
        else:
            await client.send_message(msg.channel, msg.author.mention + " You are not in the queue")

    # Reset
    if (msg.content.startswith(cmdprefix + "reset")):
        if (msg.author.id in config.admins):
            del entered[:]
            picking = False
            await client.send_message(msg.channel, "Queue reset")
        else:
            await client.send_message(msg.channel, msg.author.mention + " You do not have access to this command")

    # Easter egg 1
    if ("Kappa" in msg.content):
        await client.send_message(msg.channel, "http://i.imgur.com/cpzYXCI.png")

    # Easter egg 2
    if (msg.content.startswith(cmdprefix + "egg")):
        await client.send_message(msg.channel, "http://i.imgur.com/GZ79poy.jpg")


# Print when ready
@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)

# Run the bot
client.run(config.token)
