# Import important stuff
import discord
import config
from random import shuffle

# Create the client object
client = discord.Client()

# Make the empty lists all in one place (because its the right thing to do)
entered = []
captains = []
team1 = []
team2 = []
picking = False

# Set the things from the config file
admins = config.admins
cmdprefix = config.cmdprefix
teamsize = config.teamsize
pugsize = config.pugsize

# When the bot recieves a message


@client.event
async def on_message(msg):

    # Don't reply to self
    if msg.author == client.user:
        return

    # Ping
    if (msg.content.startswith("!ping")):
        await client.send_message(msg.channel, "pong!")

    # About
    if (msg.content.startswith("!about")):
        await client.send_message(msg.channel, "PugBot version (alpha 0.0.0 dev3) Written by NightFury\nhttps://github.com/techlover1/PugBot-for-Discord\nType !help for commands")

    # Help
    if (msg.content.startswith("!help")):
        await client.send_message(msg.channel, "This command is not available in this version")

    # Add
    if (msg.content.startswith("!add")):
        if (picking = True):
            await client.send_message(msg.channel, "You cannot use this command in the picking phase")
        elif (msg.author in entered):
            await client.send_message(msg.channel, "You are already in the queue")
        elif (len(entered) == (pugsize - 1)):
        #elif (len(entered) == 2):
            entered.append(msg.author)

            # start the pug
            picking = True

            shuffle(entered)
            captains = [entered[0], entered[1]]
            team1 = [captains[0]]
            team2 = [captains[1]]
            entered.remove(team1[0])
            entered.remove(team2[0])

            startingMsg = "PUG Starting!\nCaptains are " + captains[0].mention + " and " + captains[1].mention + \
                "\n" + captains[0].mention + " will have first pick"
            await client.send_message(msg.channel, startingMsg)

            # while teams are not full
            while(len(team1) < teamsize and len(team2) < teamsize):

                async def team1func(msg):
                    inputobj = 0
                    await client.send_message(msg.channel,captains[0].mention + " Type @player to pick. Available players are:\n" + ("\n".join(map(str, entered))))

                    while True:
                        try:
                            inputobj = await client.wait_for_message(author=msg.server.get_member(captains[0].id))
                            team1add = inputobj.mentions[0]
                        except(IndexError):
                            continue
                        break

                    if(team1add in entered and team1add not in team1 and team1add not in team2):
                        team1.append(team1add)
                        entered.remove(team1add)
                        await client.send_message(msg.channel, team1add.mention + " Added to your team")

                    elif(team1add in entered and team1add in team1 or team1add in team2):
                        await client.send_message(msg.channel, team1add.mention + " Is already on a team")
                        await team1func(msg)

                    elif(team1add not in entered):
                        await client.send_message(msg.channel, team1add.mention + " Is not in the queue")
                        await team1func(msg)

                    else:
                        await client.send_message(msg.channel, "Unknown error")
                        await team1func(msg)

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

            team1mention = []
            team2mention = []
            for i in team1:
                team1mention.append(i.mention)
            for i in team2:
                team2mention.append(i.mention)

            await client.send_message(msg.channel, "Team 1 is: " + "\n".join(map(str, team1mention)) + "\nTeam2 is: " + "\n".join(map(str, team2mention)) + "\n GLHF!")

            entered = []
            captains = []
            team1 = []
            team2 = []
            team1mention = []
            team2mention = []
            picking = False

        else:
            entered.append(msg.author)
            await client.send_message(msg.channel, msg.author.mention + " Successfuly entered into the queue. " + str(len(entered)) + " Players in queue")

    # Queue
    if (msg.content.startswith("!queue") and len(entered) < 1):
        await client.send_message(msg.channel, "The queue is currently empty")
    if (msg.content.startswith("!queue") and len(entered) > 0):
        await client.send_message(msg.channel, "Players in queue: " + str(len(entered)))

    # Remove
    if (msg.content.startswith("!remove")):
        if(picking = True):
            await client.send_message(msg.channel, "You cannot use this command in the picking phase")
        elif(msg.author in entered):
            entered.remove(msg.author)
            await client.send_message(msg.channel, "Successfuly left the queue. " + str(len(entered)) + " Currently in queue")
        else:
            await client.send_message(msg.channel, "You are not in the queue")

    # Reset
    if (msg.content.startswith("!reset")):
        if (msg.author.id in config.admins):
            del entered[:]
            await client.send_message(msg.channel, "Queue reset")
        else:
            await client.send_message(msg.channel, "You do not have access to this command")


# Print when ready
@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)

# Run the bot
client.run(config.token)
