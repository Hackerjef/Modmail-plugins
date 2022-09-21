import asyncio
import typing
from asyncio import Task

import discord
from discord import Message
from discord.abc import Snowflake
from discord.ext import commands

from core import checks
from core.models import getLogger, PermissionLevel
from core.thread import Thread

# emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️9️⃣"]
menu_description = "Please pick a category for your inquery"


class SelectMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=3000)
        self.cog: typing.Optional[Categorymoverplugin] = None
        self.thread: typing.Optional[Thread] = None
        self.initial_message: typing.Optional[Message] = None
        self.menu_message: typing.Optional[Message] = None

    @classmethod
    async def create(cls, cog, thread, initial_message):
        self = SelectMenu()
        self.cog = cog
        self.thread = thread
        self.initial_message = initial_message

        selections = discord.ui.Select(placeholder="Choose a Category!", min_values=1, max_values=1)

        for category, description in self.cog.categories.items():
            selections.add_option(label="category", value=str(category), description=description)

        self.add_item(selections)
        self.menu_message = await self.thread.recipient.send(embed=discord.Embed(color=self.cog.bot.main_color, description=self.cog.menu_description), view=self)

        return self

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        print(self.values[0])
        moved_to = None
        await self.disband(moved_to)
        #await interaction.response.send_message(content=f"Your choice is {self.values[0]}!",ephemeral=True)

    async def on_timeout(self):
        await self.disband(moved_to=None)

    async def disband(self, moved_to=None):
        if moved_to:
            pass
        else:
            pass
        del self.cog.running_responses[discord.Object(id=self.thread.id)]

    async def _get_pings(self, category_id):  # noqa
        ping_ids = self.cog.categories_ping.get(category_id, [])
        if ping_ids:
            pings = []
            for _id in ping_ids:
                obj: typing.Union[discord.member.Member, discord.role.Role] = discord.utils.get(
                    self.cog.bot.modmail_guild.roles + self.cog.bot.modmail_guild.members, id=_id)
                if obj is not None:
                    pings.append(obj.mention)
            return " ".join(pings)
        return None


