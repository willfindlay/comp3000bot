import os
import sys

import discord
from discord.ext import commands

from comp3000bot import config
from comp3000bot.poll import Polls
from comp3000bot.manage_students import ManageStudents
from comp3000bot.status_message import StatusMessage
from comp3000bot.logger import get_logger


logger = get_logger()


class MyHelpCommand(commands.DefaultHelpCommand):
    """
    A help command with longer help messages.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.width = 300


async def ensure_guild_id(ctx: commands.Context):
    """
    If ctx.guild.guild_id is not the same as config.GUILD_ID, raise an exception.
    """
    if ctx.guild is None:
        return

    if ctx.guild.id != config.GUILD_ID:
        await ctx.send(
            "You have invoked this command from an unauthorized server. This incident has been reported."
        )
        msg = (
            f"An unauthorized server `{ctx.guild.name}` ({ctx.guild.id}) attempted "
            f"to invoke the command `{ctx.command.name}`"
        )
        logger.warn(msg)
        raise Exception(msg)


# List of commands for which the user should receive a detailed notification of
# failure
NOTIFY_WITH_DETAILS = [
    commands.UserInputError,
    commands.ArgumentParsingError,
    commands.CheckFailure,
    commands.DisabledCommand,
    commands.CommandOnCooldown,
    commands.MaxConcurrencyReached,
]


async def on_command_error(ctx: commands.Context, err: Exception):
    """
    Log command errors.
    """
    logger.exception(f"Error in command {ctx.command}:", exc_info=err)
    if any(map(lambda x: isinstance(err, x), NOTIFY_WITH_DETAILS)):
        await ctx.send(f'Command failed: {err}')
    else:
        await ctx.send(f'Command failed due to an unhandled exception.')


def main(sys_args=sys.argv[1:]):
    # Create directories to store data, if they don't already exist
    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.STUDENTS_DIR, exist_ok=True)

    # We now need to signal what "Intents" we want to use.
    # Since we require privileged intents, don't forget to turn those on via the
    # bot management interface in Discord's developer portal.
    intents = discord.Intents.all()

    # Create the bot with command prefix '!' and out list of "Intents"
    client = commands.Bot(command_prefix='!', intents=intents)

    # Override the default help command with something more, well, helpful...
    client.help_command = MyHelpCommand()

    # Add cogs, one for each category of operation
    client.add_cog(Polls(client))
    client.add_cog(ManageStudents(client))
    client.add_cog(StatusMessage(client))
    # TODO: Add a participation cog

    client.before_invoke(ensure_guild_id)
    client.on_command_error = on_command_error

    # Run the bot
    client.run(config.API_TOKEN)


if __name__ == "__main__":
    main()
