import asyncio

import discord
from discord.ext import commands

from core import checks, utils
from core.models import PermissionLevel


class logviewer2companion(commands.Cog):
    """
    Companion plugin for https://github.com/hackerjef/logviewer2
    """

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.plugin_db.get_partition(self)

        # settings
        self.enabled = True
        self.allow_evidence_share = False
        self.allowed_users: list = list()
        asyncio.create_task(self._set_options())

    async def _update_config(self):
        await self.db.find_one_and_update(
            {"_id": "config"},
            {
                "$set": {
                    "enabled": self.enabled,
                    "allow_evidence_share": self.allow_evidence_share,
                    "allowed_users": self.allowed_users,
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
        self.allow_evidence_share = config.get("allow_evidence_share", False)
        self.allowed_users = config.get("allowed_users", [])

    @commands.group(name="l2c", invoke_without_command=True)
    @checks.has_permissions(PermissionLevel.OWNER)
    async def l2c(self, ctx):
        """
            Oauth replacement for hackerjef/logviewer2 for self-hosting && multi modmail instance setup (Not required)
            Please support the patron for kyb3r Thanks! <3
        """
        await ctx.send_help(ctx.command)

    @commands.group(name="oauth2", invoke_without_command=True)
    @checks.has_permissions(PermissionLevel.OWNER)
    async def oauth2(self, ctx):
        """
            Oauth replacement for hackerjef/logviewer2 for self-hosting && multi modmail instance setup (Not required)
            Please support the patron for kyb3r Thanks! <3
        """
        await ctx.send_help(ctx.command)

    @l2c.command(name="evidenceshare")
    @checks.has_permissions(PermissionLevel.OWNER)
    async def l2c_evidenceshare(self, ctx):
        """Disable/enables user of shareable thread links (evidence) without internal messages

        Usage: `l2c evidenceshare`
        """

        self.allow_evidence_share = not self.allow_evidence_share
        await self._update_config()
        embed = discord.Embed(color=self.bot.main_color)
        embed.description = "Evidence share has been " + ("enabled" if self.allow_evidence_share else "disabled")
        return await ctx.send(embed=embed)

    @commands.command(aliases=['eloglink'])
    #@l2c.command(name="eloglink")
    @checks.has_permissions(PermissionLevel.SUPPORTER)
    @checks.thread_only()
    async def l2c_loglink(self, ctx):
        log = await self.bot.api.get_log(ctx.channel.id)
        embed = discord.Embed(color=self.bot.main_color)
        embed.description = f"{self.bot.config['log_url'].strip('/')}/evidence/{self.bot.modmail_guild.id}/{log['key']}"
        return await ctx.send(embed=embed)

    @oauth2.command(name="toggle")
    @checks.has_permissions(PermissionLevel.OWNER)
    async def oauth_enable(self, ctx):
        """Disable or enable the oauth system.

        Usage: `oauth2 toggle`
        """

        self.enabled = not self.enabled
        await self._update_config()
        embed = discord.Embed(color=self.bot.main_color)
        embed.description = "Oauth has been " + ("enabled" if self.enabled else "disabled")
        return await ctx.send(embed=embed)

    @oauth2.command(name="allowed")
    @checks.has_permissions(PermissionLevel.SUPPORTER)
    async def oauth_allowed_users(self, ctx):
        """Shows who is allowed to view oauth protected logs

        Usage: `oauth2 allowed`
        """
        embed = discord.Embed(color=self.bot.main_color)
        embed.title = "Allowed users:"
        description = []
        for uid in self.allowed_users:
            user = self.bot.get_user(uid)
            description.append(f"{str(user)} - `{user.id}`")
        embed.description = "\n".join(description)
        return await ctx.send(embed=embed)

    @oauth2.command(name="user")
    @checks.has_permissions(PermissionLevel.OWNER)
    async def oauth_user(self, ctx, mode: str, user: utils.User):
        """Gives permissions on who can/cannot see oauth protected logs and checks status on users

        Usage: `oauth2 (add, remove, info) <userID>`
        """

        embed = discord.Embed(color=self.bot.main_color)

        if mode == "add" or mode == "set":
            self.allowed_users.append(user.id)
            await self._update_config()
            embed.description = f"User {str(user)} ({user.id}) has been added"
            return await ctx.send(embed=embed)
        elif mode == "remove" or mode == "rmv":
            self.allowed_users.remove(user.id)
            await self._update_config()
            embed.description = f"User {str(user)} ({user.id}) has been removed"
            return await ctx.send(embed=embed)
        elif mode == "status" or mode == "info":
            verbage = "has" if user.id in self.allowed_users else "doesn't have"
            embed.description = f"User {str(user)} ({user.id}) {verbage} access to oauth logs"
            return await ctx.send(embed=embed)
        else:
            raise commands.BadArgument("Invalid usage, allowed options `add, remove status`")


def setup(bot):
    bot.add_cog(logviewer2companion(bot))
