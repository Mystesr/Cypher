import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio

CURRENCY = "🪙"
def coin(n): return f"{CURRENCY} **{n:,}**"
def clamp_bet(bet, balance):
    if bet <= 0: return "❌ Cược phải lớn hơn 0!"
    if bet > balance: return f"❌ Bạn chỉ có {coin(balance)}!"
    return None

# ════════════════════════════════════════════════════════════
#  SHARED DECK UTILS
# ════════════════════════════════════════════════════════════
SUITS     = ["♠", "♣", "♦", "♥"]   # spade < club < diamond < heart
SUIT_EMO  = {"♠": "♠️", "♣": "♣️", "♦": "♦️", "♥": "♥️"}
RANKS     = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"]

def make_deck(n=1):
    d = [f"{r}{s}" for s in SUITS for r in RANKS] * n
    random.shuffle(d)
    return d

def card_rank(card):
    for s in SUITS:
        if card.endswith(s):
            return card[:-len(s)]
    return card[:-1]

def card_suit(card):
    for s in SUITS:
        if card.endswith(s):
            return s
    return card[-1]

def fmt(card):
    r = card_rank(card)
    s = card_suit(card)
    return f"`{r}{SUIT_EMO.get(s,s)}`"

def fmt_hand(hand):
    return "  ".join(fmt(c) for c in hand)

FLIP = ["🂠", "🀫", "🎴", "🃏"]

# ════════════════════════════════════════════════════════════
#  🃏 3 CÂY (BÀI CÀO) — Vietnam Baccarat
#  Each player gets 3 cards. Points = last digit of sum.
#  J/Q/K = 10pts. Special: 3 Tây (J+Q+K) > 3 Đôi > 9 > ... > 0
# ════════════════════════════════════════════════════════════
def ba_cay_value(card):
    r = card_rank(card)
    if r in ["J","Q","K"]: return 10
    if r == "A": return 1
    return int(r)

def ba_cay_score(hand):
    return sum(ba_cay_value(c) for c in hand) % 10

def ba_cay_special(hand):
    ranks = sorted([card_rank(c) for c in hand])
    # 3 Tây: all face cards (J, Q, K)
    if all(r in ["J","Q","K"] for r in ranks):
        return ("3 Tây 👑", 3)
    # 3 Đôi: all same rank
    if ranks[0] == ranks[1] == ranks[2]:
        return ("3 Đôi 🎯", 2)
    return None

def ba_cay_hand_rank(hand):
    sp = ba_cay_special(hand)
    if sp: return (10 + sp[1], sp[0])
    pts = ba_cay_score(hand)
    return (pts, f"**{pts} điểm**")

def ba_cay_tiebreak(h1, h2):
    """Returns True if h1 beats h2 on tiebreak (suit of highest card)"""
    suit_order = {"♠":0,"♣":1,"♦":2,"♥":3}
    def best_suit(hand):
        return max(suit_order.get(card_suit(c),0) for c in hand)
    return best_suit(h1) > best_suit(h2)

class BaCayView(discord.ui.View):
    def __init__(self, bot, interaction, bet, player_hand, dealer_hand):
        super().__init__(timeout=60)
        self.bot = bot
        self.db  = bot.db
        self.bet = bet
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.uid  = interaction.user.id
        self.msg  = None

    @discord.ui.button(label="🃏 Lật bài!", style=discord.ButtonStyle.danger, emoji="👀")
    async def reveal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message("Không phải lượt của bạn!", ephemeral=True)
        await interaction.response.defer()
        msg = await interaction.original_response()

        # Flip animation
        for frame in FLIP:
            e = discord.Embed(title="🃏  L Ậ T  B À I . . .", color=0xF4C430)
            e.add_field(name="Bài của bạn", value=fmt_hand(self.player_hand), inline=False)
            e.add_field(name="Bài nhà cái", value=frame, inline=False)
            await msg.edit(embed=e, view=self)
            await asyncio.sleep(0.35)

        pr, pl = ba_cay_hand_rank(self.player_hand)
        dr, dl = ba_cay_hand_rank(self.dealer_hand)

        if pr > dr:
            won, result = True, f"🎉 Bạn thắng! {pl} vs {dl}"
        elif dr > pr:
            won, result = False, f"😢 Nhà cái thắng! {dl} vs {pl}"
        else:
            # Tiebreak by suit
            if ba_cay_tiebreak(self.player_hand, self.dealer_hand):
                won, result = True, f"🎉 Hòa điểm — bạn thắng theo chất bài!"
            else:
                won, result = False, f"😢 Hòa điểm — nhà cái thắng theo chất bài!"

        net = self.bet if won else -self.bet
        self.db.update_balance(self.uid, net)
        if net > 0: self.db.record_game(self.uid, net, 0)
        else: self.db.record_game(self.uid, 0, abs(net))
        bal = self.db.get_user(self.uid)["balance"]

        net_str = f"+{net:,}" if net >= 0 else f"{net:,}"
        color = 0x2ECC71 if won else 0xE74C3C
        e = discord.Embed(title="🃏  3  C Â Y  —  K Ế T  Q U Ả", color=color)
        e.add_field(name="Bài của bạn", value=fmt_hand(self.player_hand), inline=True)
        e.add_field(name="Bài nhà cái", value=fmt_hand(self.dealer_hand), inline=True)
        e.add_field(name="\u200b", value="\u200b", inline=True)
        e.add_field(name="📢 Kết quả", value=result, inline=False)
        e.add_field(name="Net", value=f"{CURRENCY} **{net_str}**", inline=True)
        e.add_field(name="Số dư", value=coin(bal), inline=True)
        e.set_footer(text="3 Tây👑 > 3 Đôi🎯 > 9 > 8 > ... > 0  |  Hòa → so chất ♥>♦>♣>♠")
        for child in self.children: child.disabled = True
        self.stop()
        await msg.edit(embed=e, view=self)


