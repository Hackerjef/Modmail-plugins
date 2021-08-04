import asyncio

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
    async def oauth(self, ctx):
        """
            Oauth replacement with hackerjef/logviewer for self-hosting && multi modmail instance setup (Not required)
            PLEASE SUPPORT KYB3R AND IF U CAN DO WITHOUT SELF HOSTING, DONT USE THIS PLUGIN - THANK YOU!
        """
        await ctx.send_help(ctx.command)

    @oauth.command(name="status")
    @checks.has_permissions(PermissionLevel.OWNER)
    async def oauth_enable(self, ctx, mode: bool = False):
        """Disable or enable the oauth system.

        Usage: `oauth status enable` / `auth status disable`
        """
        self.enabled = mode
        await self._update_config()
        await ctx.send(("Enabled" if mode else "Disabled") + " oauth.")

    @oauth.command(name="user")
    @checks.has_permissions(PermissionLevel.OWNER)
    async def oauth_user(self, ctx, user: utils.User, allowed: bool):
        if not hasattr(user, "id"):
            raise commands.BadArgument(f'User "{user}" not found')

        if allowed:
            self.allowed_users.append(user.id)
        else:
            self.allowed_users.remove(user.id)

        await self._update_config()
        await ctx.send(f"{'allowed' if allowed else 'disallowed'} {str(user)} ({user.id}) oauth permission")


def setup(bot):
    print("Removing stock oauth command, remove by uninstalling logviewer2companion plugin")
    bot.remove_command('oauth')  # Remove built in usage of oauth before load
    bot.add_cog(logviewer2companion(bot))
