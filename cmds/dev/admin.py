from discord.ext import commands
import asyncio
import io
import sys
import traceback
import subprocess
import textwrap
from contextlib import redirect_stdout
from typing import Optional, Union
import discord
import os
import copy

from config import OWNER_ID, DEV_IDS, BOT_PREFIX, BOT_NAME, BOT_VERSION

class Admin(commands.Cog):
    """Admin-only commands for managing bot functionality."""

    def __init__(self, bot):
        self.bot = bot
        # Combine OWNER_ID and DEV_IDS into one list for checking allowed users
        self.allowed_user_ids = [OWNER_ID] + DEV_IDS

    async def cog_check(self, ctx: commands.Context) -> bool:
        """Check if the user is the allowed user (by user ID)."""
        return ctx.author.id in self.allowed_user_ids

    async def run_process(self, command: str) -> list[str]:
        """Runs a shell command asynchronously and returns output."""
        process = await asyncio.create_subprocess_shell(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = await process.communicate()
        return [stdout.decode(), stderr.decode()]

    def cleanup_code(self, content: str) -> str:
        """Cleans up code for evaluation."""
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])
        return content.strip('` \n')

    @commands.command(hidden=True)
    async def load(self, ctx: commands.Context, *, module: str):
        """Loads a cog/module."""
        try:
            await self.bot.load_extension(module)
            await ctx.send(f"{BOT_PREFIX}load: Module loaded successfully!")
        except Exception as e:
            await ctx.send(f"{BOT_PREFIX}load: Failed to load module: {e}")

    @commands.command(hidden=True)
    async def unload(self, ctx: commands.Context, *, module: str):
        """Unloads a cog/module."""
        try:
            await self.bot.unload_extension(module)
            await ctx.send(f"{BOT_PREFIX}unload: Module unloaded successfully!")
        except Exception as e:
            await ctx.send(f"{BOT_PREFIX}unload: Failed to unload module: {e}")

    @commands.command(hidden=True)
    async def eval(self, ctx: commands.Context, *, body: str):
        """Evaluates Python code."""
        env = {
            'bot': self.bot,
            'ctx': ctx,
            '_': None,
        }
        body = self.cleanup_code(body)
        stdout = io.StringIO()

        to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'
        try:
            exec(to_compile, env)
        except Exception as e:
            return await ctx.send(f"{BOT_PREFIX}eval: Error: {e}")

        func = env['func']
        try:
            with redirect_stdout(stdout):
                result = await func()
        except Exception as e:
            value = stdout.getvalue()
            await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
        else:
            value = stdout.getvalue()
            if result is None:
                if value:
                    await ctx.send(f'```py\n{value}\n```')
            else:
                await ctx.send(f'```py\n{value}{result}\n```')

    @commands.command(hidden=True)
    async def sh(self, ctx: commands.Context, *, command: str):
        """Runs a shell command and sends the output."""
        async with ctx.typing():
            stdout, stderr = await self.run_process(command)
        if stderr:
            await ctx.send(f"{BOT_PREFIX}sh: Error: {stderr}")
        else:
            await ctx.send(stdout)

    @commands.command(hidden=True)
    async def sudo(self, ctx: commands.Context, channel: Optional[discord.TextChannel], who: Union[discord.Member, discord.User], *, command: str):
        """Run a command as another user."""
        msg = copy.copy(ctx.message)
        msg.channel = channel or ctx.channel
        msg.author = who
        msg.content = ctx.prefix + command
        new_ctx = await self.bot.get_context(msg, cls=type(ctx))
        await self.bot.invoke(new_ctx)

    @commands.command(hidden=True)
    async def restart(self, ctx: commands.Context):
        """Restarts the bot."""
        if ctx.author.id in self.allowed_user_ids:  # Check if the user is in the allowed list
            await ctx.send(f"{BOT_PREFIX}restart: Restarting the bot...")
            await self.bot.close()  # Close the bot (this will stop it)
            os.execv(sys.executable, ['python'] + sys.argv)  # Restart the bot by running the same command used to start it

    @commands.command(hidden=True)
    async def reload_all(self, ctx: commands.Context):
        """Reload all modules."""
        if ctx.author.id in self.allowed_user_ids:  # Check if the user is in the allowed list
            for filename in os.listdir('./cmds'):
                if filename.endswith('.py'):
                    module = f'cmds.{filename[:-3]}'
                    try:
                        await self.bot.reload_extension(module)
                        await ctx.send(f"{BOT_PREFIX}reload_all: Reloaded {module} successfully!")
                    except Exception as e:
                        await ctx.send(f"{BOT_PREFIX}reload_all: Failed to reload {module}: {e}")

    @commands.command(hidden=True)
    async def reload(self, ctx: commands.Context, *, module: str):
        """Reload a specific module."""
        try:
            await self.bot.reload_extension(module)
            await ctx.send(f"{BOT_PREFIX}reload: Reloaded {module} successfully!")
        except Exception as e:
            await ctx.send(f"{BOT_PREFIX}reload: Failed to reload module: {e}")

    @commands.group(name='adminhelp', invoke_without_command=True)
    async def admin_help_group(self, ctx: commands.Context):
         """Base help command for displaying available admin commands."""
         if ctx.author.id in self.allowed_user_ids:  # Check if the user is in the allowed list
            embed = discord.Embed(
            title="Admin Commands Help",
            description="List of available admin commands. These are available only to the bot owner and developers.",
            color=discord.Color.green()
            )
            embed.add_field(name="🧑‍💻 " + f"{BOT_PREFIX}eval <code>", value="Executes Python code (useful for testing code snippets).", inline=False)
            embed.add_field(name="🖥️ " + f"{BOT_PREFIX}sh <command>", value="Runs a shell command and sends the output.", inline=False)
            embed.add_field(name="👤 " + f"{BOT_PREFIX}sudo <channel> <user> <command>", value="Run a command as another user.", inline=False)
            embed.add_field(name="🔄 " + f"{BOT_PREFIX}restart", value="Restarts the bot.", inline=False)
            embed.add_field(name="🔄 " + f"{BOT_PREFIX}reload_all", value="Reloads all modules (cmds).", inline=False)
            embed.add_field(name="🔄 " + f"{BOT_PREFIX}reload <module>", value="Reloads a specific module.", inline=False)
            embed.add_field(name="📦 " + f"{BOT_PREFIX}load <module>", value="Loads a specified cog/module.", inline=False)
            embed.add_field(name="🗑️ " + f"{BOT_PREFIX}unload <module>", value="Unloads a specified cog/module.", inline=False)

            embed.set_footer(
                text=f"{BOT_NAME} - Beta v{BOT_VERSION} - Developed by {self.bot.get_user(OWNER_ID).name}"
            )

            try:
                await ctx.author.send(embed=embed)  # Attempt to send as a DM
            except discord.errors.Forbidden:
                pass  # Handle if the bot cannot DM the member

                await ctx.message.delete()  # Deletes the command message for a cleaner experience

        # Only delete the command if it's in a server (not in a DM)
            if ctx.guild:
                try:
                    await ctx.message.delete()  # Deletes the command message for a cleaner experience
                except discord.errors.Forbidden:
                    pass  # Ignore the error if the bot can't delete messages

    @admin_help_group.command(name='admin')
    async def help_admin(self, ctx: commands.Context):
        """Help message for the admin commands."""
        if ctx.author.id in self.allowed_user_ids:  # Check if the user is in the allowed list
            await self.admin_help_group(ctx)

async def setup(bot):
    await bot.add_cog(Admin(bot))