# ════════════════════════════════════════════════════════════
#  🃏 LIÊNG (Vietnamese 3-card poker / bluffing game)
#  Each player gets 3 cards. Rankings:
#  Sảnh đồng chất > Sảnh (straight) > Thùng (flush)
#  > Ba đôi (three of a kind) > Đôi (pair) > Bài cao
# ════════════════════════════════════════════════════════════
RANK_ORDER = {"3":1,"4":2,"5":3,"6":4,"7":5,"8":6,"9":7,"10":8,"J":9,"Q":10,"K":11,"A":12,"2":13}

def lieng_rank_val(card):
    return RANK_ORDER.get(card_rank(card), 0)

def lieng_hand_type(hand):
    ranks = sorted([lieng_rank_val(c) for c in hand])
    suits = [card_suit(c) for c in hand]
    is_flush = len(set(suits)) == 1
    is_straight = (ranks[2]-ranks[1]==1 and ranks[1]-ranks[0]==1)
    # A-2-3 straight
    if sorted(ranks) == sorted([RANK_ORDER["A"], RANK_ORDER["2"], RANK_ORDER["3"]]):
        is_straight = True
    is_triple = ranks[0]==ranks[1]==ranks[2]
    is_pair   = ranks[0]==ranks[1] or ranks[1]==ranks[2]

    if is_straight and is_flush: return (7, "Sảnh Đồng Chất 🌈")
    if is_triple:                 return (6, "Ba Đôi 🎯")
    if is_straight:               return (5, "Sảnh ➡️")
    if is_flush:                  return (4, "Thùng ♦️")
    if is_pair:                   return (3, "Đôi 👥")
    return (1, f"Bài Cao {fmt(max(hand, key=lieng_rank_val))}")

def lieng_hand_key(hand):
    htype, _ = lieng_hand_type(hand)
    ranks = sorted([lieng_rank_val(c) for c in hand], reverse=True)
    return (htype, *ranks)

