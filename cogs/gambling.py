import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio

CURRENCY = "🪙"

def coin(n: int) -> str:
    return f"{CURRENCY} **{n:,}**"

def clamp_bet(bet: int, balance: int):
    if bet <= 0:
        return "❌ Bet must be positive!"
    if bet > balance:
        return f"❌ You only have {coin(balance)}!"
    return None

# ════════════════════════════════════════════════
#  SLOT MACHINE
# ════════════════════════════════════════════════
SLOTS = ["🍒", "🍋", "🍊", "🍇", "⭐", "💎", "7️⃣"]
SLOT_WEIGHTS = [30, 25, 20, 15, 6, 3, 1]

SLOT_PAYOUTS = {
    ("7️⃣", "7️⃣", "7️⃣"): 50,
    ("💎", "💎", "💎"): 20,
    ("⭐", "⭐", "⭐"): 10,
    ("🍇", "🍇", "🍇"): 5,
    ("🍊", "🍊", "🍊"): 4,
    ("🍋", "🍋", "🍋"): 3,
    ("🍒", "🍒", "🍒"): 2,
}

def spin_slots():
    return random.choices(SLOTS, weights=SLOT_WEIGHTS, k=3)

def get_slot_payout(reels, bet):
    key = tuple(reels)
    if key in SLOT_PAYOUTS:
        mult = SLOT_PAYOUTS[key]
        return bet * mult, f"🎊 **JACKPOT! {mult}x multiplier!**"
    if reels[0] == reels[1] or reels[1] == reels[2]:
        return int(bet * 0.5), "🎯 Two of a kind — **0.5x** back"
    return 0, "😢 No match!"

def slot_embed(r1, r2, r3, bet, spinning=False, result_msg=None, net=None, bal=None):
    if spinning:
        color, title = 0xF4C430, "🎰  S P I N N I N G . . ."
    elif net is not None and net >= 0:
        color, title = 0x2ECC71, "🎰  Y O U  W I N !"
    else:
        color, title = 0xE74C3C, "🎰  N O  L U C K"

    embed = discord.Embed(title=title, color=color)
    embed.add_field(
        name="\u200b",
        value=f"┌─────────────────┐\n│  {r1}  ║  {r2}  ║  {r3}  │\n└─────────────────┘",
        inline=False
    )
    if result_msg:
        embed.add_field(name="Result", value=result_msg, inline=False)
    if net is not None:
        net_str = f"+{net:,}" if net >= 0 else f"{net:,}"
        embed.add_field(name="Net", value=f"{CURRENCY} **{net_str}**", inline=True)
    if bal is not None:
        embed.add_field(name="Balance", value=coin(bal), inline=True)
    embed.add_field(
        name="📊 Payouts",
        value="`7️⃣×3`=**50x** | `💎×3`=**20x** | `⭐×3`=**10x** | 2-match=**0.5x**",
        inline=False
    )
    return embed


