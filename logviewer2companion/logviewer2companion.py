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
        self.allowed_users: list = list()
        asyncio.create_task(self._set_options())

    async def _update_config(self):
        await self.db.find_one_and_update(
            {"_id": "config"},
            {
                "$set": {
                    "enabled": self.enabled,
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
        self.allowed_users = config.get("allowed_users", [])

    @commands.group(invoke_without_command=True)
    @checks.has_permissions(PermissionLevel.OWNER)
    async def oauth2(self, ctx):
        """
            Oauth replacement for hackerjef/logviewer2 for self-hosting && multi modmail instance setup (Not required)
            Please support the patron for kyb3r Thanks! <3
        """
        await ctx.send_help(ctx.command)

    @oauth2.command(name="enable")
    @checks.has_permissions(PermissionLevel.OWNER)
    async def oauth_enable(self, ctx):
        """Disable or enable the oauth system.

        Usage: `oauth enable` / `auth enable`
        """

        self.enabled = not self.enabled
        await self._update_config()
        await ctx.send(("Enabled" if self.enabled else "Disabled") + " oauth.")

    @oauth2.command(name="user")
    @checks.has_permissions(PermissionLevel.OWNER)
    async def oauth_user(self, ctx, mode: str, user: utils.User):
        if not hasattr(user, "id"):
            raise commands.BadArgument(f'User "{user}" not found')

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
    print("Removing stock oauth command, remove by uninstalling logviewer2companion plugin")
    bot.add_cog(logviewer2companion(bot))
