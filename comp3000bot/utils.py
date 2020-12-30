from io import StringIO
import csv
from typing import Tuple, Iterable, Any

import discord
from discord.ext import commands


def get_guild(bot: commands.Bot, guild_name: str) -> discord.Guild:
    """
    Get the guild @guild_name that @bot belongs to or raise an exception.
    """
    guild = discord.utils.get(bot.guilds, name=guild_name)
    if guild is None:
        raise Exception(f'No such guild {guild_name}')
    return guild


def get_guild_by_id(bot: commands.Bot, guild_id: int) -> discord.Guild:
    """
    Get the guild @guild_id that @bot belongs to or raise an exception.
    """
    guild = discord.utils.get(bot.guilds, id=guild_id)
    if guild is None:
        raise Exception(f'No such guild {guild_id}')
    return guild


def get_role(guild: discord.Guild, *role_names: str) -> discord.Role:
    """
    Get the first role found in @names or raise an Exception.
    """
    for name in role_names:
        role = discord.utils.get(guild.roles, name=name)
        if role:
            return role
    raise Exception(f'Unable to find any role in {", ".join(role_names)}')


def get_text_channel(
    guild: discord.Guild, *text_channel_names: str
) -> discord.TextChannel:
    """
    Get the first text_channel found in @names or raise an Exception.
    """
    for name in text_channel_names:
        text_channel = discord.utils.get(guild.text_channels, name=name)
        if text_channel:
            return text_channel
    raise Exception(
        f'Unable to find any text channel in {", ".join(text_channel_names)}'
    )


def get_text_channel_or_curr(ctx: commands.Context, *names: str) -> discord.TextChannel:
    """
    Get the first text channel found in @names or return the current channel.
    """
    for name in names:
        channel = discord.utils.get(ctx.guild.text_channels, name=name)
        if channel:
            return channel
    return ctx.channel


def generate_file(name: str, contents: str, spoiler=False) -> discord.File:
    """
    Generate an in-memory file and return a :class:discord.File that contains it.
    """
    out = StringIO()
    out.write(contents)
    out.seek(0)
    return discord.File(out, filename=name, spoiler=spoiler)


def generate_csv_file(
    name: str, header: Tuple[Any, ...], rows: Iterable[Tuple[Any, ...]], spoiler=False
) -> discord.File:
    """
    Generate an in-memory file and return a :class:discord.File that contains it.
    """
    out = StringIO()
    writer = csv.writer(out)
    writer.writerows([header, *rows])
    out.seek(0)
    return discord.File(out, filename=name, spoiler=spoiler)