class LiengView(discord.ui.View):
    def __init__(self, bot, interaction, bet, player_hand, dealer_hand):
        super().__init__(timeout=90)
        self.bot = bot
        self.db  = bot.db
        self.bet = bet
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.uid = interaction.user.id

    @discord.ui.button(label="  Theo (Call)  ", style=discord.ButtonStyle.success, emoji="✅")
    async def call(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message("Không phải lượt bạn!", ephemeral=True)
        await self._resolve(interaction, folded=False)

    @discord.ui.button(label=" Bỏ (Fold) ", style=discord.ButtonStyle.danger, emoji="🏳️")
    async def fold(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message("Không phải lượt bạn!", ephemeral=True)
        await self._resolve(interaction, folded=True)

    async def _resolve(self, interaction, folded):
        await interaction.response.defer()
        msg = await interaction.original_response()
        for child in self.children: child.disabled = True
        self.stop()

        if folded:
            net = -self.bet
            self.db.update_balance(self.uid, net)
            self.db.record_game(self.uid, 0, self.bet)
            bal = self.db.get_user(self.uid)["balance"]
            e = discord.Embed(title="🏳️  B Ỏ  B À I", color=0x95A5A6)
            e.add_field(name="Bài của bạn", value=fmt_hand(self.player_hand), inline=True)
            e.add_field(name="Bài nhà cái", value=fmt_hand(self.dealer_hand), inline=True)
            e.add_field(name="Net", value=f"{CURRENCY} **{net:,}**", inline=False)
            e.add_field(name="Số dư", value=coin(bal), inline=True)
            return await msg.edit(embed=e, view=self)

        # Flip reveal
        for frame in FLIP:
            e = discord.Embed(title="🃏  S O  B À I . . .", color=0x3498DB)
            e.add_field(name="Bài của bạn", value=fmt_hand(self.player_hand), inline=True)
            e.add_field(name="Nhà cái", value=frame, inline=True)
            await msg.edit(embed=e, view=self)
            await asyncio.sleep(0.35)

        pk = lieng_hand_key(self.player_hand)
        dk = lieng_hand_key(self.dealer_hand)
        _, pname = lieng_hand_type(self.player_hand)
        _, dname = lieng_hand_type(self.dealer_hand)

        if pk > dk:
            won, result = True, f"🎉 Bạn thắng!\n👤 {pname} vs 🏦 {dname}"
        elif dk > pk:
            won, result = False, f"😢 Nhà cái thắng!\n🏦 {dname} vs 👤 {pname}"
        else:
            won, result = False, f"🤝 Hòa — nhà cái giữ tiền!"

        net = self.bet if won else -self.bet
        self.db.update_balance(self.uid, net)
        if net > 0: self.db.record_game(self.uid, net, 0)
        else: self.db.record_game(self.uid, 0, abs(net))
        bal = self.db.get_user(self.uid)["balance"]

        net_str = f"+{net:,}" if net >= 0 else f"{net:,}"
        color = 0x2ECC71 if won else 0xE74C3C
        e = discord.Embed(title="🃏  L I Ê N G  —  K Ế T  Q U Ả", color=color)
        e.add_field(name="Bài của bạn", value=fmt_hand(self.player_hand), inline=True)
        e.add_field(name="Bài nhà cái", value=fmt_hand(self.dealer_hand), inline=True)
        e.add_field(name="\u200b", value="\u200b", inline=True)
        e.add_field(name="📢 Kết quả", value=result, inline=False)
        e.add_field(name="Net", value=f"{CURRENCY} **{net_str}**", inline=True)
        e.add_field(name="Số dư", value=coin(bal), inline=True)
        e.set_footer(text="Sảnh Đồng Chất > Ba Đôi > Sảnh > Thùng > Đôi > Bài Cao")
        await msg.edit(embed=e, view=self)


# ════════════════════════════════════════════════════════════
#  🃏 XÌ DÁCH — Vietnamese Blackjack
#  A + face card = Xì Dách (instant win, 2x)
#  A + A = Xì Bàn (instant win, 3x)
#  Goal: get closest to 21 without going over
# ════════════════════════════════════════════════════════════
def xi_dach_value(card):
    r = card_rank(card)
    if r in ["J","Q","K"]: return 10
    if r == "A": return 11
    return int(r)

def xi_dach_total(hand):
    total = sum(xi_dach_value(c) for c in hand)
    aces = sum(1 for c in hand if card_rank(c) == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

def xi_dach_check(hand):
    """Check for instant win hands"""
    if len(hand) == 2:
        ranks = [card_rank(c) for c in hand]
        if ranks[0] == "A" and ranks[1] == "A":
            return "xi_ban"   # Xì Bàn: 2 Aces
        if ("A" in ranks and any(r in ["J","Q","K","10"] for r in ranks)):
            return "xi_dach"  # Xì Dách: Ace + face/10
    return None

class XiDachView(discord.ui.View):
    def __init__(self, bot, interaction, bet, player, dealer, deck):
        super().__init__(timeout=120)
        self.bot = bot
        self.db  = bot.db
        self.bet = bet
        self.player = player
        self.dealer = dealer
        self.deck   = deck
        self.uid    = interaction.user.id
        self.msg    = None

    def make_embed(self, reveal=False, result=None, net=None, bal=None, status="playing"):
        pv = xi_dach_total(self.player)
        dv = xi_dach_total(self.dealer)
        colors = {"playing":0x1A1A2E,"win":0x2ECC71,"lose":0xE74C3C,"push":0x95A5A6,"xi_dach":0xF4C430,"xi_ban":0xFF6B6B}
        titles = {
            "playing":"🎴  X Ì  D Á C H","win":"🎴  T H Ắ N G !",
            "lose":"🎴  T H U A !","push":"🎴  H Ò A",
            "xi_dach":"🎴  X Ì  D Á C H !  🎊","xi_ban":"🎴  X Ì  B À N !  🔥",
            "flip":"🎴  N H À  C Á I  R Ú T  B À I . . ."
        }
        e = discord.Embed(title=titles.get(status,"🎴 Xì Dách"), color=colors.get(status,0x1A1A2E))
        e.add_field(name=f"👤 Bài bạn  [{pv}]", value=fmt_hand(self.player), inline=False)
        if reveal:
            e.add_field(name=f"🏦 Nhà cái  [{dv}]", value=fmt_hand(self.dealer), inline=False)
        else:
            e.add_field(name="🏦 Nhà cái  [?]", value=f"{fmt(self.dealer[0])}  🂠", inline=False)
        e.add_field(name="\u200b", value="─────────────────", inline=False)
        if result: e.add_field(name="📢 Kết quả", value=result, inline=False)
        if net is not None:
            net_str = f"+{net:,}" if net >= 0 else f"{net:,}"
            e.add_field(name="Net", value=f"{CURRENCY} **{net_str}**", inline=True)
        if bal is not None:
            e.add_field(name="Số dư", value=coin(bal), inline=True)
        e.set_footer(text=f"Cược: {self.bet:,} {CURRENCY}  •  Xì Dách=2x | Xì Bàn=3x | Nhà cái rút đến 16")
        return e

    async def dealer_draw(self, msg):
        for frame in FLIP:
            e = discord.Embed(title="🎴  N H À  C Á I  L Ậ T  B À I . . .", color=0x3498DB)
            e.add_field(name=f"👤 Bài bạn [{xi_dach_total(self.player)}]", value=fmt_hand(self.player), inline=False)
            e.add_field(name="🏦 Nhà cái lật...", value=f"{fmt(self.dealer[0])}  {frame}", inline=False)
            await msg.edit(embed=e, view=self)
            await asyncio.sleep(0.35)
        while xi_dach_total(self.dealer) <= 16:
            self.dealer.append(self.deck.pop())
            await msg.edit(embed=self.make_embed(reveal=True, status="flip"), view=self)
            await asyncio.sleep(0.5)

    async def finish(self, msg, pv=None, dv=None):
        pv = pv or xi_dach_total(self.player)
        dv = dv or xi_dach_total(self.dealer)
        if pv > 21:
            status, result, net = "lose", "💥 **Quá 21! Bạn thua.**", -self.bet
        elif dv > 21:
            status, result, net = "win", "💥 **Nhà cái quá 21! Bạn thắng!**", self.bet
        elif pv > dv:
            status, result, net = "win", f"✅ **{pv} vs {dv} — Bạn thắng!**", self.bet
        elif pv == dv:
            status, result, net = "push", f"🤝 **Hòa {pv} điểm — hoàn cược!**", 0
        else:
            status, result, net = "lose", f"❌ **{dv} vs {pv} — Nhà cái thắng.**", -self.bet

        self.db.update_balance(self.uid, net)
        if net > 0: self.db.record_game(self.uid, net, 0)
        elif net < 0: self.db.record_game(self.uid, 0, abs(net))
        bal = self.db.get_user(self.uid)["balance"]
        for child in self.children: child.disabled = True
        self.stop()
        await msg.edit(embed=self.make_embed(reveal=True, result=result, net=net, bal=bal, status=status), view=self)

    @discord.ui.button(label="  Rút (Hit)  ", style=discord.ButtonStyle.success, emoji="👊")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message("Không phải bạn!", ephemeral=True)
        await interaction.response.defer()
        msg = await interaction.original_response()
        for frame in FLIP:
            e = self.make_embed()
            e.add_field(name="Rút bài...", value=frame, inline=False)
            await msg.edit(embed=e, view=self)
            await asyncio.sleep(0.22)
        self.player.append(self.deck.pop())
        pv = xi_dach_total(self.player)
        if pv >= 21:
            await self.dealer_draw(msg)
            await self.finish(msg)
        else:
            await msg.edit(embed=self.make_embed(), view=self)

    @discord.ui.button(label=" Dừng (Stand) ", style=discord.ButtonStyle.danger, emoji="✋")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message("Không phải bạn!", ephemeral=True)
        await interaction.response.defer()
        msg = await interaction.original_response()
        await self.dealer_draw(msg)
        await self.finish(msg)

    @discord.ui.button(label="Gấp Đôi (Double)", style=discord.ButtonStyle.primary, emoji="💰")
    async def double(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message("Không phải bạn!", ephemeral=True)
        if len(self.player) != 2:
            return await interaction.response.send_message("❌ Chỉ gấp đôi được với 2 lá đầu!", ephemeral=True)
        data = self.db.get_user(self.uid)
        if data["balance"] < self.bet:
            return await interaction.response.send_message("❌ Không đủ tiền để gấp đôi!", ephemeral=True)
        await interaction.response.defer()
        msg = await interaction.original_response()
        self.bet *= 2
        for frame in FLIP:
            e = self.make_embed()
            e.add_field(name="💰 Gấp đôi cược...", value=frame, inline=False)
            await msg.edit(embed=e, view=self)
            await asyncio.sleep(0.22)
        self.player.append(self.deck.pop())
        await msg.edit(embed=self.make_embed(), view=self)
        await asyncio.sleep(0.6)
        await self.dealer_draw(msg)
        await self.finish(msg)

    async def on_timeout(self):
        for child in self.children: child.disabled = True
        if self.msg:
            try: await self.msg.edit(view=self)
            except: pass


# ════════════════════════════════════════════════════════════
#  🎴 TIẾN LÊN (simplified 1v1 vs bot, betting version)
#  Each gets 13 cards. Play higher combos to shed cards.
#  First to empty hand wins. Cards: 3 low → 2 high.
# ════════════════════════════════════════════════════════════
TIEN_LEN_ORDER = {"3":1,"4":2,"5":3,"6":4,"7":5,"8":6,"9":7,"10":8,"J":9,"Q":10,"K":11,"A":12,"2":13}
SUIT_ORDER     = {"♠":1,"♣":2,"♦":3,"♥":4}

def tl_card_key(card):
    return (TIEN_LEN_ORDER.get(card_rank(card),0), SUIT_ORDER.get(card_suit(card),0))

def tl_sort(hand):
    return sorted(hand, key=tl_card_key)

def tl_combo_type(cards):
    if len(cards) == 1: return "single"
    if len(cards) == 2:
        if card_rank(cards[0]) == card_rank(cards[1]): return "pair"
    if len(cards) == 4:
        if len(set(card_rank(c) for c in cards)) == 1: return "four_of_a_kind"
    if len(cards) >= 3:
        # Check sequence
        vals = sorted(set(TIEN_LEN_ORDER.get(card_rank(c)) for c in cards))
        if len(vals) == len(cards) and all(vals[i]+1==vals[i+1] for i in range(len(vals)-1)):
            return "sequence"
        # Check pair sequence
        if len(cards) % 2 == 0:
            pairs = [(cards[i], cards[i+1]) for i in range(0,len(cards),2)]
            if all(card_rank(p[0])==card_rank(p[1]) for p in pairs):
                pvals = sorted(TIEN_LEN_ORDER.get(card_rank(p[0])) for p in pairs)
                if all(pvals[i]+1==pvals[i+1] for i in range(len(pvals)-1)):
                    return "pair_sequence"
    return None

def tl_can_beat(prev, new_combo):
    """Returns True if new_combo beats prev"""
    pt = tl_combo_type(prev)
    nt = tl_combo_type(new_combo)
    if pt != nt: return False
    # Compare by highest card
    prev_key = max(tl_card_key(c) for c in prev)
    new_key  = max(tl_card_key(c) for c in new_combo)
    return new_key > prev_key

def bot_tien_len_move(hand, current_play, combo_type):
    """Simple AI: play lowest valid combo"""
    if combo_type == "single":
        for c in tl_sort(hand):
            if tl_can_beat(current_play, [c]):
                return [c]
    elif combo_type == "pair":
        pairs = []
        by_rank = {}
        for c in hand:
            r = card_rank(c)
            by_rank.setdefault(r,[]).append(c)
        for r, cards in by_rank.items():
            if len(cards) >= 2:
                pairs.append(cards[:2])
        pairs.sort(key=lambda p: tl_card_key(p[0]))
        for p in pairs:
            if tl_can_beat(current_play, p):
                return p
    elif combo_type == "sequence":
        n = len(current_play)
        hand_sorted = tl_sort(hand)
        for i in range(len(hand_sorted)-n+1):
            seq = hand_sorted[i:i+n]
            vals = [TIEN_LEN_ORDER.get(card_rank(c)) for c in seq]
            if all(vals[j]+1==vals[j+1] for j in range(len(vals)-1)):
                if tl_can_beat(current_play, seq):
                    return seq
    return None  # pass

class TienLenView(discord.ui.View):
    def __init__(self, bot, interaction, bet, player_hand, bot_hand):
        super().__init__(timeout=180)
        self.bot = bot
        self.db  = bot.db
        self.bet = bet
        self.player = tl_sort(player_hand)
        self.bot_hand = tl_sort(bot_hand)
        self.uid = interaction.user.id
        self.current_play = None   # cards on table
        self.current_type = None
        self.player_passed = False
        self.msg = None
        self.selecting = []        # cards player is selecting

    def hand_display(self, hand, selectable=False):
        if selectable:
            return " ".join(
                f"[{fmt(c)}]" if c in self.selecting else fmt(c)
                for c in hand
            )
        return fmt_hand(hand)

    def make_embed(self, status="playing", result=None):
        colors = {"playing":0x0D3B66,"win":0x2ECC71,"lose":0xE74C3C}
        e = discord.Embed(title="🀄  T I Ế N  L Ê N  —  1 v 1", color=colors.get(status,0x0D3B66))
        e.add_field(name=f"👤 Bài bạn ({len(self.player)} lá)", value=self.hand_display(self.player) or "*Hết bài!*", inline=False)
        e.add_field(name=f"🤖 Bot ({len(self.bot_hand)} lá)", value=f"🂠 × {len(self.bot_hand)}", inline=False)
        if self.current_play:
            e.add_field(name="🃏 Bài đang đánh", value=fmt_hand(self.current_play), inline=False)
        else:
            e.add_field(name="🃏 Bàn trống", value="*Bạn đánh trước*", inline=False)
        if self.selecting:
            e.add_field(name="✅ Đang chọn", value=fmt_hand(self.selecting), inline=False)
        if result:
            e.add_field(name="📢", value=result, inline=False)
        e.set_footer(text=f"Cược: {self.bet:,} {CURRENCY}  •  Chọn bài rồi nhấn Đánh | Bỏ để pass")
        return e

    @discord.ui.button(label="◀ Chọn lá nhỏ nhất", style=discord.ButtonStyle.secondary, emoji="🃏", row=0)
    async def pick_lowest(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message("Không phải bạn!", ephemeral=True)
        if not self.player:
            return await interaction.response.send_message("Hết bài!", ephemeral=True)
        # Auto-select lowest valid single
        for c in self.player:
            if c not in self.selecting:
                self.selecting = [c]
                break
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="Thêm lá tiếp theo ▶", style=discord.ButtonStyle.secondary, emoji="➕", row=0)
    async def pick_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message("Không phải bạn!", ephemeral=True)
        remaining = [c for c in self.player if c not in self.selecting]
        if remaining:
            self.selecting.append(remaining[0])
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="  Đánh!  ", style=discord.ButtonStyle.success, emoji="⚡", row=1)
    async def play_cards(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message("Không phải bạn!", ephemeral=True)
        if not self.selecting:
            return await interaction.response.send_message("❌ Chưa chọn lá nào!", ephemeral=True)

        combo_type = tl_combo_type(self.selecting)
        if not combo_type:
            return await interaction.response.send_message("❌ Bộ bài không hợp lệ!", ephemeral=True)

        if self.current_play:
            if not tl_can_beat(self.current_play, self.selecting):
                return await interaction.response.send_message("❌ Bài không đủ mạnh để đánh!", ephemeral=True)

        # Play the cards
        for c in self.selecting:
            self.player.remove(c)
        self.current_play = self.selecting[:]
        self.current_type = combo_type
        self.selecting = []
        self.player_passed = False

        if not self.player:
            await self._end(interaction, won=True)
            return

        # Bot turn
        await interaction.response.defer()
        msg = await interaction.original_response()
        await asyncio.sleep(0.8)

        bot_move = bot_tien_len_move(self.bot_hand, self.current_play, self.current_type)
        if bot_move:
            for c in bot_move:
                self.bot_hand.remove(c)
            self.current_play = bot_move
            e = self.make_embed()
            e.add_field(name="🤖 Bot đánh", value=fmt_hand(bot_move), inline=False)
            await msg.edit(embed=e, view=self)
            if not self.bot_hand:
                await asyncio.sleep(0.5)
                await self._end(interaction, won=False, msg=msg)
                return
        else:
            e = self.make_embed()
            e.add_field(name="🤖 Bot", value="*Bỏ lượt (Pass)*", inline=False)
            self.current_play = None
            self.current_type = None
            await msg.edit(embed=e, view=self)

        await asyncio.sleep(0.3)
        await msg.edit(embed=self.make_embed(), view=self)

    @discord.ui.button(label=" Bỏ lượt (Pass) ", style=discord.ButtonStyle.danger, emoji="🏳️", row=1)
    async def pass_turn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message("Không phải bạn!", ephemeral=True)
        if not self.current_play:
            return await interaction.response.send_message("❌ Bàn trống, bạn phải đánh bài!", ephemeral=True)
        self.selecting = []
        await interaction.response.defer()
        msg = await interaction.original_response()

        # Bot leads new round
        await asyncio.sleep(0.5)
        if self.bot_hand:
            best = tl_sort(self.bot_hand)[0]
            self.bot_hand.remove(best)
            self.current_play = [best]
            self.current_type = "single"
            e = self.make_embed()
            e.add_field(name="🤖 Bot dẫn đầu", value=fmt_hand([best]), inline=False)
            await msg.edit(embed=e, view=self)
            if not self.bot_hand:
                await asyncio.sleep(0.5)
                await self._end(interaction, won=False, msg=msg)
                return
        await asyncio.sleep(0.3)
        await msg.edit(embed=self.make_embed(), view=self)

    async def _end(self, interaction, won, msg=None):
        for child in self.children: child.disabled = True
        self.stop()
        net = self.bet if won else -self.bet
        self.db.update_balance(self.uid, net)
        if net > 0: self.db.record_game(self.uid, net, 0)
        else: self.db.record_game(self.uid, 0, abs(net))
        bal = self.db.get_user(self.uid)["balance"]
        net_str = f"+{net:,}" if net >= 0 else f"{net:,}"
        color = 0x2ECC71 if won else 0xE74C3C
        result = "🎉 **Bạn thắng! Đánh hết bài trước!**" if won else "😢 **Bot thắng! Bạn thua rồi!**"
        e = discord.Embed(title="🀄  T I Ế N  L Ê N  —  K Ế T  T H Ú C", color=color)
        e.add_field(name="Kết quả", value=result, inline=False)
        e.add_field(name="Net", value=f"{CURRENCY} **{net_str}**", inline=True)
        e.add_field(name="Số dư", value=coin(bal), inline=True)
        if msg:
            await msg.edit(embed=e, view=self)
        else:
            try:
                msg2 = await interaction.original_response()
                await msg2.edit(embed=e, view=self)
            except:
                pass


# ════════════════════════════════════════════════════════════
#  COG
# ════════════════════════════════════════════════════════════
class VietCards(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db  = bot.db

    # ── /bacay ─────────────────────────────────────────────
    @app_commands.command(name="bacay", description="🃏 Chơi 3 Cây (Bài Cào) — so điểm với nhà cái!")
    @app_commands.describe(bet="Số tiền cược")
    async def bacay(self, interaction: discord.Interaction, bet: int):
        data = self.db.get_user(interaction.user.id, interaction.user.display_name)
        err = clamp_bet(bet, data["balance"])
        if err:
            return await interaction.response.send_message(err, ephemeral=True)

        deck = make_deck()
        player_hand = [deck.pop(), deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop(), deck.pop()]

        pr, pl = ba_cay_hand_rank(player_hand)
        e = discord.Embed(title="🃏  3  C Â Y  —  B À I  C À O", color=0xC0392B)
        e.add_field(name="👤 Bài của bạn", value=fmt_hand(player_hand), inline=False)
        e.add_field(name="🏦 Nhà cái", value="🂠 🂠 🂠 *(úp)*", inline=False)
        e.add_field(name="Điểm của bạn", value=f"**{pl}**", inline=True)
        e.add_field(name="Cược", value=coin(bet), inline=True)
        e.set_footer(text="3 Tây👑 > 3 Đôi🎯 > 9 > 8 > ... > 0  |  Hòa → so chất ♥>♦>♣>♠")

        view = BaCayView(self.bot, interaction, bet, player_hand, dealer_hand)
        await interaction.response.send_message(embed=e, view=view)
        view.msg = await interaction.original_response()

    # ── /lieng ─────────────────────────────────────────────
    @app_commands.command(name="lieng", description="🃏 Chơi Liêng — 3 lá, so tay bài với nhà cái!")
    @app_commands.describe(bet="Số tiền cược")
    async def lieng(self, interaction: discord.Interaction, bet: int):
        data = self.db.get_user(interaction.user.id, interaction.user.display_name)
        err = clamp_bet(bet, data["balance"])
        if err:
            return await interaction.response.send_message(err, ephemeral=True)

        deck = make_deck()
        player_hand = [deck.pop(), deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop(), deck.pop()]

        _, pname = lieng_hand_type(player_hand)
        e = discord.Embed(title="🃏  L I Ê N G  —  3  L Á", color=0x6C3483)
        e.add_field(name="👤 Bài của bạn", value=fmt_hand(player_hand), inline=False)
        e.add_field(name="🏦 Nhà cái", value="🂠 🂠 🂠 *(úp)*", inline=False)
        e.add_field(name="Tay bài", value=f"**{pname}**", inline=True)
        e.add_field(name="Cược", value=coin(bet), inline=True)
        e.set_footer(text="Sảnh Đồng Chất > Ba Đôi > Sảnh > Thùng > Đôi > Bài Cao  |  Theo hoặc Bỏ bài")

        view = LiengView(self.bot, interaction, bet, player_hand, dealer_hand)
        await interaction.response.send_message(embed=e, view=view)

    # ── /xidach ────────────────────────────────────────────
    @app_commands.command(name="xidach", description="🎴 Chơi Xì Dách — Blackjack phiên bản Việt Nam!")
    @app_commands.describe(bet="Số tiền cược")
    async def xidach(self, interaction: discord.Interaction, bet: int):
        data = self.db.get_user(interaction.user.id, interaction.user.display_name)
        err = clamp_bet(bet, data["balance"])
        if err:
            return await interaction.response.send_message(err, ephemeral=True)

        deck = make_deck()
        player, dealer = [], []

        # Deal with animation setup
        e = discord.Embed(title="🎴  X Ì  D Á C H  —  C H I A  B À I . . .", color=0x1A1A2E)
        e.add_field(name="Đang chia bài...", value="🂠 🂠 🂠 🂠", inline=False)
        await interaction.response.send_message(embed=e)
        msg = await interaction.original_response()
        await asyncio.sleep(0.5)

        for i in range(4):
            if i % 2 == 0: player.append(deck.pop())
            else: dealer.append(deck.pop())
            deal_e = discord.Embed(title="🎴  C H I A  B À I . . .", color=0x1A1A2E)
            deal_e.add_field(name=f"👤 Bài bạn [{xi_dach_total(player)}]", value=fmt_hand(player) if player else "🂠", inline=False)
            deal_e.add_field(name="🏦 Nhà cái [?]",
                value=(fmt_hand(dealer) + "  🂠") if len(dealer)==1 else fmt_hand(dealer[:1])+"  🂠" if dealer else "🂠",
                inline=False)
            deal_e.set_footer(text=f"Cược: {bet:,} {CURRENCY}")
            await msg.edit(embed=deal_e)
            await asyncio.sleep(0.4)

        view = XiDachView(self.bot, interaction, bet, player, dealer, deck)
        view.msg = msg

        # Check instant win
        instant = xi_dach_check(player)
        if instant == "xi_ban":
            while xi_dach_total(dealer) <= 16: dealer.append(deck.pop())
            mult = 3
            net = bet * (mult - 1)
            view.db.update_balance(interaction.user.id, net)
            view.db.record_game(interaction.user.id, net, 0)
            bal = view.db.get_user(interaction.user.id)["balance"]
            for child in view.children: child.disabled = True
            view.stop()
            await msg.edit(embed=view.make_embed(reveal=True,
                result=f"🔥 **Xì Bàn! AA! Thắng {mult}x!**", net=net, bal=bal, status="xi_ban"), view=view)
            return
        elif instant == "xi_dach":
            while xi_dach_total(dealer) <= 16: dealer.append(deck.pop())
            dcheck = xi_dach_check(dealer)
            if dcheck == "xi_dach":
                net = 0
                result = "🤝 **Cả hai Xì Dách — Hòa! Hoàn cược.**"
                status = "push"
            else:
                net = bet  # 2x = win 1x the bet
                result = "🎊 **Xì Dách! Thắng 2x!**"
                status = "xi_dach"
            view.db.update_balance(interaction.user.id, net)
            if net > 0: view.db.record_game(interaction.user.id, net, 0)
            bal = view.db.get_user(interaction.user.id)["balance"]
            for child in view.children: child.disabled = True
            view.stop()
            await msg.edit(embed=view.make_embed(reveal=True, result=result, net=net, bal=bal, status=status), view=view)
            return

        await msg.edit(embed=view.make_embed(), view=view)

    # ── /tienlen ───────────────────────────────────────────
    @app_commands.command(name="tienlen", description="🀄 Chơi Tiến Lên 1v1 với Bot — ai hết bài trước thắng!")
    @app_commands.describe(bet="Số tiền cược")
    async def tienlen(self, interaction: discord.Interaction, bet: int):
        data = self.db.get_user(interaction.user.id, interaction.user.display_name)
        err = clamp_bet(bet, data["balance"])
        if err:
            return await interaction.response.send_message(err, ephemeral=True)

        deck = make_deck()
        player_hand = [deck.pop() for _ in range(13)]
        bot_hand    = [deck.pop() for _ in range(13)]

        view = TienLenView(self.bot, interaction, bet, player_hand, bot_hand)

        e = discord.Embed(title="🀄  T I Ế N  L Ê N  —  1  v  1", color=0x0D3B66)
        e.add_field(name="👤 Bài của bạn (13 lá)", value=view.hand_display(view.player), inline=False)
        e.add_field(name="🤖 Bot (13 lá)", value="🂠 × 13", inline=False)
        e.add_field(name="🃏 Bàn trống", value="*Bạn đánh trước — chọn lá rồi nhấn Đánh!*", inline=False)
        e.set_footer(text=f"Cược: {bet:,} {CURRENCY}  •  3 thấp nhất → 2 cao nhất | Bộ: Đơn, Đôi, Bộ 3+")

        await interaction.response.send_message(embed=e, view=view)
        view.msg = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(VietCards(bot))
