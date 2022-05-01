import asyncio

import discord
from discord.ext import commands

from core import checks
from core.models import getLogger, PermissionLevel


class Guildmemberwatch(commands.Cog):
    """Plugin to watch specific guilds users, if they made a thread show message that they joined/left the guild :)"""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.plugin_db.get_partition(self)
        self.logger = getLogger(__name__)

        # settings
        self.enabled = True
        self.watching_guilds: list = list()
        asyncio.create_task(self._set_options())

    async def _update_config(self):
        await self.db.find_one_and_update(
            {"_id": "config"},
            {
                "$set": {
                    "enabled": self.enabled,
                    "watching_guilds": self.watching_guilds,
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
        self.allow_evidence_share = config.get("watching_guilds", [])

    @commands.Cog.listener()
    async def on_member_join(self, member):
        thread = self.bot.threads.find(recipient_id=member.id)
        if not thread:
            return
        self.logger.info(
            f"{member} ({member.id}) has joined guild {member.guild} ({member.guild.id}) with an active thread")
        embed = discord.Embed(description=f"{member} ({member.id}) has joined {member.guild} ({member.guild.id})",
                              color=self.bot.main_color)
        thread.channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        thread = self.bot.threads.find(recipient_id=member.id)
        if not thread:
            return
        self.logger.info(
            f"{member} ({member.id}) has left guild {member.guild} ({member.guild.id}) with an active thread")
        embed = discord.Embed(description=f"{member} ({member.id}) has left {member.guild} ({member.guild.id})",
                              color=self.bot.error_color)
        thread.channel.send(embed=embed)

    @commands.group(name="gmw", invoke_without_command=True)
    @checks.has_permissions(PermissionLevel.OWNER)
    async def gmw(self, ctx):
        """
            Plugin that watches guild member joins/leaves
        """
        await ctx.send_help(ctx.command)

    @gmw.command("toggle")
    @checks.has_permissions(PermissionLevel.OWNER)
    async def gmw_toggle(self, ctx):
        """Disable or enable the oauth system.

        Usage: `gmw toggle`
        """

        self.enabled = not self.enabled
        await self._update_config()
        embed = discord.Embed(color=self.bot.main_color)
        embed.description = "Guild member watch has been " + ("enabled" if self.enabled else "disabled")
        return await ctx.send(embed=embed)

    @gmw.command("watch")
    @checks.has_permissions(PermissionLevel.OWNER)
    async def guw_watch(self, ctx, target: discord.Guild):
        if not target:
            raise commands.BadArgument("Guild does not exist")

        if target.id in self.watching_guilds:
            self.watching_guilds.remove(target.id)
        else:
            self.watching_guilds.append(target.id)

        await self._update_config()
        return await ctx.send(embed=discord.Embed(color=self.bot.main_color,
                                                  description=f"Guild has been {'added' if target.id in self.watching_guilds else 'removed'}"))


def setup(bot):
    bot.add_cog(Guildmemberwatch(bot))
