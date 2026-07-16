import discord
from discord import app_commands
from discord.ext import commands
from utils.permissions import is_watched_channel

class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="List all available slash commands and their descriptions")
    @is_watched_channel()
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="All Bot Commands",
            description=(
                "**`/register`** — Register LeetCode & CodeForces handles\n\n"
                "**`/profile`** — View progress, badges & profile card\n\n"
                "**`/submit`** — Submit daily DSA progress\n\n"
                "**`/status`** — Check submission status for a day\n\n"
                "**`/edit_submission`** — Edit a past submission description\n\n"
                "**`/delete_submission`** — Delete a past submission\n\n"
                "**`/sync_badges`** — Sync and award milestone badges\n\n"
                "**`/upcoming`** — Show upcoming CP contests in the next 1 week"
            ),
            color=discord.Color.teal()
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
