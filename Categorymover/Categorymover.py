import asyncio
from asyncio import Task

import discord
from discord import Message
from discord.abc import Snowflake
from discord.ext import commands

from core import checks
from core.models import getLogger, PermissionLevel
from core.thread import Thread

emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️9️⃣"]
menu_description = "Please pick a category for your inquery"


class ReactionMenu(object):
    def __init__(self):
        super().__init__()
        self.cog: Categorymoverplugin
        self.thread: Thread
        self.initial_message: Message
        self.options: dict[str, Snowflake]
        self.menu: Message
        self.reaction_addr: Task
        self.is_dead: bool = False

    @classmethod
    async def create(cls, cog, thread, initial_message):
        self = ReactionMenu()
        self.cog = cog
        self.thread = thread
        self.initial_message = initial_message
        self.options = {}

        for (category, emoji) in zip(self.cog.categories.keys(), emojis):
            self.options[emoji] = category

        self.menu = await self.thread.recipient.send(embed=self._gen_embed())
        self.reaction_addr = asyncio.create_task(self._add_reactions())
        return self

    async def disband(self, moved_to=None):
        if self.is_dead:
            return
        self.is_dead = True
        self.reaction_addr.cancel()
        await self.reaction_addr
        if moved_to:
            asyncio.create_task(self._clear_reactions())
            await self.menu.edit(embed=discord.Embed(color=self.cog.bot.main_color, description=f"✅ Moved to `{self.cog.categories.get(str(moved_to.id), 'Unknown')}`"))
            await self.thread.channel.send(embed=discord.Embed(description=f"Moved to <#{moved_to.id}>", color=self.cog.bot.main_color))
        else:
            await self.menu.delete()
        del self.cog.running_responses[self.thread.id]

    async def process(self, payload: discord.RawReactionActionEvent):
        if self.is_dead:
            return
        if payload.emoji.name not in self.options:
            return
        category = discord.utils.get(self.cog.bot.modmail_guild.categories, id=int(self.options[payload.emoji.name]))
        if category:
            await self.thread.channel.move(category=category, end=True, sync_permissions=True, reason="Thread was moved by Reaction menu within modmail")
        await self.disband(moved_to=category)

    async def _add_reactions(self):
        try:
            for emoji in self.options.keys():
                await self.menu.add_reaction(emoji)
        except asyncio.CancelledError:
            pass

    async def _clear_reactions(self):
        for reaction in self.menu.reactions:
            print(reaction)
            if reaction.me:
                print("me")
                await reaction.remove(self.bot.user.id)

    def _gen_embed(self):
        embed = discord.Embed(color=self.cog.bot.main_color)
        rows = [self.cog.menu_description + "\n"]
        for emoji, category in self.options.items():
            rows.append(f"{emoji} - {self.cog.categories.get(category, 'Unknown')}")
        embed.description = "\n".join(rows)
        return embed


class Categorymoverplugin(commands.Cog):
    """Move threads automatically to reduce the worry for thread limit as well as better organization"""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.plugin_db.get_partition(self)
        self.logger = getLogger("CategoryMover")
        self.running_responses: dict[Snowflake, ReactionMenu] = {}  # userid, reactionMenu

        # settings
        self.enabled = True
        self.categories = {}
        self.menu_description = menu_description

        asyncio.create_task(self._set_options())

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if len(self.running_responses.keys()) == 0:
            return

        if payload.guild_id or payload.user_id not in self.running_responses or payload.user_id == self.bot.user.id:
            return

        if self.running_responses[payload.user_id].menu.id == payload.message_id:
            return await self.running_responses[payload.user_id].process(payload)

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

        if message.id in (threadMenu.menu.id, threadMenu.initial_message.id, threadMenu.thread.genesis_message.id):
            return
        await self.running_responses[thread.id].disband()

    @commands.Cog.listener()
    async def on_thread_ready(self, thread, creator, category, initial_message):
        if not self.enabled or not len(self.categories.keys()) >= 2:
            return

        # Assuming this message is created from a contact like function or if there is multiable recipients
        if creator or len(thread.recipients) > 1:
            self.logger.info(
                f"Ignoring thread for user {str(thread.recipient)} ({thread.recipient.id}) Created by contact like function or thread has more then one recipients")
            return

        self.running_responses[thread.id] = await ReactionMenu.create(self, thread, initial_message)

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

        if str(target.id) in self.categories:
            del self.categories[str(target.id)]
        else:
            if len(self.categories.keys()) > 9:
                return await ctx.send(
                    embed=discord.Embed(color=self.bot.error_color, description="Cannot add more then 9 categories!"))
            self.categories[str(target.id)] = info
        await self._update_config()
        return await ctx.send(embed=discord.Embed(color=self.bot.main_color,
                                                  description=f"{target} ({target.id}) has been {'added' if str(target.id) in self.categories else 'removed'}\n{f'With description: `{info}`' if str(target.id) in self.categories else ''}"))

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

    @cm.command("embed", aliases=["categories"])
    @checks.has_permissions(PermissionLevel.MOD)
    async def cm_categories(self, ctx):
        """View how the current menu looks!

        Usage: `cm embed`
        """
        embed = discord.Embed(color=self.bot.main_color)
        rows = [self.menu_description + "\n"]

        for (category, emoji) in zip(self.categories.keys(), emojis):
            rows.append(f"{emoji} - {self.categories.get(category, 'Unknown')}")
        embed.description = "\n".join(rows)
        return await ctx.send(content="Menu example:", embed=embed)

    async def _update_config(self):
        await self.db.find_one_and_update(
            {"_id": "config"},
            {
                "$set": {
                    "enabled": self.enabled,
                    "categories": self.categories,
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
        self.categories = config.get("categories", {})
        self.menu_description = config.get("menu_description", menu_description)


def setup(bot):
    bot.add_cog(Categorymoverplugin(bot))