# ════════════════════════════════════════════════
#  BLACKJACK
# ════════════════════════════════════════════════
SUITS = ["♠️", "♥️", "♦️", "♣️"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
CARD_FLIP_FRAMES = ["🂠", "🀫", "🎴", "🃏"]

def make_deck():
    return [f"{r}{s}" for s in SUITS for r in RANKS]

def card_value(card):
    rank = card[:-2] if card[:-1].endswith(("♠", "♥", "♦", "♣")) else card[:-1]
    # strip suit emoji (2 chars) to get rank
    for s in ["♠️", "♥️", "♦️", "♣️"]:
        if card.endswith(s):
            rank = card[:-len(s)]
            break
    if rank in ["J", "Q", "K"]: return 10
    if rank == "A": return 11
    try: return int(rank)
    except: return 10

def hand_value(hand):
    total = sum(card_value(c) for c in hand)
    aces = sum(1 for c in hand if c.startswith("A"))
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

def fmt_card(card):
    return f"`{card}`"

def fmt_hand(hand):
    return "  ".join(fmt_card(c) for c in hand)

def bj_embed(player_hand, dealer_hand, bet, reveal=False, result=None, net=None, bal=None, status="playing"):
    pv = hand_value(player_hand)
    dv = hand_value(dealer_hand)
    colors = {"playing": 0x2C3E50, "win": 0x2ECC71, "lose": 0xE74C3C,
              "push": 0x95A5A6, "blackjack": 0xF4C430, "flip": 0x3498DB}
    titles = {"playing": "🃏  B L A C K J A C K", "win": "🃏  Y O U  W I N !",
              "lose": "🃏  D E A L E R  W I N S", "push": "🃏  P U S H",
              "blackjack": "🃏  B L A C K J A C K !  🎊", "flip": "🃏  D E A L E R  D R A W I N G . . ."}

    embed = discord.Embed(title=titles.get(status, "🃏 Blackjack"), color=colors.get(status, 0x2C3E50))
    embed.add_field(name=f"👤 Your Hand  [{pv}]", value=fmt_hand(player_hand), inline=False)
    if reveal:
        embed.add_field(name=f"🏦 Dealer's Hand  [{dv}]", value=fmt_hand(dealer_hand), inline=False)
    else:
        embed.add_field(name="🏦 Dealer's Hand  [?]", value=f"{fmt_card(dealer_hand[0])}  🂠", inline=False)
    embed.add_field(name="\u200b", value="─────────────────", inline=False)
    if result:
        embed.add_field(name="📢 Result", value=result, inline=False)
    if net is not None:
        net_str = f"+{net:,}" if net >= 0 else f"{net:,}"
        embed.add_field(name="Net", value=f"{CURRENCY} **{net_str}**", inline=True)
    if bal is not None:
        embed.add_field(name="Balance", value=coin(bal), inline=True)
    embed.set_footer(text=f"Bet: {bet:,} {CURRENCY}  •  Dealer stands on 17")
    return embed


class BlackjackView(discord.ui.View):
    def __init__(self, bot, interaction, bet, player_hand, dealer_hand, deck):
        super().__init__(timeout=120)
        self.bot = bot
        self.db = bot.db
        self.bet = bet
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.deck = deck
        self.user_id = interaction.user.id
        self.message = None

    async def flip_and_draw(self, msg):
        """Animate card flip then dealer drawing"""
        for frame in CARD_FLIP_FRAMES:
            embed = discord.Embed(title="🃏  D E A L E R  R E V E A L I N G . . .", color=0x3498DB)
            embed.add_field(name=f"👤 Your Hand [{hand_value(self.player_hand)}]", value=fmt_hand(self.player_hand), inline=False)
            embed.add_field(name="🏦 Dealer Reveals...", value=f"{fmt_card(self.dealer_hand[0])}  {frame}", inline=False)
            embed.set_footer(text=f"Bet: {self.bet:,} {CURRENCY}")
            await msg.edit(embed=embed, view=self)
            await asyncio.sleep(0.35)

        while hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())
            embed = bj_embed(self.player_hand, self.dealer_hand, self.bet, reveal=True, status="flip")
            await msg.edit(embed=embed, view=self)
            await asyncio.sleep(0.6)

    async def resolve(self, msg):
        pv = hand_value(self.player_hand)
        dv = hand_value(self.dealer_hand)
        if pv > 21:
            status, result, net = "lose", "💥 **Bust!** Over 21!", -self.bet
        elif len(self.player_hand) == 2 and pv == 21:
            status, result, net = "blackjack", "🎊 **Blackjack!** Natural 21!", int(self.bet * 1.5)
        elif dv > 21:
            status, result, net = "win", "💥 **Dealer busts!** You win!", self.bet
        elif pv > dv:
            status, result, net = "win", f"✅ **{pv} vs {dv}** — You win!", self.bet
        elif pv == dv:
            status, result, net = "push", f"🤝 **Push!** Both {pv}. Bet returned.", 0
        else:
            status, result, net = "lose", f"❌ **{dv} vs {pv}** — Dealer wins.", -self.bet

        self.db.update_balance(self.user_id, net)
        if net > 0: self.db.record_game(self.user_id, net, 0)
        elif net < 0: self.db.record_game(self.user_id, 0, abs(net))
        bal = self.db.get_user(self.user_id)["balance"]

        for child in self.children: child.disabled = True
        self.stop()
        await msg.edit(
            embed=bj_embed(self.player_hand, self.dealer_hand, self.bet,
                reveal=True, result=result, net=net, bal=bal, status=status),
            view=self
        )

    @discord.ui.button(label="  Hit  ", style=discord.ButtonStyle.success, emoji="👊")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("Not your game!", ephemeral=True)
        await interaction.response.defer()
        msg = await interaction.original_response()

        # Card flip animation before drawing
        for frame in CARD_FLIP_FRAMES:
            embed = bj_embed(self.player_hand, self.dealer_hand, self.bet)
            embed.add_field(name="Drawing card...", value=frame, inline=False)
            await msg.edit(embed=embed, view=self)
            await asyncio.sleep(0.22)

        self.player_hand.append(self.deck.pop())
        pv = hand_value(self.player_hand)

        if pv > 21:
            await self.resolve(msg)
        elif pv == 21:
            embed = bj_embed(self.player_hand, self.dealer_hand, self.bet)
            embed.add_field(name="🎯", value="**21! Auto-standing...**", inline=False)
            await msg.edit(embed=embed, view=self)
            await asyncio.sleep(1)
            await self.flip_and_draw(msg)
            await self.resolve(msg)
        else:
            await msg.edit(embed=bj_embed(self.player_hand, self.dealer_hand, self.bet), view=self)

    @discord.ui.button(label=" Stand ", style=discord.ButtonStyle.danger, emoji="✋")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("Not your game!", ephemeral=True)
        await interaction.response.defer()
        msg = await interaction.original_response()
        await self.flip_and_draw(msg)
        await self.resolve(msg)

    @discord.ui.button(label="Double Down", style=discord.ButtonStyle.primary, emoji="💰")
    async def double_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("Not your game!", ephemeral=True)
        if len(self.player_hand) != 2:
            return await interaction.response.send_message("❌ Only on first two cards!", ephemeral=True)
        bal = self.db.get_user(self.user_id)["balance"]
        if bal < self.bet:
            return await interaction.response.send_message("❌ Not enough to double down!", ephemeral=True)

        await interaction.response.defer()
        msg = await interaction.original_response()
        self.bet *= 2

        for frame in CARD_FLIP_FRAMES:
            embed = bj_embed(self.player_hand, self.dealer_hand, self.bet)
            embed.add_field(name="💰 Doubling Down...", value=frame, inline=False)
            await msg.edit(embed=embed, view=self)
            await asyncio.sleep(0.22)

        self.player_hand.append(self.deck.pop())
        await msg.edit(embed=bj_embed(self.player_hand, self.dealer_hand, self.bet), view=self)
        await asyncio.sleep(0.8)
        await self.flip_and_draw(msg)
        await self.resolve(msg)

    async def on_timeout(self):
        for child in self.children: child.disabled = True
        if self.message:
            try: await self.message.edit(view=self)
            except: pass


