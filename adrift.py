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

###################################################################
##                      DISCORD BOT COMMANDS                     ##
##                                                               ##
## Executable commands for use inside of the Discord client.     ##
##                                                               ##
###################################################################

###################################################################
##                       DISCORD BOT EVENTS                      ##
##                                                               ##
## Events emitted by the Discord client, that the bot can react  ##
## to.                                                           ##
##                                                               ##
###################################################################


print("Logging in...")
client.loop.run_until_complete(create_db_pool())
client.run(TOKEN)