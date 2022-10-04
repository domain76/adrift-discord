import discord
from discord.ext import commands
from discord.utils import get
import calendar
import logging
import asyncpg
from asyncpg.pool import create_pool
import datetime
from datetime import date
import time as t
import os
import asyncio
import math
from collections import defaultdict
import os.path
import time
import json
import random
import uuid
from constants import *

discord_log = logging.getLogger('discord')
discord_log.setLevel(logging.INFO)
handler = logging.FileHandler(filename='Adrift.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
discord_log.addHandler(handler)

intents = discord.Intents.all()

client = commands.AutoShardedBot(command_prefix=commands.when_mentioned_or(PREFIX), intents=intents,
                                 owner_ids=OWNER_IDS)
client.strip_after_prefix = False

coin_drop_message = discord.Message
coin_drop_reward = 0

###################################################################
##                        LOGIC FUNCTIONS                        ##
##                                                               ##
## All the logic that works in the background to make the bot    ##
## functions work.                                               ##
##                                                               ##
###################################################################
async def create_db_pool():
    client.pg = await asyncpg.create_pool(database=DATABASE_NAME, user=DATABASE_USERNAME, password=DATABASE_PASSWORD,
                                          host=DATABASE_HOST, port=5432)


async def db_guild_set(guild, column, value):
    setguild = await client.pg.execute(f'UPDATE config SET {column} = $1 WHERE guild_id = $2', value, guild)


async def db_guild_get(guild, column=''):
    if isinstance(guild, int):
        guild = guild
    else:
        guild = guild.id

    if column == '':
        guild_result = await client.pg.fetchrow('SELECT * FROM config WHERE guild_id = $1', guild)
    else:
        guild_result = await client.pg.fetchrow(f'SELECT {column} FROM config WHERE guild_id = $1', guild)
    
    if guild_result is not None:
        return guild_result[0]
    else:
        return None


async def simple_embed(text: str, color=0xFFFFFF):
    embed = discord.Embed(colour=color, description=text)
    return embed


async def has_permissions(member, permission, ctx):
    if member.id in OWNER_IDS:
        return True

    perm_list = member.permissions_in(ctx.message.channel)

    if member.permissions_in(ctx.message.channel):
        var = member.permissions_in(ctx.message.channel)
    
    if permission == "ban_members":
        if perm_list.ban_members:
            return True
    if permission == "manage_messages":
        if perm_list.manage_messages:
            return True
    if permission == "manage_roles":
        if perm_list.manage_roles:
            return True
    if permission == "administrator":
        if perm_list.administrator:
            return True
    if permission == "user":
        return True


async def post_log(guild, logtype, user, target, reason="default reason"):
    try:
        log_channel = client.get_channel(id=await db_guild_get(guild, 'loggingchannel'))
        
        if log_channel:
            embed = discord.Embed
            if logtype == 'SETTING':
                embed = await simple_embed(f'⚙ **SETTING CHANGED**\n\n**User:** {user}\n\n**Setting:** {reason}\n\n'
                                           f'**User ID:** {target.id}')
            if logtype == 'MESSAGE_DELETED':
                embed = await simple_embed(f'🗑️ **MESSAGE DELETED**\n\n**User:** {target}\n\n**A message from user was '
                                           f'deleted:\n\n**Message:** {reason}\n\n**User ID:** {target.id}')
            if logtype == 'LEAVE':
                embed = await simple_embed(f'🔴 **USER LEFT**\n{target} left {guild}\n**User ID:** {target.id}')
            if logtype == 'JOIN':
                embed = await simple_embed(f'🟢 **USER JOINED**\n{target} joined {guild}\n**User ID: {target.id}')
            if logtype == 'ROLE_GIVEN':
                embed = await simple_embed(f'🛡️ **ROLE GIVEN**\n{user} was given the role <@&{target}>')
            embed.timestamp = datetime.datetime.utcnow()
            if target:
                embed.set_thumbnail(url=f"{user.avatar_url}")
            try:
                await log_channel.send(embed=embed)
            except AttributeError:
                return
    except Exception as e:
        print(e)


async def db_member_set(member, column, value):
    member = await convert_member_to_id(member)
    memberupdate = await client.pg.execute(f'UPDATE members SET {column} = $1 WHERE member_id = $2', value, member)


async def db_member_get(member, column=''):
    member = await convert_member_to_id(member)
    if column == '':
        member_result = await client.pg.fetchrow('SELECT * FROM members WHERE member_id = $1', member)
        if member_result is None:
            return_result = member_result
        else:
            return_result = member_result
    else:
        member_result = await client.pg.fetchrow(f'SELECT {column} FROM members WHERE member_id = $1', member)
        if member_result is None:
            print("No data from db_member_get single value from column {0} for member {1}".format(column, member))
            return_result = 0
        else:
            return_result = member_result[0]
    
    return return_result


async def convert_member_to_id(member):
    if isinstance(member, int):
        member = member
    elif isinstance(member, discord.Member):
        member = member.id
    elif isinstance(member, discord.User):
        member = member.id
    elif isinstance(member, discord.ClientUser):
        member = member.id
        print("ClientUser")
    else:
        print("IDK what kind of user that is: func: convert_member_to_id")
        print("Type is ", await type(member))

    return member


async def rolesonjoin(guild, member):
    roles = await db_guild_get(guild.id, 'rolesonjoin')
    print(roles)
    for i in roles:
        roleonjoin = discord.utils.get(guild.roles, id=i)
        await post_log(guild, 'ROLE_GIVEN', member, i, 'was given role')
        await member.add_roles(roleonjoin)


async def remove_msg(message, delay):
    c_name = message.channel.name
    g_name = message.guild.name
    await asyncio.sleep(delay)
    await message.delete()
    print("A message has been automatically pruned in " + c_name + " in server " + g_name)
    return


async def parseID(escapedID):
    escapechars = {64: 160, 60: 160, 62: 160, 35: 160, 38: 160, 33: 160}
    id = escapedID.translate(escapechars).strip()
    return int(id)


async def generate_profile_embed(user, embed, ctx):
    account = "user"
    user = await convert_member_to_id(user)
    member = await client.fetch_user(user)
    member_result = await db_member_get(user)

    if not member:
        try:
            await ctx.reply("Error, could not get user from Discord.")
        except:
            await ctx.message.reply("Error")
        return

    creation_date = datetime.datetime.fromtimestamp(member.created_at.timestamp())
    creation_date = creation_date.replace(microsecond=0)
    today_date = datetime.datetime.utcnow().replace(microsecond=0)
    creation_date_text = f'`{creation_date}`'
    delta = today_date - creation_date

    creation_time = datetime.datetime.fromtimestamp(member.created_at.timestamp())
    creation_time = creation_time.replace()
    creation_timestamp = creation_time.timestamp()
    creation_timestamp_text = f"<t:{math.floor(creation_timestamp)}>"
    creation_year_text = f"<t:{math.floor(creation_timestamp)}:R>"

    if account != "Bot":
        creation_date = creation_timestamp_text
        creation_date_text = f'Account created {creation_year_text}\n{creation_date}'

    embed.add_field(name=str('Username'), value=str(f'{member_result[1]}'), inline=False)
    bio_text = str(member_result[8])

    embed.add_field(name=str('🔖 Bio'), value=str(f'{bio_text}'), inline=False)
    embed.add_field(name=str('💵 Cash'), value=str(f'{member_result[2]}'))
    embed.add_field(name=str('💳 Bank'), value=str(f'{member_result[4]}'))
    embed.add_field(name=str('🎩 Karma'), value=str(f'{member_result[3]}'))
    embed.add_field(name=str('📊 Level'), value=str(f'{member_result[5]}'))
    embed.add_field(name=str('🔮 Experience'), value=str(f'{member_result[6]}'))

    if member_result[7] is None:
        embed.add_field(name=str('🎂 Birthday'), value=str(f'No Birthday'))
    else:
        birthday = member_result[7]
        formatted_bday = birthday.strftime("%b %d")
        embed.add_field(name=str('🎂 Birthday'), value=str(f'{formatted_bday}'))
    
    if account != "Bot":
        embed.add_field(name=str(' :clock1030: Account Creation:'), value=str(f'{creation_date_text}'), inline=False)
    
    if ctx:
        embed.set_footer(text=f"{ctx.guild}", icon_url=f"{ctx.guild.icon_url}")
    
    embed.timestamp = datetime.datetime.utcnow()
    embed.set_thumbnail(url=f"{member.avatar_url}")
    return embed


async def update_user(member):
    if await db_member_get(member) is None:
        member = await convert_member_to_id(member)
        createmember = await client.pg.execute('INSERT INTO members (member_id) VALUES ($1)', member)


async def automated_drops():
    await client.wait_until_ready()
    print('Automated Credit Drop Loop Started!')

    while True:
        randomtime = random.randrange(60, 240)
        print("Random Drop Interval: ", randomtime)
        print("Drop Interval Set", 60 * randomtime * 2)
        print("Final Drop Time: {0} minutes".format((60 * randomtime * 2) / 60))

        await asyncio.sleep(60 * randomtime * 2)
        global coin_drop_message
        global coin_drop_reward

        coin_drop_reward = random.randrange(50, 100)
        embed = discord.Embed(title=str(f'Credit Drop'), description='', colour=discord.Colour(0xFFFFFF))

        embed.add_field(name=str('Reward'), value=str(f'React to claim {CURRENCY_EMOJI}{coin_drop_reward}'),
                        inline=False)
        coin_drop_message = await client.get_channel(random.choice(DROP_LOCATIONS)).send(embed=embed)


async def automated_water_reminder():
    await client.wait_until_ready()
    print('Automated Water Reminder Loop Started!')

    while True:
        await asyncio.sleep(60 * 120)

        reminder = "<a:attention:1026222478613282836><a:attention:1026222478613282836>" \
                   "<a:attention:1026222478613282836> This is your friendly reminder to make sure you drink water! " \
                   "<a:attention:1026222478613282836><a:attention:1026222478613282836><a:attention:1026222478613282836>"
        water_reminder_message = await client.get_channel(random.choice(DROP_LOCATIONS)).send(reminder)

###################################################################
##                      DISCORD BOT COMMANDS                     ##
##                                                               ##
## Executable commands for use inside of the Discord client.     ##
##                                                               ##
###################################################################

######
## Social Commands
######
@client.command()
async def lick(ctx, member: discord.User):
    embed = discord.Embed(title='You\'ve been Licked!', description=f'<@{ctx.author.id}> licked {member.mention}')
    embed.set_image(url=random.choice(LICK_GIFS))

    await ctx.send(embed=embed)


@client.command()
async def fuck(ctx, member: discord.User):
    embed = discord.Embed(title='You\'ve been Fucked!', description=f'<@{ctx.author.id}> fucked {member.mention}')
    embed.set_image(url=random.choice(FUCK_GIFS))

    await ctx.send(embed=embed)


@client.command()
async def kiss(ctx, member: discord.User):
    embed = discord.Embed(title='You\'ve been Kissed!', description=f'<@{ctx.author.id}> kissed {member.mention}')
    embed.set_image(url=random.choice(KISS_GIFS))

    await ctx.send(embed=embed)


@client.command()
async def kick(ctx, member: discord.User):
    embed = discord.Embed(title='You\'ve been Kicked!', description=f'<@{ctx.author.id}> kicked {member.mention}')
    embed.set_image(url=random.choice(KICK_GIFS))

    await ctx.send(embed=embed)


@client.command()
async def hug(ctx, member: discord.User):
    embed = discord.Embed(title='You\'ve been Hugged!', description=f'<@{ctx.author.id}> hugged {member.mention}')
    embed.set_image(url=random.choice(HUG_GIFS))

    await ctx.send(embed=embed)


@client.command()
async def slap(ctx, member: discord.User):
    embed = discord.Embed(title='You\'ve been Slapped!', description=f'<@{ctx.author.id}> slapped {member.mention}')
    embed.set_image(url=random.choice(SLAP_GIFS))

    await ctx.send(embed=embed)


@client.command()
async def spank(ctx, member: discord.User):
    embed = discord.Embed(title='You\'ve been Spanked!', description=f'<@{ctx.author.id}> spanked {member.mention}')
    embed.set_image(url=random.choice(SPANK_GIFS))

    await ctx.send(embed=embed)


@client.command()
async def restrain(ctx, member: discord.User):
    embed = discord.Embed(title='You\'ve been Restrained!',
                          description=f'<@{ctx.author.id}> restrained {member.mention}')
    embed.set_image(url=random.choice(RESTRAIN_GIFS))

    await ctx.send(embed=embed)


@client.command()
async def cuddle(ctx, member: discord.User):
    embed = discord.Embed(title='You\'ve been Cuddled!', description=f'<@{ctx.author.id}> cuddled {member.mention}')
    embed.set_image(url=random.choice(CUDDLE_GIFS))

    await ctx.send(embed=embed)


@client.command()
async def pet(ctx, member: discord.User):
    embed = discord.Embed(title='You\'ve been Pet!', description=f'<@{ctx.author.id}> pet {member.mention}')
    embed.set_image(url=random.choice(PET_GIFS))

    await ctx.send(embed=embed)


@client.command()
async def punch(ctx, member: discord.User):
    embed = discord.Embed(title='You\'ve been Punched!', description=f'<@{ctx.author.id}> punched {member.mention}')
    embed.set_image(url=random.choice(PUNCH_GIFS))

    await ctx.send(embed=embed)


######
## Economy Commands
######
@client.command(brief='Set your server bio.')
async def setbio(ctx):
    saytax = ctx.message.content.split(" ", 1)
    user = ctx.message.author
    aboutMeText = saytax[1]

    await db_member_set(user, "bio", aboutMeText)
    await ctx.message.channel.send(content=f':white_check_mark: Alright! I set your bio to `{aboutMeText}`')


@client.command(brief='Clear out your server bio.')
async def clearbio(ctx):
    user = ctx.message.author
    aboutMeText = "I have the default bio because I''m too lazy to set a proper one."

    await db_member_set(user, "bio", aboutMeText)
    await ctx.message.channel.send(content=f':white_check_mark: Alright! I cleared your bio.')


@client.command(aliases=['dep'], brief='Deposit x credits to your bank.')
async def deposit(ctx, amount: int):
    user = ctx.message.author
    cash = await db_member_get(user, "credits")
    bank = await db_member_get(user, "bank")
    
    if cash == 0:
        await ctx.message.channel.send(content=f":x: You don't have any credits to deposit!")
    elif cash < amount:
        await ctx.message.channel.send(content=f":x: You don't have enough credits to deposit!")
    else:
        cash_remaining = cash - amount
        bank_new = bank + amount
        new_cash = await db_member_set(user, "credits", cash_remaining)
        new_bank = await db_member_set(user, "bank", bank_new)

        await ctx.message.channel.send(
            content=f':white_check_mark: Deposited {amount} credit(s) to your bank. Your new bank balance '
                    f':is {bank_new}')


@client.command(aliases=['with'], breif='Withdraw x credits from your bank.')
async def withdraw(ctx, amount: int):
    user = ctx.message.author
    cash = await db_member_get(user, "credits")
    bank = await db_member_get(user, "bank")
    
    if bank == 0:
        await ctx.message.channel.send(content=f":x: You don't have any credits to withdraw!")
    elif bank < amount:
        await ctx.message.channel.send(content=f":x: You don't have enough credits to withdraw!")
    else:
        bank_remaining = bank - amount
        cash_new = cash + amount
        new_bank = await db_member_set(user, "bank", bank_remaining)
        new_cash = await db_member_set(user, "credits", cash_new)

        await ctx.message.channel.send(content=f':white_check_mark: Withdrew {amount} to your credit balance. Your new '
                                               f'credit balance is {cash_new}')


@client.command(brief='Pay anothher member x credits.')
async def pay(ctx, member: discord.User, amount: int):
    user = ctx.message.author
    member = member
    amount = amount

    my_cash = await db_member_get(user, "credits")
    their_cash = await db_member_get(member, "credits")

    if my_cash == 0:
        await ctx.message.send(content=f":x: You don't have any credits to pay {member}!")
    elif my_cash < amount:
        await ctx.message.send(content=f":x: You don't have enough credits to pay {member}!")
    else:
        my_remaining_cash = my_cash - amount
        their_new_cash = their_cash + amount
        my_rc = await db_member_set(user, "credits", my_remaining_cash)
        their_nc = await db_member_set(member, "credits", their_new_cash)

        await ctx.message.channel.send(content=f':white_check_mark: You paid {member} {amount} to their credit account.')


@client.command(brief='Work and earn coins.')
@commands.cooldown(1, 3600, commands.BucketType.user)
async def work(ctx):
    work_salary = random.randrange(20, 100)
    user_coins = await db_member_get(ctx.author, 'credits')
    total_salary_earned = user_coins + work_salary
    salary_given = await db_member_set(ctx.author, 'credits', total_salary_earned)

    embed = discord.Embed(title='Work Complete!', colour=discord.Colour(0xFFFFFF),
                          description=f'You earned {work_salary}! You now have {total_salary_earned} credits added to '
                                      f'your wallet.')
                                      
    await ctx.send(embed=embed)


@client.command(brief='Take a chance at robbing another user.')
@commands.cooldown(1, 3600, commands.BucketType.user)
async def rob(ctx, member: discord.User):
    potential_loot = await db_member_get(member, 'credits')
    chance_of_rob = random.randrange(0, 1)
    if potential_loot > 0:
        if chance_of_rob == 1:
            random_loot = random.randrange(0, potential_loot)
            robbed_remaining = potential_loot - random_loot
            robbed_updated = await db_member_set(member, 'credits', robbed_remaining)
            my_loot = await db_member_get(ctx.author, 'credits')
            my_loot = my_loot + random_loot
            my_new_loot = await db_member_set(ctx.author, 'credits', my_loot)
            await ctx.send(f'You successfully stole {random_loot} from {member.mention}')
        else:
            random_fine = random.randrange(0, 50)
            fine_assessed = await db_member_get(ctx.author, 'credits')
            total_fine = fine_assessed - random_fine
            fine_set = await db_member_set(ctx.author, 'credits', total_fine)
            await ctx.send(
                f'You are by far the worst pirate we have ever seen! You were fined {random_fine} credits for your '
                f'attempted robbery of {member.mention}!')
    else:
        await ctx.send(f'{member.mention} has no credits in their wallet to steal!')


@client.command(aliases=['bal'], brief='Get credit balance info for a user.')
async def balance(ctx):
    try:
        await ctx.message.reply(delete_after=0.2, content="Getting Balance")
        arg = ctx.message.content.split(" ", 2)
        user = 'user'
        if len(arg) == 1:
            user = ctx.author.id
        if len(arg) > 1:
            user = await parseID(arg[1])

        if user:
            if isinstance(user, int):
                print("User is an int")
            else:
                await ctx.message.reply(delete_after=0.5, content="You need to specify a user.")
                return
        else:
            user = 'user'

        user_name = await client.fetch_user(user)

        member = await db_member_get(user)

        await ctx.send(f'{user_name.name} has {member[2]} credits in their wallet, and {member[4]} in their bank.')
    except Exception as e:
        print(e)


@client.command(brief='Create a dynamic with another user.', hidden=True)
async def dynamic(ctx, member: discord.User):
    pass


@client.command(brief='End your dynamic with a partner.', hidden=True)
async def enddynamic(ctx, member: discord.User):
    pass


######
## Administration Commands
######
@client.command(brief='Sets the mod log channel.', hidden=True)
@commands.has_permissions()
async def setlogging(ctx, channel: discord.TextChannel):
    if await has_permissions(ctx.message.author, "manage_roles", ctx):
        try:
            await channel.send(embed=await simple_embed(f':white_check_mark: This is where I will post logs!'))
            await ctx.send(embed=await simple_embed(f':white_check_mark: Done! I will now post logged events in '
                                                    f'{channel.mention}'))
            await post_log(ctx.guild, 'SETTING', ctx.author, ctx.author, f'Set the logging channel to '
                           f'{channel.mention}')
            await db_guild_set(ctx.guild.id, 'loggingchannel', channel.id)
        except discord.errors.Forbidden:
            await ctx.send(embed=await simple_embed(f':warning: I don\'t have permission to post in {channel.mention}\n'
                                                    f'Make sure I have permissions and try again!'))
    else:
        await ctx.message.reply(delete_after=5, content=NO_PERMS)


@client.command(brief='Sets the starboard channel.', hidden=True)
@commands.has_permissions()
async def setstarboard(ctx, channel: discord.TextChannel):
    if await has_permissions(ctx.message.author, "manage_roles", ctx):
        try:
            await channel.send(embed=await simple_embed(f':white_check_mark: This is where I will post starboards!'))
            await ctx.send(embed=await simple_embed(f':white_check_mark: Done! I will now post starboard events in '
                                                    f'{channel.mention}'))
            await post_log(ctx.guild, 'SETTING', ctx.author, ctx.author, f'Set the starboard channel to '
                                                                         f'{channel.mention}')
            await db_guild_set(ctx.guild.id, 'starboard_id', channel.id)
        except discord.errors.Forbidden:
            await ctx.send(embed=await simple_embed(f':warning: I don\'t have permission to post in {channel.mention}\n'
                                                    f'Make sure I have permissions and try again!'))
    else:
        await ctx.message.reply(delete_after=5, content=NO_PERMS)


@client.command(brief='Sets the auto-prune channels.', hidden=True)
@commands.has_permissions()
async def addPruneChannel(ctx):
    if await has_permissions(ctx.message.author, "administrator", ctx):
        with open('guilds.json') as json_file:
            existingData = json.load(json_file)
        data = existingData

        if str(ctx.guild.id) not in data:
            data[str(ctx.guild.id)] = []

        if ctx.message.channel.id not in data[str(ctx.guild.id)]:
            data[str(ctx.guild.id)].append(ctx.message.channel.id)
        else:
            print("This channel already has pruning enabled. Use the remove command in this channel if you would like "
                  "to remove it.")

        await ctx.send("Added " + ctx.message.channel.name + " to auto-prune list.")

        with open("guilds.json", "w") as write_file:
            json.dump(data, write_file)

        with open('delays.json') as json_file:
            existingData = json.load(json_file)
        data = existingData

        if str(ctx.guild.id) not in data:
            data[str(ctx.guild.id)] = 300

        with open("delays.json", "w") as write_file:
            json.dump(data, write_file)


@client.command(aliases=['aboutme'], brief='Display a users server profile.', description='Displays a users server '
                                                                                          'profile.')
async def profile(ctx):
    try:
        await ctx.message.reply(delete_after=0.2, content="Generating Profile")
        arg = ctx.message.content.split(" ", 2)
        user = 'user'
        if len(arg) == 1:
            user = ctx.author.id
        if len(arg) > 1:
            user = await parseID(arg[1])

        if user:
            if isinstance(user, int):
                print("User is an int")
            else:
                await ctx.message.reply(delete_after=0.5, content="You need to specify a user.")
                return
        else:
            user = 'user'

        user_name = await client.fetch_user(user)

        profileemb = discord.Embed(colour=0xFFFFFF, title=f"{user_name.name}'s Adrift Profile.")
        try:
            embed = await generate_profile_embed(user, profileemb, ctx)
            if embed:
                await ctx.message.reply(embed=embed)
            else:
                await ctx.message.reply("ERROR?")
        except Exception as e:
            print("Error: ", e)
    except Exception as e:
        print(e)


###################################################################
##                       DISCORD BOT EVENTS                      ##
##                                                               ##
## Events emitted by the Discord client, that the bot can react  ##
## to.                                                           ##
##                                                               ##
###################################################################
@client.event
async def on_member_join(member):
    try:
        await update_user(member)
        await post_log(member.guild, 'JOIN', member, member, 'has joined the server!')
        await rolesonjoin(member.guild, member)
    except Exception as e:
        print("Error on join ", e)


@client.event
async def on_message(message):
    with open('guilds.json') as json_file:
        existingData = json.load(json_file)
    data = existingData

    if str(message.guild.id) not in data:
        return

    if isinstance(message.channel, discord.channel.DMChannel):
        return
    else:
        await update_user(message.author)
        await db_member_set(message.author, 'member_name', message.author.name)

    if message.channel.id in data[str(message.guild.id)]:
        with open('delays.json') as json_file:
            existingData = json.load(json_file)
        t_data = existingData
        d = t_data[str(message.guild.id)]
        if message.attachments:
            await message.add_reaction("<:heart_pansexual:905559517528485959>")
            await message.add_reaction("<:simp:905558608396292117>")
            await message.add_reaction("<:poke_psyduck_wut:905562122208034836>")
            await remove_msg(message, d)
            return
    
    await client.process_commands(message)


@client.event
async def on_raw_reaction_add(reaction):
    global coin_drop_message
    global coin_drop_reward

    if reaction.emoji.name == '⭐':
        message = await client.get_channel(reaction.channel_id).fetch_message(reaction.message_id)
        starboard_channel = await db_guild_get(message.guild, "starboard_id")

        if not message.author.bot and reaction.member.id != message.author.id:
            msg_id, stars = await client.pg.fetchrow(
                "SELECT starmessageid, stars FROM starboard WHERE rootmessageid = $1", message.id) or (None, 0)
            
            embed = discord.Embed(title="The People Have Voted! This is Starboard Worthy!", colour=0xFFFFFF,
                                  timestamp=datetime.datetime.utcnow())
            
            embed.add_field(name="Author", value=message.author.mention, inline=False)
            embed.add_field(name="Content", value=message.content or "[See attachment]", inline=False)
            embed.add_field(name="Original", value=f"[See Original to vote]({message.jump_url})", inline=False)
            embed.add_field(name="Stars", value=stars + 1, inline=False)

            if len(message.attachments):
                embed.set_image(url=message.attachments[0].url)

            if not stars:
                star_message = await client.get_channel(starboard_channel).send(embed=embed)
                new_starboard = await client.pg.execute("INSERT INTO starboard VALUES ($1, $2)", message.id,
                                                        star_message.id)
            else:
                star_message = await client.get_channel(starboard_channel).fetch_message(msg_id)
                await star_message.edit(embed=embed)
                increase_stars = await client.pg.execute(
                    "UPDATE starboard SET stars = stars + 1 WHERE rootmessageid = $1", message.id)

        else:
            await message.remove_reaction(reaction.emoji, reaction.member)
    if reaction.message.id == coin_drop_message.id and reaction.member.id != OWNER_IDS:
        embed = discord.Embed(title=str(f'Credit Drop Claimed!'), description='', colour=discord.Colour(0xFFFFFF))
        payout_text = ''
        multiplier = 0
        embed.add_field(name=str('Claimed'), value=str(
            f'{reaction.member.mention} claimed the {CURRENCY_EMOJI}{coin_drop_reward}'), inline=False)

        await coin_drop_message.channel.send(embed=embed)
        await coin_drop_message.delete()

        on_hand_credits = await db_member_get(reaction.member, 'credits')
        new_credits = on_hand_credits + coin_drop_reward
        new_credit_balance = await db_member_set(reaction.member, 'credits', new_credits)


@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        msg = '**You cannot run this command right now!** Please try again in {:.2f}s'.format(error.retry_after)
        await ctx.send(msg)


print("Logging in...")
client.loop.run_until_complete(create_db_pool())
client.loop.create_task(automated_drops())
client.loop.create_task(automated_water_reminder())
client.run(TOKEN)