import asyncio
import typing
from datetime import datetime

import discord
from discord import Message, ButtonStyle
from discord.abc import Snowflake
from discord.ext import commands

from core import checks
from core.models import getLogger, PermissionLevel
from core.thread import Thread

menu_description = "Please pick a category for your inquery"


def fxCallback(item: discord.ui.Item, callback: typing.Callable) -> typing.Any:
    item.callback = callback
    return item


# TODO: CALLBACKS FOR BUTTONS | MODELS

class Category(typing.TypedDict):
    label: str
    description: typing.Optional[str]
    mentions: typing.Optional[list[Snowflake]]


class CategorySettings(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.cog: typing.Optional[Categorymoverplugin] = None
        self.target: typing.Optional[discord.CategoryChannel] = None
        self.message: typing.Optional[discord.Message] = None

    @classmethod
    async def create_from_message(cls, msg, cog, target):
        self = CategorySettings()
        self.cog = cog
        self.target = target
        self.message = msg
        await self._update_message()
        return self


    async def _update_message(self):
        # update buttons and embeds here :D
        for child in self.children:
            if child.custom_id == "delete_button":
                child.disabled = self.target.id not in self.cog.conf_categories
        await self.message.edit(embed=self._generate_embed(), view=self)


    def _generate_embed(self):
        data: Category = self.cog.conf_categories.get(self.target.id, {})

        ids = data.get('mentions', [])
        mentions = []
        if ids:
            for _id in ids:
                obj: typing.Union[discord.member.Member, discord.role.Role, None] = self.cog.search_id(_id)
                if obj is not None:
                    mentions.append(obj.mention)

        embed = discord.Embed(title="Category Settings", description=f"For {self.target.mention} (`{self.target.id}`)", timestamp=datetime.now())
        embed.set_footer(text="Last updated")
        embed.add_field(name="Label:", value=data.get("label", "N/A"))
        embed.add_field(name="Description:", value=data.get("description", "N/A"))
        embed.add_field(name="Mentions:", value=" ".join(mentions))
        return embed

    async def stop(self):
        self.clear_items()
        await self._update_message()
        super().stop()

    async def on_timeout(self):
        await self.stop()

    @discord.ui.button(label='Delete', style=ButtonStyle.red, custom_id="delete_button")
    async def Delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cog.conf_categories.pop(self.target)
        await self.cog.update_config()
        await self.stop()


    @discord.ui.button(label='Cancel', style=ButtonStyle.grey, custom_id="cancel_button")
    async def Cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.delete_original_response()
        await self.stop()


class SelectMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.cog: typing.Optional[Categorymoverplugin] = None
        self.thread: typing.Optional[Thread] = None
        self.initial_message: typing.Optional[Message] = None
        self.menu_message: typing.Optional[Message] = None
        self.selections: typing.Optional[discord.ui.Select] = None

    @classmethod
    async def create(cls, cog, thread, initial_message):
        self = SelectMenu()
        self.cog = cog
        self.thread = thread
        self.initial_message = initial_message
        self.selections = fxCallback(discord.ui.Select(placeholder="Choose a Category!", min_values=1, max_values=1),
                                     callback=self.callback)

        for category_id, category in self.cog.conf_categories.items():
            self.selections.add_option(label=category.get('label', None), value=str(category_id),
                                       description=category.get('description', None))

        self.add_item(self.selections)
        self.menu_message = await self.thread.recipient.send(embed=discord.Embed(color=self.cog.bot.main_color, description=self.cog.menu_description), view=self)
        return self

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.disband(discord.utils.get(self.cog.bot.modmail_guild.categories, id=int(self.selections.values[0])))

    async def on_timeout(self):
        await self.disband(move_to=None)

    async def disband(self, move_to=None):
        self.stop()
        if move_to:
            c: Category = self.cog.conf_categories.get(move_to.id, {})
            await self.thread.channel.move(category=move_to, end=True, sync_permissions=True,
                                           reason="Thread was moved by Reaction menu within modmail")
            await self.thread.channel.send(content=await self._get_mentions(move_to.id),
                                           embed=discord.Embed(description=f"Moved to <#{move_to.id}>",
                                                               color=self.cog.bot.main_color))
            self.clear_items()
            await self.menu_message.edit(embed=discord.Embed(color=self.cog.bot.main_color,
                                                             description=f"✅ Moved to: {c.get('label', 'unknown')}"),
                                         view=self)
        else:
            await self.menu_message.delete()
        del self.cog.running_responses[self.thread.id]

    async def _get_mentions(self, category_id):  # noqa
        c: Category = self.cog.conf_categories.get(category_id, {})
        ids = c.get('mentions', [])
        if ids:
            mentions = []
            for _id in ids:
                obj: typing.Union[discord.member.Member, discord.role.Role, None] = self.cog.search_id(_id)
                if obj is not None:
                    mentions.append(obj.mention)
            return " ".join(mentions)
        return None


class Categorymoverplugin(commands.Cog):
    """Move threads automatically to reduce the worry for thread limit as well as better organization"""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.plugin_db.get_partition(self)
        self.logger = getLogger("CategoryMover")

        self.running_responses: dict[typing.Union[Snowflake, int], ReactionMenu] = {}  # userid, reactionMenu

        # settings
        self.enabled = True
        self.conf_categories: dict[typing.Union[Snowflake, int], Category] = {}
        self.menu_description = menu_description
        asyncio.create_task(self._set_options())

    def search_id(self, _id):
        # roles > member > None
        role = discord.utils.get(self.cog.bot.modmail_guild.roles, id=_id)
        if role:
           return role
        member = discord.utils.get(self.cog.bot.modmail_guild.members, id=_id)
        if member:
            return member
        return None

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
        if not self.enabled or not len(self.conf_categories.keys()) >= 2:
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
    async def cm_toggle(self, ctx):
        """Disable or enable the plugin.

        Usage: `cm toggle`
        """
        self.enabled = not self.enabled
        await self._update_config()
        embed = discord.Embed(color=self.bot.main_color,
                              description="Guild member watch has been " + ("enabled" if self.enabled else "disabled"))
        return await ctx.reply(embed=embed)

    @cm.command("category")
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def cm_category(self, ctx, target: discord.CategoryChannel):
        """Add or remove categories used in Menu
        Usage: `cm category (category_id)`
        """
        if not target:
            raise commands.BadArgument("Category does not exist")
        msg = await ctx.send("Loading...")
        await CategorySettings.create_from_message(msg, self, target)

    async def update_config(self):
        await self.db.find_one_and_update(
            {"_id": "config"},
            {
                "$set": {
                    "enabled": self.enabled,
                    "conf_categories": dict((str(key), value) for (key, value) in self.conf_categories.items()),
                    "menu_description": self.menu_description
                }
            },
            upsert=True,
        )

    async def _set_options(self):
        config = await self.db.find_one({"_id": "config"})

        if config is None:
            await self.update_config()
            return

        self.enabled = config.get("enabled", True)
        self.conf_categories = dict((int(key), value) for (key, value) in config.get("conf_categories", {}).items())
        self.menu_description = config.get("menu_description", menu_description)


async def setup(bot):
    await bot.add_cog(Categorymoverplugin(bot))