class Categorymoverplugin(commands.Cog):
    """Move threads automatically to reduce the worry for thread limit as well as better organization"""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.plugin_db.get_partition(self)
        self.logger = getLogger("CategoryMover")
        self.running_responses: dict[Snowflake, ReactionMenu] = {}  # userid, reactionMenu

        # settings
        self.enabled = True
        self.categories: dict[Snowflake, str] = {}  # Category, Category Description
        self.categories_ping: dict[Snowflake, list[Snowflake]]
        self.menu_description = menu_description
        asyncio.create_task(self._set_options())

    @commands.Cog.listener()
    async def on_thread_close(self, thread, closer, silent, delete_channel, message, scheduled):
        if thread.id not in self.running_responses:
            return
        await self.running_responses[thread.id].disband()

    @commands.Cog.listener()
    async def on_thread_reply(self, thread, from_mod, message, anonymous, plain):
        threadMenu = self.running_responses.get(thread.id, None)
        if not threadMenu:
            return

        gm = await threadMenu.thread.get_genesis_message()
        if message.id in (threadMenu.menu_message.id, threadMenu.initial_message.id, gm.id):
            return
        await self.running_responses[thread.id].disband()

    @commands.Cog.listener()
    async def on_thread_ready(self, thread, creator, category, initial_message):
        if not self.enabled or not len(self.categories.keys()) >= 2:
            return

        # Assuming this message is created from a contact like function or if there is one or more recipients
        if creator or len(thread.recipients) > 1:
            self.logger.info(
                f"Ignoring thread for user {str(thread.recipient)} ({thread.recipient.id}) Created by contact like function or thread has more then one recipients")
            return

        self.running_responses[thread.id] = await SelectMenu.create(self, thread, initial_message)

    @commands.group(name="cm", invoke_without_command=True)
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def cm(self, ctx):
        """
            Plugin that moves threads automatically to reduce the worry for thread limit as well as better organization
        """
        await ctx.send_help(ctx.command)

    @cm.command("toggle")
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def gmw_toggle(self, ctx):
        """Disable or enable the plugin.

        Usage: `cm toggle`
        """
        self.enabled = not self.enabled
        await self._update_config()
        embed = discord.Embed(color=self.bot.main_color,
                              description="Guild member watch has been " + ("enabled" if self.enabled else "disabled"))
        return await ctx.send(embed=embed)

    @cm.command("category")
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def cm_category(self, ctx, target: discord.CategoryChannel, *, info: str):
        """Add or remove categories used in Menu

        Usage: `cm category (category_id) (info about category for users)`
        """
        if not target:
            raise commands.BadArgument("Category does not exist")

        if target.id in self.categories:
            del self.categories[target.id]
        else:
            if len(self.categories.keys()) > 9:
                return await ctx.send(
                    embed=discord.Embed(color=self.bot.error_color, description="Cannot add more then 9 categories!"))
            self.categories[target.id] = info
        await self._update_config()
        return await ctx.send(embed=discord.Embed(color=self.bot.main_color,
                                                  description=f"{target} ({target.id}) has been {'added' if target.id in self.categories else 'removed'}\n{f'With description: `{info}`' if target.id in self.categories else ''}"))

    # NOTE: add clause for snowflake in target (pos typing.Union discord.snowflake.Snowflake uwu
    @cm.command("ping")
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def cm_ping(self, ctx, target: discord.CategoryChannel,
                      mentionable: typing.Union[discord.member.Member, discord.role.Role] = None):
        """Add or remove categories used in Menu

        Usage: `cm ping (category_id) (User/Role)
        """
        if not target:
            raise commands.BadArgument("Category does not exist")

        if mentionable is None:
            desc = []
            for _id in self.categories_ping.get(target.id, []):
                obj: typing.Union[discord.member.Member, discord.role.Role] = discord.utils.get(
                    self.bot.modmail_guild.roles + self.bot.modmail_guild.members, id=_id)
                if obj is not None:
                    desc.append(f"{str(obj)} - (`{obj.id}`)")
            return await ctx.send(embed=discord.Embed(color=self.bot.main_color, description="\n".join(desc)))

        if mentionable.id in self.categories_ping.get(target.id, []):
            self.categories_ping.get(target.id, []).remove(mentionable.id)
            await ctx.send(embed=discord.Embed(color=self.bot.main_color,
                                               description=f"Removed {mentionable} ({mentionable.id}) to {target} ({target.id})"))
        else:
            self.categories_ping.get(target.id, []).append(mentionable.id)
            await ctx.send(embed=discord.Embed(color=self.bot.main_color,
                                               description=f"Added {mentionable} ({mentionable.id}) to {target} ({target.id})"))
        await self._update_config()

    @cm.command("set_description")
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def cm_set_description(self, ctx, *, text=None):
        """Sets description of the menu

        Text can be blank to revert to default
        Usage: `cm set_description (text)`
        """
        if text:
            self.menu_description = text
        else:
            self.menu_description = menu_description
        await self._update_config()
        return await ctx.send(embed=discord.Embed(color=self.bot.main_color,
                                                  description=f"Menu Description set to:\n`{self.menu_description}`"))

    # TODO: remake
    # @cm.command("embed", aliases=["categories"])
    # @checks.has_permissions(PermissionLevel.MOD)
    # async def cm_categories(self, ctx):
    #     """View how the current menu looks!
    #
    #     Usage: `cm embed`
    #     """
    #     embed = discord.Embed(color=self.bot.main_color)
    #     rows = [self.menu_description + "\n"]
    #
    #     for (category, emoji) in zip(self.categories.keys(), emojis):
    #         rows.append(f"{emoji} - {self.categories.get(category, 'Unknown')}")
    #     embed.description = "\n".join(rows)
    #     return await ctx.send(content="Menu example:", embed=embed)

    async def _update_config(self):
        await self.db.find_one_and_update(
            {"_id": "config"},
            {
                "$set": {
                    "enabled": self.enabled,
                    "categories": dict((str(key), value) for (key, value) in self.categories.items()),
                    "categories_ping": dict((str(key), value) for (key, value) in self.categories_ping.items()),
                    "menu_description": self.menu_description
                }
            },
            upsert=True,
        )

    async def _set_options(self):
        config = await self.db.find_one({"_id": "config"})

        if config is None:
            await self._update_config()
            return

        self.enabled = config.get("enabled", True)
        self.categories = dict((int(key), value) for (key, value) in config.get("categories", {}).items())
        self.categories_ping = dict((int(key), value) for (key, value) in config.get("categories_ping", {}).items())
        self.menu_description = config.get("menu_description", menu_description)


async def setup(bot):
    await bot.add_cog(Categorymoverplugin(bot))
