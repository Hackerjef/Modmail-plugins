import asyncio
import sqlite3
import re
import os
from datetime import datetime
import secrets
from io import BytesIO

import discord
from discord.ext import commands

# This used to be included in kyb3r/modmail-plugins but it has been broken so Wanted to fix it uwu

USER_CACHE = {}


class Thread:
    statuses = {1: "open", 2: "closed", 3: "suspended"}

    __slots__ = [
        "bot",
        "id",
        "status",
        "recipient",
        "creator",
        "creator_mod",
        "closer",
        "channel_id",
        "created_at",
        "scheduled_close_at",
        "scheduled_close_id",
        "alert_id",
        "messages",
    ]

    @classmethod
    async def from_data(cls, bot, data, cursor):
        # id
        # status
        # is_legacy
        # user_id
        # user_name
        # channel_id
        # created_at
        # scheduled_close_at
        # scheduled_close_id
        # scheduled_close_name
        # alert_id

        self = cls()
        self.bot = bot
        self.id = data[0]
        self.status = self.statuses[data[1]]

        user_id = data[3]
        if user_id:
            self.recipient = bot.get_user(int(user_id))
            if self.recipient is None:
                try:
                    if int(user_id) in USER_CACHE:
                        user = USER_CACHE[int(user_id)]
                        self.recipient = user
                    else:
                        self.recipient = await bot.fetch_user(int(user_id))
                        USER_CACHE[int(user_id)] = self.recipient
                except discord.NotFound:
                    self.recipient = None
        else:
            self.recipient = None

        self.creator = self.recipient
        self.creator_mod = False
        self.closer = None

        self.channel_id = int(data[5])
        self.created_at = datetime.fromisoformat(data[6])
        self.scheduled_close_at = (
            datetime.fromisoformat(data[7]) if data[7] else datetime.utcnow()
        )
        self.scheduled_close_id = data[8]
        self.alert_id = data[9]

        self.messages = []

        if self.id:
            for i in cursor.execute(
                    "SELECT * FROM 'thread_messages' WHERE thread_id == ?", (self.id,)
            ):
                message = await ThreadMessage.from_data(bot, i)
                if message.type_ == "command" and "close" in message.body:
                    self.closer = message.author
                elif message.type_ == "system" and message.body.startswith(
                        "Thread was opened by "
                ):
                    # user used the `newthread` command
                    mod = message.body[:21]  # gets name#discrim
                    for i in bot.users:
                        if str(i) == mod:
                            self.creator = i
                            self.creator_mod = True
                            break
                self.messages.append(message)
        return self

    def serialize(self):
        """Turns it into a document"""
        payload = {
            "migrated": True,
            "open": not bool(self.closer),
            "channel_id": str(self.channel_id),
            "guild_id": str(self.bot.guild_id),
            "created_at": str(self.created_at),
            "closed_at": str(self.scheduled_close_at),
            "closer": None,
            "recipient": {
                "id": str(self.recipient.id),
                "name": self.recipient.name,
                "discriminator": self.recipient.discriminator,
                "avatar_url": str(self.recipient.display_avatar.url),
                "mod": False,
            },
            "creator": {
                "id": str(self.creator.id),
                "name": self.creator.name,
                "discriminator": self.creator.discriminator,
                "avatar_url": str(self.creator.display_avatar.url),
                "mod": self.creator_mod,
            },
            "messages": [m.serialize() for m in self.messages if m.serialize()],
        }
        if self.closer:
            payload["closer"] = {
                "id": str(self.closer.id),
                "name": self.closer.name,
                "discriminator": self.closer.discriminator,
                "avatar_url": str(self.closer.display_avatar.url),
                "mod": True,
            }
        return payload


