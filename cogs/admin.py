import discord
from discord.ext import commands
from discord import app_commands

CURRENCY = "🪙"

def coin(n: int) -> str:
    return f"{CURRENCY} **{n:,}**"

def is_owner(interaction: discord.Interaction) -> bool:
    return interaction.user.id == interaction.client.OWNER_ID

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    # ── /setmoney — OWNER ONLY ─────────────────────────────
    @app_commands.command(name="setmoney", description="[OWNER] Set your balance to any amount")
    @app_commands.describe(amount="Amount to set your balance to")
    async def setmoney(self, interaction: discord.Interaction, amount: int):
        if not is_owner(interaction):
            return await interaction.response.send_message(
                "❌ This command is reserved for the casino owner.", ephemeral=True
            )
        if amount < 0:
            return await interaction.response.send_message("❌ Amount can't be negative!", ephemeral=True)

        self.db.get_user(interaction.user.id, interaction.user.display_name)
        self.db.set_balance(interaction.user.id, amount)
        self.db.log_transaction(interaction.user.id, amount, "admin_set", "Owner set balance")

        embed = discord.Embed(
            title="💰 Balance Set",
            description=f"Your balance is now {coin(amount)}",
            color=0xF4C430
        )
        embed.set_footer(text="👑 Owner command")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /addmoney — OWNER ONLY ─────────────────────────────
    @app_commands.command(name="addmoney", description="[OWNER] Add coins to any player's balance")
    @app_commands.describe(user="Target user", amount="Amount to add (use negative to subtract)")
    async def addmoney(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if not is_owner(interaction):
            return await interaction.response.send_message(
                "❌ This command is reserved for the casino owner.", ephemeral=True
            )

        self.db.get_user(user.id, user.display_name)
        new_bal = self.db.update_balance(user.id, amount)
        self.db.log_transaction(user.id, amount, "admin_add", f"Admin gave by owner")

        action = "added to" if amount >= 0 else "removed from"
        embed = discord.Embed(
            title="🛠️ Balance Updated",
            description=f"{coin(abs(amount))} {action} **{user.display_name}**\nNew balance: {coin(new_bal)}",
            color=0x3498DB
        )
        embed.set_footer(text="👑 Owner command")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /resetuser — OWNER ONLY ────────────────────────────
    @app_commands.command(name="resetuser", description="[OWNER] Reset a player's balance to 1000")
    @app_commands.describe(user="The user to reset")
    async def resetuser(self, interaction: discord.Interaction, user: discord.Member):
        if not is_owner(interaction):
            return await interaction.response.send_message(
                "❌ This command is reserved for the casino owner.", ephemeral=True
            )

        self.db.get_user(user.id, user.display_name)
        self.db.set_balance(user.id, 1000)
        self.db.log_transaction(user.id, 1000, "admin_reset", "Owner reset balance")

        embed = discord.Embed(
            title="🔄 User Reset",
            description=f"**{user.display_name}** has been reset to {coin(1000)}",
            color=0xE74C3C
        )
        embed.set_footer(text="👑 Owner command")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /canceldebt — OWNER ONLY ───────────────────────────
    @app_commands.command(name="canceldebt", description="[OWNER] Cancel/forgive a debt by ID")
    @app_commands.describe(debt_id="The debt ID to cancel")
    async def canceldebt(self, interaction: discord.Interaction, debt_id: int):
        if not is_owner(interaction):
            return await interaction.response.send_message(
                "❌ This command is reserved for the casino owner.", ephemeral=True
            )

        debt = self.db.get_debt_by_id(debt_id)
        if not debt:
            return await interaction.response.send_message("❌ Debt not found!", ephemeral=True)
        if debt["paid"]:
            return await interaction.response.send_message("✅ Debt already paid!", ephemeral=True)

        self.db.pay_debt(debt_id)
        embed = discord.Embed(
            title="🗑️ Debt Cancelled",
            description=f"Debt `#{debt_id}` of {coin(debt['amount'])} has been forgiven.",
            color=0x2ECC71
        )
        embed.set_footer(text="👑 Owner command")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /help ──────────────────────────────────────────────
    @app_commands.command(name="help", description="Show all available commands")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎰 Casino Royale — Command Guide",
            description="All amounts are in 🪙 coins. Starting balance: **1,000**",
            color=0xF4C430
        )

        embed.add_field(
            name="💰 Economy",
            value=(
                "`/balance [user]` — Check wallet\n"
                "`/daily` — Claim 500 coins (24h cooldown)\n"
                "`/work` — Earn 50-300 coins (1h cooldown)\n"
                "`/transfer <user> <amount>` — Send coins\n"
                "`/leaderboard` — Top 10 richest"
            ),
            inline=False
        )

        embed.add_field(
            name="🤝 Loans & Debt",
            value=(
                "`/lend <user> <amount>` — Lend money (recorded as debt)\n"
                "`/paydebt <id>` — Repay a debt\n"
                "`/debts` — View all your debts"
            ),
            inline=False
        )

        embed.add_field(
            name="🎮 Games",
            value=(
                "`/slots <bet>` — Slot machine\n"
                "`/coinflip <bet> <heads/tails>` — 50/50\n"
                "`/blackjack <bet>` — vs the dealer\n"
                "`/dice <bet> <over/under/seven>` — Dice roll\n"
                "`/roulette <bet> <red/black/odd/even/low/high/0-36>` — Roulette\n"
                "`/crash <bet> <cashout>` — Crash game"
            ),
            inline=False
        )

        if is_owner(interaction):
            embed.add_field(
                name="👑 Owner Only",
                value=(
                    "`/setmoney <amount>` — Set YOUR balance to any amount\n"
                    "`/addmoney <user> <amount>` — Give/remove coins from anyone\n"
                    "`/resetuser <user>` — Reset a player to 1,000\n"
                    "`/canceldebt <id>` — Forgive any debt"
                ),
                inline=False
            )

        embed.set_footer(text="Good luck, and gamble responsibly 🎲")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Admin(bot))
