import asyncio
from typing import Union

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
        self.allowed_roles: dict = dict()
        asyncio.create_task(self._set_options())

    async def _update_config(self):
        await self.db.find_one_and_update(
            {"_id": "config"},
            {
                "$set": {
                    "enabled": self.enabled,
                    "allow_evidence_share": self.allow_evidence_share,
                    "allowed_users": self.allowed_users,
                    "allowed_roles": self.allowed_roles,
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
        self.allowed_roles = config.get("allowed_roles", [])

    async def update_roles(self):
        g = self.bot.modmail_guild
        if not g:
            return

        for role in self.allowed_roles:
            grole = g.get_role(role)
            if grole:
                members = []
                for member in grole.members:
                    members.append(member.id)
                self.allowed_roles = members
            else:
                del self.allowed_roles[role]

        await self._update_config()

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

    # note: Cannot make this a l2c and a root command at the same time, though i could just make another function, ez
    @commands.command(aliases=['eloglink'])
    @checks.has_permissions(PermissionLevel.SUPPORTER)
    @checks.thread_only()
    async def l2c_loglink(self, ctx):
        """Get evidence based loglink if enabled :)

        Usage: `eloglink`
        """
        if not self.allow_evidence_share:
            embed = discord.Embed(color=self.bot.error_color)
            embed.description = "Cannot get evidence loglink, Please enabled it (<p>l2c evidenceshare)"
            return await ctx.send(embed=embed)

        log = await self.bot.api.get_log(ctx.channel.id)
        embed = discord.Embed(color=self.bot.main_color)
        embed.description = f"{self.bot.config['log_url'].strip('/')}/evidence/{self.bot.modmail_guild.id}/{log['key']}"
        return await ctx.send(embed=embed)

    @l2c.command(name="eloglink")
    @checks.has_permissions(PermissionLevel.SUPPORTER)
    @checks.thread_only()
    async def l2c_loglink(self, ctx):
        """Get evidence based loglink if enabled :)

        Usage: `l2c eloglink`
        """
        return await self.l2c_loglink(ctx)

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
        users = []
        for uid in self.allowed_users:
            user = self.bot.get_user(uid)
            users.append(uid)
            description.append(f"{str(user)} - `{user.id}`")

        for rid in self.allowed_roles:
            for uid in self.allowed_roles[rid]:
                if uid not in users:
                    user = self.bot.get_user(uid)
                    users.append(uid)
                    description.append(f"{str(user)} - `{user.id}` - role: {rid}")
        embed.description = "\n".join(description)

        return await ctx.send(embed=embed)

    @oauth2.command(name="whitelist")
    @checks.has_permissions(PermissionLevel.OWNER)
    async def oauth_user(self, ctx, mode: str, target: Union[discord.Role, utils.User]):
        """Gives permissions on who can/cannot see oauth protected logs and checks status on users

        Usage: `oauth2 whitelist (add, remove, info) <userID>`
        """

        embed = discord.Embed(color=self.bot.main_color)

        # yes was taken from core/utilitys but it works :)
        if not hasattr(target, "mention"):
            target = self.bot.get_user(target.id) or self.bot.modmail_guild.get_role(target.id)

        if mode == "add" or mode == "set":
            if isinstance(target, discord.Role):
                self.allowed_roles[target.id] = []
            else:
                self.allowed_users.append(target.id)

        elif mode == "remove" or mode == "rmv":
            if isinstance(target, discord.Role):
                del self.allowed_roles[target.id]
            else:
                self.allowed_users.remove(target.id)

        elif mode == "status" or mode == "info":
            if isinstance(target, discord.Role):
                verbage = "has" if target.id in self.allowed_roles else "doesn't have"
            else:
                verbage = "has" if target.id in self.allowed_users else "doesn't have"

            embed.description = f"{target.mention} ({target.id}) {verbage} access to oauth logs"
        else:
            raise commands.BadArgument("Invalid usage, allowed options `add, remove status`")

        if mode in ["add", "set", "remove", "rmv"]:
            await self._update_config()
            asyncio.create_task(self.update_roles())
            embed.description = f"{target.mention} ({target.id}) has been edited"

        return await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(logviewer2companion(bot))
