import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import random

CURRENCY = "🪙"
DAILY_AMOUNT = 500
WORK_MIN = 50
WORK_MAX = 300
WORK_COOLDOWN_HOURS = 1
DAILY_COOLDOWN_HOURS = 24

WORK_MESSAGES = [
    "You washed dishes at the casino kitchen",
    "You dealt cards as a croupier",
    "You cleaned up after a high-roller party",
    "You drove a whale to the airport",
    "You fixed the slot machines",
    "You managed the valet parking",
    "You worked security at the VIP lounge",
    "You shined shoes in the lobby",
    "You replenished chips at the cashier",
    "You mopped up someone's tears after a bad streak",
]

def coin(n: int) -> str:
    return f"{CURRENCY} **{n:,}**"

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    # ── /balance ───────────────────────────────────────────────
    @app_commands.command(name="balance", description="Check your or someone else's balance")
    @app_commands.describe(user="The user to check (leave blank for yourself)")
    async def balance(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        data = self.db.get_user(target.id, target.display_name)

        debts_owed = self.db.get_debts_owed_by(target.id)
        total_debt = sum(d["amount"] for d in debts_owed)

        embed = discord.Embed(
            title=f"💰 {target.display_name}'s Wallet",
            color=0xF4C430
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Balance",      value=coin(data["balance"]),          inline=True)
        embed.add_field(name="Total Won",    value=coin(data["total_won"]),         inline=True)
        embed.add_field(name="Total Lost",   value=coin(data["total_lost"]),        inline=True)
        embed.add_field(name="Games Played", value=f"🎮 **{data['games_played']:,}**", inline=True)

        net = data["total_won"] - data["total_lost"]
        net_str = f"📈 +{net:,}" if net >= 0 else f"📉 {net:,}"
        embed.add_field(name="Net P/L", value=f"{CURRENCY} **{net_str}**", inline=True)

        if total_debt > 0:
            can_pay = "✅ Đủ tiền trả" if data["balance"] >= total_debt else "⚠️ **Không đủ tiền trả nợ!**"
            embed.add_field(
                name="⚠️ Outstanding Debt",
                value=f"{coin(total_debt)} across {len(debts_owed)} loan(s)\n{can_pay}",
                inline=False
            )
        embed.set_footer(text="Casino Royale • Economy")
        await interaction.response.send_message(embed=embed)

    # ── /daily ─────────────────────────────────────────────────
    @app_commands.command(name="daily", description=f"Claim your daily {DAILY_AMOUNT} coins")
    async def daily(self, interaction: discord.Interaction):
        data = self.db.get_user(interaction.user.id, interaction.user.display_name)
        now = datetime.utcnow()

        if data["last_daily"]:
            last = datetime.fromisoformat(data["last_daily"])
            diff = now - last
            if diff < timedelta(hours=DAILY_COOLDOWN_HOURS):
                remaining = timedelta(hours=DAILY_COOLDOWN_HOURS) - diff
                h, m = divmod(int(remaining.total_seconds()), 3600)
                m //= 60
                return await interaction.response.send_message(
                    f"⏰ Come back in **{h}h {m}m** for your next daily!",
                    ephemeral=True, delete_after=6
                )

        self.db.update_balance(interaction.user.id, DAILY_AMOUNT)
        self.db.set_last_daily(interaction.user.id, now.isoformat())
        self.db.log_transaction(interaction.user.id, DAILY_AMOUNT, "daily", "Daily claim")

        new_bal = self.db.get_user(interaction.user.id)["balance"]
        embed = discord.Embed(
            title="🎁 Daily Reward Claimed!",
            description=f"You received {coin(DAILY_AMOUNT)}!\nNew balance: {coin(new_bal)}",
            color=0x2ECC71
        )
        await interaction.response.send_message(embed=embed)

    # ── /work ──────────────────────────────────────────────────
    @app_commands.command(name="work", description="Work a shift at the casino for coins")
    async def work(self, interaction: discord.Interaction):
        data = self.db.get_user(interaction.user.id, interaction.user.display_name)
        now = datetime.utcnow()

        if data["last_work"]:
            last = datetime.fromisoformat(data["last_work"])
            diff = now - last
            if diff < timedelta(hours=WORK_COOLDOWN_HOURS):
                remaining = timedelta(hours=WORK_COOLDOWN_HOURS) - diff
                m = int(remaining.total_seconds() // 60)
                return await interaction.response.send_message(
                    f"😓 Rest for **{m} more minute(s)**.",
                    ephemeral=True, delete_after=6
                )

        earned = random.randint(WORK_MIN, WORK_MAX)
        msg = random.choice(WORK_MESSAGES)
        self.db.update_balance(interaction.user.id, earned)
        self.db.set_last_work(interaction.user.id, now.isoformat())
        self.db.log_transaction(interaction.user.id, earned, "work", msg)

        new_bal = self.db.get_user(interaction.user.id)["balance"]
        embed = discord.Embed(
            title="💼 Shift Complete!",
            description=f"*{msg}*\n\nEarned: {coin(earned)}\nBalance: {coin(new_bal)}",
            color=0x3498DB
        )
        await interaction.response.send_message(embed=embed)

    # ── /transfer ──────────────────────────────────────────────
    @app_commands.command(name="transfer", description="Send coins to another player")
    @app_commands.describe(user="Who to send to", amount="Amount to send")
    async def transfer(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if user.id == interaction.user.id:
            return await interaction.response.send_message(
                "❌ Can't send to yourself!", ephemeral=True, delete_after=5)
        if amount <= 0:
            return await interaction.response.send_message(
                "❌ Amount must be positive!", ephemeral=True, delete_after=5)

        sender = self.db.get_user(interaction.user.id, interaction.user.display_name)
        if sender["balance"] < amount:
            return await interaction.response.send_message(
                f"❌ You only have {coin(sender['balance'])}.", ephemeral=True, delete_after=5)

        self.db.update_balance(interaction.user.id, -amount)
        self.db.update_balance(user.id, amount)
        self.db.get_user(user.id, user.display_name)
        self.db.log_transaction(interaction.user.id, -amount, "transfer_out", f"Sent to {user.display_name}")
        self.db.log_transaction(user.id, amount, "transfer_in", f"From {interaction.user.display_name}")

        embed = discord.Embed(
            title="💸 Transfer Complete",
            description=f"{interaction.user.mention} → {user.mention}\n\n{coin(amount)} transferred!",
            color=0x9B59B6
        )
        await interaction.response.send_message(embed=embed)

    # ── /lend ──────────────────────────────────────────────────
    @app_commands.command(name="lend", description="Lend coins to a friend — recorded as debt")
    @app_commands.describe(user="Who to lend to", amount="Amount to lend")
    async def lend(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if user.id == interaction.user.id:
            return await interaction.response.send_message(
                "❌ Can't lend to yourself!", ephemeral=True, delete_after=5)
        if amount <= 0:
            return await interaction.response.send_message(
                "❌ Amount must be positive!", ephemeral=True, delete_after=5)

        lender = self.db.get_user(interaction.user.id, interaction.user.display_name)
        if lender["balance"] < amount:
            return await interaction.response.send_message(
                f"❌ You only have {coin(lender['balance'])}!", ephemeral=True, delete_after=5)

        self.db.get_user(user.id, user.display_name)
        self.db.update_balance(interaction.user.id, -amount)
        self.db.update_balance(user.id, amount)
        debt_id = self.db.add_debt(interaction.user.id, user.id, amount)
        self.db.log_transaction(interaction.user.id, -amount, "lend", f"Lent to {user.display_name}")
        self.db.log_transaction(user.id, amount, "borrowed", f"Borrowed from {interaction.user.display_name}")

        embed = discord.Embed(title="🤝 Loan Created", color=0xE67E22)
        embed.add_field(name="Lender",   value=interaction.user.mention, inline=True)
        embed.add_field(name="Borrower", value=user.mention,             inline=True)
        embed.add_field(name="Amount",   value=coin(amount),             inline=True)
        embed.add_field(name="Debt ID",  value=f"`#{debt_id}`",          inline=True)
        embed.add_field(
            name="📋 Hướng dẫn",
            value=(
                f"**Con nợ:** `/paydebt {debt_id}` — tự trả\n"
                f"**Chủ nợ:** `/forcerepay {debt_id}` — thu nợ ngay\n"
                f"**Chủ nợ:** `/forgivedebt {debt_id}` — tha nợ"
            ),
            inline=False
        )
        await interaction.response.send_message(embed=embed)

    # ── /paydebt ───────────────────────────────────────────────
    @app_commands.command(name="paydebt", description="Tự trả một khoản nợ theo ID")
    @app_commands.describe(debt_id="ID khoản nợ (xem /debts)")
    async def paydebt(self, interaction: discord.Interaction, debt_id: int):
        debt = self.db.get_debt_by_id(debt_id)
        if not debt:
            return await interaction.response.send_message("❌ Debt not found!", ephemeral=True, delete_after=5)
        if debt["paid"]:
            return await interaction.response.send_message("✅ Already paid!", ephemeral=True, delete_after=5)
        if debt["borrower_id"] != interaction.user.id:
            return await interaction.response.send_message("❌ That's not your debt!", ephemeral=True, delete_after=5)

        borrower = self.db.get_user(interaction.user.id, interaction.user.display_name)
        amount = debt["amount"]
        if borrower["balance"] < amount:
            return await interaction.response.send_message(
                f"❌ Need {coin(amount)}, only have {coin(borrower['balance'])}!",
                ephemeral=True, delete_after=5)

        self.db.update_balance(interaction.user.id, -amount)
        self.db.update_balance(debt["lender_id"], amount)
        self.db.pay_debt(debt_id)
        self.db.log_transaction(interaction.user.id, -amount, "debt_paid", f"Repaid #{debt_id}")

        lender = await self.bot.fetch_user(debt["lender_id"])
        embed = discord.Embed(
            title="✅ Debt Repaid!",
            description=f"{interaction.user.mention} repaid {coin(amount)} to {lender.mention}",
            color=0x2ECC71
        )
        embed.set_footer(text=f"Debt #{debt_id} cleared")
        await interaction.response.send_message(embed=embed)

    # ── /forcerepay — CHỦ NỢ thu tiền ngay ───────────────────
    @app_commands.command(name="forcerepay", description="💀 Thu nợ ngay lập tức (chỉ chủ nợ dùng được)")
    @app_commands.describe(debt_id="ID khoản nợ muốn thu")
    async def forcerepay(self, interaction: discord.Interaction, debt_id: int):
        debt = self.db.get_debt_by_id(debt_id)
        if not debt:
            return await interaction.response.send_message("❌ Không tìm thấy khoản nợ!", ephemeral=True, delete_after=5)
        if debt["paid"]:
            return await interaction.response.send_message("✅ Khoản nợ đã trả rồi!", ephemeral=True, delete_after=5)
        if debt["lender_id"] != interaction.user.id:
            return await interaction.response.send_message(
                "❌ Bạn không phải chủ nợ khoản này!", ephemeral=True, delete_after=5)

        amount   = debt["amount"]
        borrower = self.db.get_user(debt["borrower_id"])
        cur_bal  = borrower["balance"]

        if cur_bal <= 0:
            # Không có tiền — thu 0, ghi nhận
            self.db.pay_debt(debt_id)
            self.db.log_transaction(debt["borrower_id"], 0, "force_collect_broke",
                                    f"Bị thu nợ #{debt_id} — không có tiền")
            borrower_user = await self.bot.fetch_user(debt["borrower_id"])
            embed = discord.Embed(
                title="💸 Con Nợ Trắng Tay!",
                color=0x95A5A6
            )
            embed.add_field(name="Con nợ",  value=borrower_user.mention, inline=True)
            embed.add_field(name="Nợ gốc",  value=coin(amount),          inline=True)
            embed.add_field(name="Thu được", value=coin(0),              inline=True)
            embed.add_field(
                name="⚠️",
                value=f"{borrower_user.mention} **không có đồng nào** — nợ được xoá nhưng bạn mất trắng!",
                inline=False
            )
            embed.set_footer(text=f"Debt #{debt_id} closed (unpaid)")
            return await interaction.response.send_message(embed=embed)

        # Có tiền — thu bao nhiêu có bấy nhiêu
        collected = min(cur_bal, amount)
        shortage  = amount - collected

        self.db.update_balance(debt["borrower_id"], -collected)
        self.db.update_balance(interaction.user.id, collected)
        self.db.pay_debt(debt_id)
        self.db.log_transaction(debt["borrower_id"], -collected, "force_collected",
                                f"Bị thu nợ #{debt_id}")
        self.db.log_transaction(interaction.user.id, collected, "force_collect",
                                f"Thu nợ #{debt_id}")

        borrower_user = await self.bot.fetch_user(debt["borrower_id"])
        new_bal = self.db.get_user(debt["borrower_id"])["balance"]

        if shortage > 0:
            color = 0xE67E22
            title = "⚠️ Thu Nợ Một Phần"
            extra = f"\n**Còn thiếu:** {coin(shortage)} — con nợ không đủ tiền!"
        else:
            color = 0xE74C3C
            title = "💀 Thu Nợ Thành Công!"
            extra = ""

        embed = discord.Embed(title=title, color=color)
        embed.add_field(name="Con nợ",         value=borrower_user.mention, inline=True)
        embed.add_field(name="Nợ gốc",         value=coin(amount),          inline=True)
        embed.add_field(name="Thu được",        value=coin(collected),       inline=True)
        embed.add_field(name="Số dư con nợ",   value=coin(new_bal),         inline=True)
        if extra:
            embed.add_field(name="📋 Ghi chú", value=extra, inline=False)
        embed.set_footer(text=f"Debt #{debt_id} settled — forced by lender")
        await interaction.response.send_message(embed=embed)

    # ── /forgivedebt — Chủ nợ tha nợ ─────────────────────────
    @app_commands.command(name="forgivedebt", description="🕊️ Tha nợ cho người vay (chủ nợ dùng)")
    @app_commands.describe(debt_id="ID khoản nợ muốn tha")
    async def forgivedebt(self, interaction: discord.Interaction, debt_id: int):
        debt = self.db.get_debt_by_id(debt_id)
        if not debt:
            return await interaction.response.send_message("❌ Không tìm thấy khoản nợ!", ephemeral=True, delete_after=5)
        if debt["paid"]:
            return await interaction.response.send_message("✅ Khoản nợ đã trả rồi!", ephemeral=True, delete_after=5)
        if debt["lender_id"] != interaction.user.id:
            return await interaction.response.send_message(
                "❌ Bạn không phải chủ nợ khoản này!", ephemeral=True, delete_after=5)

        self.db.pay_debt(debt_id)
        self.db.log_transaction(debt["borrower_id"], debt["amount"], "debt_forgiven",
                                f"Được tha nợ #{debt_id}")
        borrower_user = await self.bot.fetch_user(debt["borrower_id"])

        embed = discord.Embed(
            title="🕊️ Nợ Đã Được Tha!",
            description=f"{interaction.user.mention} đã tha {coin(debt['amount'])} cho {borrower_user.mention}",
            color=0x2ECC71
        )
        embed.set_footer(text=f"Debt #{debt_id} forgiven")
        await interaction.response.send_message(embed=embed)

    # ── /debts ─────────────────────────────────────────────────
    @app_commands.command(name="debts", description="View all outstanding debts involving you")
    async def debts(self, interaction: discord.Interaction):
        self.db.get_user(interaction.user.id, interaction.user.display_name)
        owed_to_me = self.db.get_debts_owed_to(interaction.user.id)
        i_owe      = self.db.get_debts_owed_by(interaction.user.id)

        embed = discord.Embed(title="📋 Debt Ledger", color=0xE74C3C)

        if owed_to_me:
            lines = []
            for d in owed_to_me:
                try:
                    borrower = await self.bot.fetch_user(d["borrower_id"])
                    name = borrower.display_name
                except:
                    name = f"User {d['borrower_id']}"
                cur_bal  = self.db.get_user(d["borrower_id"])["balance"]
                status   = "✅ Đủ tiền" if cur_bal >= d["amount"] else f"⚠️ Chỉ có {cur_bal:,}"
                lines.append(
                    f"• **{name}** — {coin(d['amount'])} `(#{d['id']})` {status}\n"
                    f"  `/forcerepay {d['id']}` thu  |  `/forgivedebt {d['id']}` tha"
                )
            embed.add_field(name="💵 Người Nợ Bạn", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="💵 Người Nợ Bạn", value="*Không có ai nợ bạn*", inline=False)

        if i_owe:
            lines = []
            for d in i_owe:
                try:
                    lender = await self.bot.fetch_user(d["lender_id"])
                    name = lender.display_name
                except:
                    name = f"User {d['lender_id']}"
                lines.append(
                    f"• Bạn nợ **{name}** — {coin(d['amount'])} `(#{d['id']})` — `/paydebt {d['id']}`"
                )
            embed.add_field(name="💸 Bạn Đang Nợ", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="💸 Bạn Đang Nợ", value="*Bạn không nợ ai!* 🎉", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /leaderboard ───────────────────────────────────────────
    @app_commands.command(name="leaderboard", description="Top 10 richest players")
    async def leaderboard(self, interaction: discord.Interaction):
        rows = self.db.get_leaderboard(10)
        medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
        embed = discord.Embed(title="🏆 Casino Leaderboard", color=0xF4C430)
        lines = []
        for i, row in enumerate(rows):
            try:
                u = await self.bot.fetch_user(row["user_id"])
                name = u.display_name
            except:
                name = row["username"] or f"User {row['user_id']}"
            debts = self.db.get_debts_owed_by(row["user_id"])
            debt_tag = ""
            if debts:
                total = sum(d["amount"] for d in debts)
                debt_tag = f" *(⚠️ nợ {total:,})*"
            lines.append(f"{medals[i]} **{name}** — {coin(row['balance'])}{debt_tag}")
        embed.description = "\n".join(lines) if lines else "*No players yet!*"
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Economy(bot))