# ════════════════════════════════════════════════
#  ROULETTE HELPERS
# ════════════════════════════════════════════════
RED_NUMS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
BLACK_NUMS = set(range(1, 37)) - RED_NUMS
ROULETTE_FRAMES = ["🌀", "💫", "🔄", "⏩", "🎡"]


class Gambling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    # ── /slots ─────────────────────────────────────────────
    @app_commands.command(name="slots", description="🎰 Spin the slot machine!")
    @app_commands.describe(bet="Amount to bet")
    async def slots(self, interaction: discord.Interaction, bet: int):
        data = self.db.get_user(interaction.user.id, interaction.user.display_name)
        err = clamp_bet(bet, data["balance"])
        if err:
            return await interaction.response.send_message(err, ephemeral=True)

        await interaction.response.send_message(embed=slot_embed("🎰", "🎰", "🎰", bet, spinning=True))
        msg = await interaction.original_response()

        final = spin_slots()

        # Animate each reel stopping one by one
        for reel_idx in range(3):
            for _ in range(8):
                current = list(final[:reel_idx]) + [random.choice(SLOTS)] + ["🎰"] * (2 - reel_idx)
                await msg.edit(embed=slot_embed(*current, bet, spinning=True))
                await asyncio.sleep(0.1)
            # Lock this reel in
            current = list(final[:reel_idx + 1]) + ["🎰"] * (2 - reel_idx)
            await msg.edit(embed=slot_embed(*current, bet, spinning=(reel_idx < 2)))
            await asyncio.sleep(0.35)

        winnings, result_msg = get_slot_payout(final, bet)
        net = winnings - bet
        self.db.update_balance(interaction.user.id, net)
        if net > 0: self.db.record_game(interaction.user.id, net, 0)
        else: self.db.record_game(interaction.user.id, 0, abs(net))
        bal = self.db.get_user(interaction.user.id)["balance"]

        # Flash animation on win
        if net > 0:
            for _ in range(3):
                await msg.edit(embed=slot_embed(*final, bet, result_msg="✨ ✨ ✨", net=net, bal=bal))
                await asyncio.sleep(0.25)
                await msg.edit(embed=slot_embed(*final, bet, result_msg=result_msg, net=net, bal=bal))
                await asyncio.sleep(0.25)

        await msg.edit(embed=slot_embed(*final, bet, result_msg=result_msg, net=net, bal=bal))

    # ── /coinflip ──────────────────────────────────────────
    @app_commands.command(name="coinflip", description="🪙 Flip a coin — heads or tails?")
    @app_commands.describe(bet="Amount to bet", choice="heads or tails")
    @app_commands.choices(choice=[
        app_commands.Choice(name="Heads 🌕", value="heads"),
        app_commands.Choice(name="Tails 🌑", value="tails"),
    ])
    async def coinflip(self, interaction: discord.Interaction, bet: int, choice: str):
        data = self.db.get_user(interaction.user.id, interaction.user.display_name)
        err = clamp_bet(bet, data["balance"])
        if err:
            return await interaction.response.send_message(err, ephemeral=True)

        COIN_FRAMES = ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘"]

        embed = discord.Embed(title="🪙  F L I P P I N G . . .", color=0xF4C430)
        embed.add_field(name="You chose", value=f"**{choice.capitalize()}**", inline=True)
        embed.add_field(name="Spinning", value=COIN_FRAMES[0], inline=True)
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()

        # Coin spin — speeds up then slows down
        frames = COIN_FRAMES * 4
        for i, frame in enumerate(frames):
            delay = 0.06 + (i / len(frames)) * 0.12  # slow down over time
            embed = discord.Embed(title="🪙  F L I P P I N G . . .", color=0xF4C430)
            embed.add_field(name="You chose", value=f"**{choice.capitalize()}**", inline=True)
            embed.add_field(name="Spinning", value=frame, inline=True)
            await msg.edit(embed=embed)
            await asyncio.sleep(delay)

        result = random.choice(["heads", "tails"])
        won = result == choice
        net = bet if won else -bet
        self.db.update_balance(interaction.user.id, net)
        if won: self.db.record_game(interaction.user.id, net, 0)
        else: self.db.record_game(interaction.user.id, 0, abs(net))
        bal = self.db.get_user(interaction.user.id)["balance"]

        result_emoji = "🌕" if result == "heads" else "🌑"
        color = 0x2ECC71 if won else 0xE74C3C
        net_str = f"+{net:,}" if net >= 0 else f"{net:,}"

        await asyncio.sleep(0.3)
        embed = discord.Embed(
            title=f"{'🎉  Y O U  W I N !' if won else '💀  Y O U  L O S E'}",
            color=color
        )
        embed.add_field(name="You chose", value=f"**{choice.capitalize()}**", inline=True)
        embed.add_field(name="Result", value=f"{result_emoji} **{result.capitalize()}**", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="Net", value=f"{CURRENCY} **{net_str}**", inline=True)
        embed.add_field(name="Balance", value=coin(bal), inline=True)
        await msg.edit(embed=embed)

    # ── /blackjack ─────────────────────────────────────────
    @app_commands.command(name="blackjack", description="🃏 Play blackjack vs the dealer")
    @app_commands.describe(bet="Amount to bet")
    async def blackjack(self, interaction: discord.Interaction, bet: int):
        data = self.db.get_user(interaction.user.id, interaction.user.display_name)
        err = clamp_bet(bet, data["balance"])
        if err:
            return await interaction.response.send_message(err, ephemeral=True)

        # Deal animation
        embed = discord.Embed(title="🃏  S H U F F L I N G . . .", color=0x2C3E50)
        embed.add_field(name="Preparing deck", value="🂠 🂠 🂠 🂠 🂠", inline=False)
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        await asyncio.sleep(0.6)

        deck = make_deck()
        random.shuffle(deck)
        player, dealer = [], []

        # Deal cards one by one with animation
        for i in range(4):
            if i % 2 == 0:
                player.append(deck.pop())
            else:
                dealer.append(deck.pop())

            deal_embed = discord.Embed(title="🃏  D E A L I N G . . .", color=0x2C3E50)
            deal_embed.add_field(
                name=f"👤 Your Hand [{hand_value(player)}]",
                value=fmt_hand(player) if player else "🂠",
                inline=False
            )
            deal_embed.add_field(
                name="🏦 Dealer's Hand [?]",
                value=(fmt_hand(dealer) + "  🂠") if len(dealer) == 1 else fmt_hand(dealer[:1]) + "  🂠" if dealer else "🂠",
                inline=False
            )
            deal_embed.set_footer(text=f"Bet: {bet:,} {CURRENCY}")
            await msg.edit(embed=deal_embed)
            await asyncio.sleep(0.4)

        view = BlackjackView(self.bot, interaction, bet, player, dealer, deck)
        view.message = msg

        # Instant blackjack
        if hand_value(player) == 21:
            while hand_value(dealer) < 17:
                dealer.append(deck.pop())
            net = int(bet * 1.5)
            view.db.update_balance(interaction.user.id, net)
            view.db.record_game(interaction.user.id, net, 0)
            bal = view.db.get_user(interaction.user.id)["balance"]
            for child in view.children: child.disabled = True
            view.stop()
            await msg.edit(
                embed=bj_embed(player, dealer, bet, reveal=True,
                    result="🎊 **Blackjack! Natural 21!**", net=net, bal=bal, status="blackjack"),
                view=view
            )
            return

        await msg.edit(embed=bj_embed(player, dealer, bet, status="playing"), view=view)

    # ── /dice ──────────────────────────────────────────────
    @app_commands.command(name="dice", description="🎲 Roll the dice!")
    @app_commands.describe(bet="Amount to bet", pick="Your prediction")
    @app_commands.choices(pick=[
        app_commands.Choice(name="Over 7 (2x)", value="over"),
        app_commands.Choice(name="Under 7 (2x)", value="under"),
        app_commands.Choice(name="Exactly 7 (5x!)", value="seven"),
    ])
    async def dice(self, interaction: discord.Interaction, bet: int, pick: str):
        data = self.db.get_user(interaction.user.id, interaction.user.display_name)
        err = clamp_bet(bet, data["balance"])
        if err:
            return await interaction.response.send_message(err, ephemeral=True)

        dice_faces = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]

        embed = discord.Embed(title="🎲  R O L L I N G . . .", color=0xF4C430)
        embed.add_field(name="Your Bet", value=f"**{pick.capitalize()}**", inline=True)
        embed.add_field(name="Dice", value="🎲  🎲", inline=True)
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()

        # Roll animation — slows down
        for i in range(16):
            f1, f2 = random.choice(dice_faces), random.choice(dice_faces)
            embed = discord.Embed(title="🎲  R O L L I N G . . .", color=0xF4C430)
            embed.add_field(name="Your Bet", value=f"**{pick.capitalize()}**", inline=True)
            embed.add_field(name="Rolling...", value=f"{f1}  {f2}", inline=True)
            await msg.edit(embed=embed)
            await asyncio.sleep(0.06 + i * 0.018)

        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        total = d1 + d2
        f1, f2 = dice_faces[d1 - 1], dice_faces[d2 - 1]

        if pick == "over": won, mult = total > 7, 2
        elif pick == "under": won, mult = total < 7, 2
        else: won, mult = total == 7, 5

        net = (bet * mult - bet) if won else -bet
        self.db.update_balance(interaction.user.id, net)
        if net > 0: self.db.record_game(interaction.user.id, net, 0)
        else: self.db.record_game(interaction.user.id, 0, abs(net))
        bal = self.db.get_user(interaction.user.id)["balance"]

        color = 0x2ECC71 if won else 0xE74C3C
        net_str = f"+{net:,}" if net >= 0 else f"{net:,}"
        await asyncio.sleep(0.3)
        embed = discord.Embed(title=f"🎲  {'Y O U  W I N !' if won else 'Y O U  L O S E'}", color=color)
        embed.add_field(name="Result", value=f"{f1} + {f2} = **{total}**", inline=False)
        embed.add_field(name="You picked", value=f"**{pick.capitalize()}**", inline=True)
        embed.add_field(name="Net", value=f"{CURRENCY} **{net_str}**", inline=True)
        embed.add_field(name="Balance", value=coin(bal), inline=True)
        await msg.edit(embed=embed)

    # ── /roulette ──────────────────────────────────────────
    @app_commands.command(name="roulette", description="🎡 Spin the roulette wheel!")
    @app_commands.describe(bet="Amount to bet", bet_on="red/black/green/odd/even/low/high or a number 0-36")
    async def roulette(self, interaction: discord.Interaction, bet: int, bet_on: str):
        data = self.db.get_user(interaction.user.id, interaction.user.display_name)
        err = clamp_bet(bet, data["balance"])
        if err:
            return await interaction.response.send_message(err, ephemeral=True)

        bl = bet_on.lower()
        valid = ["red", "black", "green", "odd", "even", "low", "high"]
        if bl not in valid and not (bl.isdigit() and 0 <= int(bl) <= 36):
            return await interaction.response.send_message(
                "❌ Valid bets: `red` `black` `green` `odd` `even` `low` `high` or a number `0-36`",
                ephemeral=True
            )

        embed = discord.Embed(title="🎡  S P I N N I N G . . .", color=0xF4C430)
        embed.add_field(name="Your Bet", value=f"**{bet_on.capitalize()}**", inline=True)
        embed.add_field(name="Wheel", value=ROULETTE_FRAMES[0], inline=True)
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()

        # Spinning animation — slows to a stop
        for i in range(20):
            num = random.randint(0, 36)
            nc = "🔴" if num in RED_NUMS else ("⚫" if num in BLACK_NUMS else "🟢")
            frame = ROULETTE_FRAMES[i % len(ROULETTE_FRAMES)]
            embed = discord.Embed(title="🎡  S P I N N I N G . . .", color=0xF4C430)
            embed.add_field(name="Your Bet", value=f"**{bet_on.capitalize()}**", inline=True)
            embed.add_field(name=frame, value=f"{nc} **{num}**", inline=True)
            await msg.edit(embed=embed)
            await asyncio.sleep(0.07 + i * 0.015)

        number = random.randint(0, 36)
        nc = "🔴" if number in RED_NUMS else ("⚫" if number in BLACK_NUMS else "🟢")

        if bl == "red": won, mult = number in RED_NUMS, 2
        elif bl == "black": won, mult = number in BLACK_NUMS, 2
        elif bl == "green": won, mult = number == 0, 14
        elif bl == "odd": won, mult = number != 0 and number % 2 == 1, 2
        elif bl == "even": won, mult = number != 0 and number % 2 == 0, 2
        elif bl == "high": won, mult = 19 <= number <= 36, 2
        elif bl == "low": won, mult = 1 <= number <= 18, 2
        else: won, mult = int(bl) == number, 35

        net = (bet * mult - bet) if won else -bet
        self.db.update_balance(interaction.user.id, net)
        if net > 0: self.db.record_game(interaction.user.id, net, 0)
        else: self.db.record_game(interaction.user.id, 0, abs(net))
        bal = self.db.get_user(interaction.user.id)["balance"]

        color = 0x2ECC71 if won else 0xE74C3C
        net_str = f"+{net:,}" if net >= 0 else f"{net:,}"
        await asyncio.sleep(0.4)
        embed = discord.Embed(title=f"🎡  {'W I N N E R !' if won else 'N O  L U C K'}", color=color)
        embed.add_field(name="Ball Landed", value=f"{nc} **{number}**", inline=False)
        embed.add_field(name="Your Bet", value=f"**{bet_on.capitalize()}**", inline=True)
        embed.add_field(name="Net", value=f"{CURRENCY} **{net_str}**", inline=True)
        embed.add_field(name="Balance", value=coin(bal), inline=True)
        embed.set_footer(text="red/black/odd/even/low/high=2x | number=35x | green=14x")
        await msg.edit(embed=embed)

    # ── /crash ─────────────────────────────────────────────
    @app_commands.command(name="crash", description="🚀 Set your cash-out and watch it climb!")
    @app_commands.describe(bet="Amount to bet", cashout="Auto cash-out multiplier (e.g. 2.5)")
    async def crash(self, interaction: discord.Interaction, bet: int, cashout: float):
        data = self.db.get_user(interaction.user.id, interaction.user.display_name)
        err = clamp_bet(bet, data["balance"])
        if err:
            return await interaction.response.send_message(err, ephemeral=True)
        if cashout < 1.01:
            return await interaction.response.send_message("❌ Cashout must be ≥ 1.01x", ephemeral=True)

        r = random.random()
        crash_at = round(max(1.01, 0.99 / r), 2)

        embed = discord.Embed(title="🚀  L A U N C H I N G . . .", color=0x3498DB)
        embed.add_field(name="Bet", value=coin(bet), inline=True)
        embed.add_field(name="Auto Cash-Out", value=f"**{cashout}x**", inline=True)
        embed.add_field(name="Multiplier", value="**1.00x** 🚀", inline=False)
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()

        rockets = ["🚀", "🛸", "💫", "🌟", "⭐"]
        mult = 1.0
        step = 0.08
        cashed_out = False

        while round(mult, 2) < crash_at:
            mult = round(mult + step, 2)
            if mult >= cashout:
                cashed_out = True
                break

            pct = min(mult / max(crash_at, cashout + 1), 1.0)
            bar = "█" * int(pct * 12) + "░" * (12 - int(pct * 12))
            rocket = rockets[int(mult * 2) % len(rockets)]
            color = 0x2ECC71 if mult < cashout * 0.85 else 0xF4C430

            embed = discord.Embed(title=f"🚀  {mult:.2f}x  —  C L I M B I N G !", color=color)
            embed.add_field(name="Progress", value=f"`{bar}` **{mult:.2f}x**", inline=False)
            embed.add_field(name="Bet", value=coin(bet), inline=True)
            embed.add_field(name="Target", value=f"**{cashout}x** {rocket}", inline=True)
            await msg.edit(embed=embed)
            await asyncio.sleep(max(0.04, 0.25 - mult * 0.015))
            step = min(step + 0.015, 0.4)

        won = cashed_out
        net = int(bet * cashout - bet) if won else -bet
        self.db.update_balance(interaction.user.id, net)
        if net > 0: self.db.record_game(interaction.user.id, net, 0)
        else: self.db.record_game(interaction.user.id, 0, abs(net))
        bal = self.db.get_user(interaction.user.id)["balance"]

        net_str = f"+{net:,}" if net >= 0 else f"{net:,}"
        color = 0x2ECC71 if won else 0xE74C3C
        title = f"✅  C A S H E D  O U T  @  {cashout}x !" if won else f"💥  C R A S H E D  @  {crash_at}x !"
        desc = f"Got out in time! Crashed at **{crash_at}x**" if won else f"Set {cashout}x — crashed before that!"

        embed = discord.Embed(title=title, description=desc, color=color)
        embed.add_field(name="Net", value=f"{CURRENCY} **{net_str}**", inline=True)
        embed.add_field(name="Balance", value=coin(bal), inline=True)
        await msg.edit(embed=embed)


async def setup(bot):
    await bot.add_cog(Gambling(bot))