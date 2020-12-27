import os
import sys

import discord
from discord.ext import commands

from comp3000bot import config
from comp3000bot.poll import Polls
from comp3000bot.manage_students import ManageStudents
from comp3000bot.status_message import StatusMessage


class MyHelpCommand(commands.DefaultHelpCommand):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.width = 300


def main(sys_args=sys.argv[1:]):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.STUDENTS_DIR, exist_ok=True)

    intents = discord.Intents.all()

    client = commands.Bot(command_prefix='!', intents=intents)
    client.help_command = MyHelpCommand()

    client.add_cog(Polls(client))
    client.add_cog(ManageStudents(client))
    client.add_cog(StatusMessage(client))

    client.run(config.API_TOKEN)


if __name__ == "__main__":
    main()
