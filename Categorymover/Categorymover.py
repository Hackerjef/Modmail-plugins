import asyncio
import traceback
import typing
import uuid
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


class Category(typing.TypedDict):
    label: str
    description: typing.Optional[str]
    mentions: typing.Optional[list[Snowflake]]


class TextResp(discord.ui.Modal, title='Response'):
    async def on_submit(self, interaction: discord.Interaction, /) -> None:
        await interaction.response.defer()

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message('Oops! Something went wrong.', ephemeral=True)
        traceback.print_exception(type(error), error, error.__traceback__)

    def get_child_value(self, custom_id):
        for child in self._children:
            if child.custom_id == custom_id:
                return child.__getattribute__("value")
        raise Exception(f"Child {custom_id} not found")


class CategorySettings(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=1800)
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


    async def _update_message(self, interaction=None, noview=False):
        if not noview:
            for child in self.children:
                if getattr(child, "custom_id") == "edit_description":
                    child.disabled = self.target.id not in self.cog.conf_categories
                    continue

                if getattr(child, "custom_id") == "clear":
                    child.disabled = self.target.id not in self.cog.conf_categories
                    continue

        if interaction:
            await interaction.response.edit_message(content=None, embed=self._generate_embed(), view=None if noview else self)
        else:
            await self.message.edit(content=None, embed=self._generate_embed(), view=None if noview else self)


    def _generate_embed(self):
        data: Category = self.cog.conf_categories.get(self.target.id, {})

        ids = data.get('mentions', [])
        mentions = []
        if ids:
            for _id in ids:
                obj: typing.Union[discord.member.Member, discord.role.Role, None] = self.cog.search_id(_id)
                if obj is not None:
                    mentions.append(obj.mention)
        embed = discord.Embed(title="Category Settings", description=f"For {self.target.mention} (`{self.target.id}`)", timestamp=datetime.now(), color=65535)
        embed.set_footer(text="Last updated")
        embed.add_field(name="Label:", value=data.get("label", "N/A"), inline=False)
        embed.add_field(name="Description:", value=data.get("description", "N/A"), inline=False)
        if mentions:
            embed.add_field(name="Mentions:", value=" ".join(mentions), inline=False)
        else:
            embed.add_field(name="Mentions:", value="N/A", inline=False)
        return embed

    async def stop(self, interaction=None):
        await self._update_message(interaction=interaction, noview=True)
        super().stop()

    async def on_timeout(self):
        await self.stop()


    @discord.ui.button(label="Edit Label", style=ButtonStyle.blurple, disabled=False, custom_id="edit_label")
    async def btn_edit_lbl(self, interaction: discord.Interaction, button: discord.ui.Button):
        t = TextResp(timeout=120)
        t.add_item(discord.ui.TextInput(custom_id="label", label="label:", placeholder="Please enter a name for the category", default=self.cog.conf_categories.get(self.target.id, {}).get('label', None), required=True))
        await interaction.response.send_modal(t)
        await t.wait()
        if t.get_child_value('label') == "":
            return
        if self.target.id not in self.cog.conf_categories:
            self.cog.conf_categories[self.target.id] = Category(label=t.get_child_value('label')) # noqa
        else:
            self.cog.conf_categories[self.target.id].update({'label': t.get_child_value('label')})

        await self.cog.update_config()
        await self._update_message()

    @discord.ui.button(label="Edit Description", style=ButtonStyle.blurple, disabled=True, custom_id="edit_description")
    async def btn_edit_des(self, interaction: discord.Interaction, button: discord.ui.Button):
        description = TextResp(timeout=120)
        description.add_item(discord.ui.TextInput(custom_id="description", label="Description:", placeholder="Please enter a description for the category (put N/A to remove)", default=self.cog.conf_categories.get(self.target.id, {}).get('description', 'N/A'), required=False))
        await interaction.response.send_modal(description)
        await description.wait()
        if description.get_child_value('description') == "":
            return

        if description.get_child_value('description') == "N/A":
            if 'description' in self.cog.conf_categories[self.target.id]:
                self.cog.conf_categories[self.target.id].__delitem__('description')
        else:
            self.cog.conf_categories[self.target.id].update({'description': description.get_child_value('description')})
        await self.cog.update_config()
        await self._update_message()
    @discord.ui.button(label="Clear Settings", style=ButtonStyle.red, disabled=True, custom_id="clear")
    async def btn_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.target.id in self.cog.conf_categories:
            self.cog.conf_categories.pop(self.target.id)
            await self.cog.update_config()
        else:
            self.cog.logger.warning(f"{self.target.id} is missing from config?")
        await self._update_message(interaction=interaction)


    @discord.ui.button(label="Close", style=ButtonStyle.grey, disabled=False, custom_id="cancel")
    async def btn_cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.stop(interaction=interaction)


class SelectMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.cog: typing.Optional[Categorymoverplugin] = None
        self.thread: typing.Optional[Thread] = None
        self.initial_message: typing.Optional[Message] = None
        self.menu_message: typing.Optional[Message] = None
        self.selections: typing.Optional[discord.ui.Select] = None
        self.nuance: str = str(uuid.uuid4())

    @classmethod
    async def create(cls, cog, thread, initial_message):
        self = SelectMenu()
        self.cog = cog
        self.thread = thread
        self.initial_message = initial_message

        self.selections = fxCallback(discord.ui.Select(placeholder="Choose a Category!", min_values=1, max_values=1, custom_id=f"{self.nuance}_cm_selectmenu"), callback=self.callback)

        for category_id, category in self.cog.conf_categories.items():
            self.selections.add_option(label=category.get('label', None), value=str(category_id), description=category.get('description', None))

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
            try:
                await self.menu_message.delete()
            except Exception: # noqa
                pass
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
        self.conf_categories: dict[int, Category] = {}
        self.menu_description = menu_description
        asyncio.create_task(self._set_options())

    def search_id(self, _id):
        # roles > member > None
        role = discord.utils.get(self.bot.modmail_guild.roles, id=_id)
        if role:
           return role
        member = discord.utils.get(self.bot.modmail_guild.members, id=_id)
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
        await self.update_config()
        embed = discord.Embed(color=self.bot.main_color,
                              description="Category mover has been " + ("enabled" if self.enabled else "disabled"))
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