class ThreadMessage:
    types = {
        1: "system",
        2: "chat",
        3: "from_user",
        4: "to_user",
        5: "legacy",
        6: "command",
        7: "system_to_user",
        8: "reply_edited",
        9: "reply_deleted"
    }

    __slots__ = [
        "bot",
        "id",
        "type_",
        "author",
        "body",
        "attachments",
        "content",
        "is_anonymous",
        "dm_message_id",
        "created_at",
    ]

    @classmethod
    async def from_data(cls, bot, data):
        # id
        # thread_id
        # message_type
        # user_id
        # user_name
        # body
        # is_anonymous
        # dm_message_id
        # created_at

        self = cls()
        self.bot = bot
        self.id = data[1]
        self.type_ = self.types[data[2]]

        user_id = data[3]
        if user_id:
            self.author = bot.get_user(int(user_id))
            if self.author is None:
                try:
                    if int(user_id) in USER_CACHE:
                        user = USER_CACHE[int(user_id)]
                        self.author = user
                    else:
                        self.author = await bot.fetch_user(int(user_id))
                        USER_CACHE[int(user_id)] = self.author
                except discord.NotFound:
                    self.author = None
        else:
            self.author = None

        self.body = data[16]

        pattern = re.compile(r"http://[\d.]+:\d+/attachments/\d+/.*")
        self.attachments = pattern.findall(str(self.body))
        if self.attachments:
            index = self.body.find(self.attachments[0])
            self.content = self.body[:index]
        else:
            self.content = self.body

        self.is_anonymous = data[5]
        self.dm_message_id = data[6]
        self.created_at = datetime.fromisoformat(data[7])
        self.attachments = pattern.findall(str(self.body))
        return self

    def serialize(self):
        if self.type_ in ("from_user", "to_user"):
            return {
                "timestamp": str(self.created_at),
                "message_id": self.dm_message_id,
                "content": self.content,
                "author": {
                    "id": str(self.author.id),
                    "name": self.author.name,
                    "discriminator": self.author.discriminator,
                    "avatar_url": str(self.author.display_avatar.url),
                    "mod": self.type_ == "to_user",
                }
                if self.author
                else None,
                "attachments": self.attachments,
            }


class DragoryMigrateRemux(commands.Cog):
    """
    Cog that migrates thread logs from [Dragory's](https://github.com/dragory/modmailbot) 
    modmail bot to this one.
    Fixed/edited by Nadie
    """

    def __init__(self, bot):
        self.bot = bot
        self.output = ""

    @commands.command()
    @commands.is_owner()
    async def migratedb(self, ctx, url=None):
        """Migrates a database file to the mongo db.
        
        Provide an sqlite file as the attachment or a url 
        pointing to the sqlite db.
        """

        self.output = ""
        try:
            url = url or ctx.message.attachments[0].url
        except IndexError:
            await ctx.send("Provide an sqlite file as the attachment.")

        async with self.bot.session.get(url) as resp:
            # TODO: use BytesIO or sth
            with open("dragorydb.sqlite", "wb+") as f:
                f.write(await resp.read())

        conn = sqlite3.connect("dragorydb.sqlite")
        c = conn.cursor()

        # Blocked Users
        for row in c.execute("SELECT * FROM 'blocked_users'"):
            # user_id
            # user_name
            # blocked_by
            # blocked_at

            user_id = row[0]

            cmd = self.bot.get_command("block")

            if int(user_id) in USER_CACHE:
                user = USER_CACHE[int(user_id)]
            else:
                user = await self.bot.fetch_user(int(user_id))
                USER_CACHE[int(user_id)] = user
            self.bot.loop.create_task(ctx.invoke(cmd, user=user))

        # Snippets
        for row in c.execute("SELECT * FROM 'snippets'"):
            # trigger	body	created_by	created_at
            name = row[0]
            value = row[1]

            if "snippets" not in self.bot.config.cache:
                self.bot.config["snippets"] = {}

            self.bot.config.snippets[name] = value
            self.output += f"Snippet {name} added: {value}\n"

        prefix = self.bot.config["log_url_prefix"]
        if prefix == "NONE":
            prefix = ""

        async def convert_thread_log(row):
            thread = await Thread.from_data(self.bot, row, c)
            converted = thread.serialize()
            key = secrets.token_hex(6)
            converted["key"] = key
            converted["_id"] = key
            await self.bot.db.logs.insert_one(converted)
            log_url = f"{self.bot.config['log_url']}{prefix}/{key}"
            print(f"Posted thread log: {log_url}")
            self.output += f"Posted thread log: {log_url}\n"

        # Threads
        for row in c.execute("SELECT * FROM 'threads'"):
            await convert_thread_log(row)

        await self.bot.config.update()
        conn.close()
        os.remove("dragorydb.sqlite")

        bytes_io = BytesIO(self.output.encode('utf-8'))
        await ctx.send("Done!, Log output", file=discord.File(fp=bytes_io, filename='output.txt'))


async def setup(bot):
    await bot.add_cog(DragoryMigrateRemux(bot))
