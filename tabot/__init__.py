import os
import sys

import discord
from discord.ext import commands

from tabot import config
from tabot.poll import Polls
from tabot.manage_students import ManageStudents

def main(sys_args = sys.argv[1:]):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.STUDENTS_DIR, exist_ok=True)

    client = commands.Bot(command_prefix='!')

    client.add_cog(Polls(client))
    client.add_cog(ManageStudents(client))

    client.run(config.API_TOKEN)

if __name__ == "__main__":
    main()
