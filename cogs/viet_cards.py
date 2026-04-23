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

# ═══════════════════════════════════════════════
#  DECK UTILS
# ═══════════════════════════════════════════════
SUITS    = ["♠", "♣", "♦", "♥"]
SUIT_EMO = {"♠": "♠️", "♣": "♣️", "♦": "♦️", "♥": "♥️"}
RANKS    = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"]
FLIP     = ["🂠", "🀫", "🎴", "🃏"]

def make_deck():
    d = [f"{r}{s}" for s in SUITS for r in RANKS]
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
    return f"`{card_rank(card)}{SUIT_EMO.get(card_suit(card), card_suit(card))}`"

def fmt_hand(hand):
    return "  ".join(fmt(c) for c in hand)

# ─── helper: send ephemeral warning that auto-deletes ───────
async def warn(interaction, text, delay=4):
    await interaction.response.send_message(text, ephemeral=True, delete_after=delay)


# ═══════════════════════════════════════════════════════════════
#  🃏  3 CÂY (BÀI CÀO)
#  Fix: game is ephemeral (chỉ người chơi thấy)
#       lật từng lá nhà cái một với animation
# ═══════════════════════════════════════════════════════════════
def ba_cay_value(card):
    r = card_rank(card)
    if r in ["J","Q","K"]: return 10
    if r == "A": return 1
    return int(r)

def ba_cay_score(hand):
    return sum(ba_cay_value(c) for c in hand) % 10

def ba_cay_special(hand):
    ranks = [card_rank(c) for c in hand]
    if all(r in ["J","Q","K"] for r in ranks): return ("3 Tây 👑", 13)
    if len(set(ranks)) == 1:                   return ("3 Đôi 🎯", 12)
    return None

def ba_cay_hand_rank(hand):
    sp = ba_cay_special(hand)
    if sp: return (sp[1], sp[0])
    pts = ba_cay_score(hand)
    return (pts, f"**{pts} điểm**")

def ba_cay_tiebreak(h1, h2):
    suit_order = {"♠":0,"♣":1,"♦":2,"♥":3}
    return max(suit_order.get(card_suit(c),0) for c in h1) > \
           max(suit_order.get(card_suit(c),0) for c in h2)

class BaCayView(discord.ui.View):
    def __init__(self, bot, interaction, bet, player_hand, dealer_hand):
        super().__init__(timeout=90)
        self.bot = bot
        self.db  = bot.db
        self.bet = bet
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.uid = interaction.user.id

    def base_embed(self, dealer_revealed=None, title="🃏  3  C Â Y", color=0xC0392B):
        """dealer_revealed = list of cards revealed so far (None = all hidden)"""
        e = discord.Embed(title=title, color=color)
        pr, pl = ba_cay_hand_rank(self.player_hand)
        e.add_field(name="👤 Bài của bạn", value=fmt_hand(self.player_hand), inline=False)
        e.add_field(name=f"Điểm: {pl}", value="\u200b", inline=True)
        e.add_field(name="Cược", value=coin(self.bet), inline=True)

        if dealer_revealed is None:
            e.add_field(name="🏦 Nhà cái", value="🂠  🂠  🂠", inline=False)
        else:
            shown = fmt_hand(dealer_revealed)
            hidden = "  🂠" * (3 - len(dealer_revealed))
            e.add_field(name="🏦 Nhà cái", value=shown + hidden, inline=False)
        e.set_footer(text="3 Tây👑 > 3 Đôi🎯 > 9 > 8 > ... > 0  |  Hòa → so chất ♥>♦>♣>♠")
        return e

    @discord.ui.button(label="👀  Lật từng lá nhà cái!", style=discord.ButtonStyle.danger)
    async def reveal(self, interaction: discord.Interaction, button: discord.ui.Button):
        # FIX 1: chỉ người chơi mới được ấn
        if interaction.user.id != self.uid:
            return await warn(interaction, "❌ Đây không phải ván của bạn!", delay=3)

        await interaction.response.defer()
        msg = await interaction.original_response()
        button.disabled = True
        await msg.edit(view=self)

        # FIX 4: lật từng lá nhà cái một (hồi hộp hơn)
        revealed = []
        for i, card in enumerate(self.dealer_hand):
            # Flip animation cho từng lá
            for frame in FLIP:
                e = self.base_embed(dealer_revealed=revealed)
                e.add_field(name=f"Lá {i+1}...", value=frame, inline=False)
                await msg.edit(embed=e, view=self)
                await asyncio.sleep(0.3)

            revealed.append(card)
            e = self.base_embed(dealer_revealed=revealed)
            await msg.edit(embed=e, view=self)
            await asyncio.sleep(0.7)  # dừng lại để xem lá vừa lật

        # Tính kết quả
        pr, pl = ba_cay_hand_rank(self.player_hand)
        dr, dl = ba_cay_hand_rank(self.dealer_hand)

        if pr > dr:
            won, result = True, f"🎉 Bạn thắng!\n👤 {pl}  vs  🏦 {dl}"
        elif dr > pr:
            won, result = False, f"😢 Nhà cái thắng!\n🏦 {dl}  vs  👤 {pl}"
        else:
            if ba_cay_tiebreak(self.player_hand, self.dealer_hand):
                won, result = True, "🎉 Hòa điểm — bạn thắng theo **chất bài**!"
            else:
                won, result = False, "😢 Hòa điểm — nhà cái thắng theo **chất bài**!"

        net = self.bet if won else -self.bet
        self.db.update_balance(self.uid, net)
        if net > 0: self.db.record_game(self.uid, net, 0)
        else:       self.db.record_game(self.uid, 0, abs(net))
        bal = self.db.get_user(self.uid)["balance"]

        net_str = f"+{net:,}" if net >= 0 else f"{net:,}"
        color = 0x2ECC71 if won else 0xE74C3C
        title = "🃏  3 CÂY — THẮNG! 🎉" if won else "🃏  3 CÂY — THUA 😢"
        e = discord.Embed(title=title, color=color)
        e.add_field(name="👤 Bài của bạn", value=fmt_hand(self.player_hand), inline=True)
        e.add_field(name="🏦 Bài nhà cái", value=fmt_hand(self.dealer_hand), inline=True)
        e.add_field(name="\u200b", value="\u200b", inline=True)
        e.add_field(name="📢 Kết quả", value=result, inline=False)
        e.add_field(name="Net", value=f"{CURRENCY} **{net_str}**", inline=True)
        e.add_field(name="Số dư", value=coin(bal), inline=True)
        e.set_footer(text="3 Tây👑 > 3 Đôi🎯 > 9 > 8 > ... > 0")
        self.stop()
        await msg.edit(embed=e, view=self)


# ═══════════════════════════════════════════════════════════════
#  🃏  LIÊNG
# ═══════════════════════════════════════════════════════════════
RANK_ORDER = {"3":1,"4":2,"5":3,"6":4,"7":5,"8":6,"9":7,
              "10":8,"J":9,"Q":10,"K":11,"A":12,"2":13}

def lieng_rank_val(card):
    return RANK_ORDER.get(card_rank(card), 0)

def lieng_hand_type(hand):
    ranks  = sorted([lieng_rank_val(c) for c in hand])
    suits  = [card_suit(c) for c in hand]
    flush  = len(set(suits)) == 1
    straight = (ranks[2]-ranks[1]==1 and ranks[1]-ranks[0]==1)
    if sorted(ranks) == sorted([RANK_ORDER["A"],RANK_ORDER["2"],RANK_ORDER["3"]]):
        straight = True
    triple = ranks[0]==ranks[1]==ranks[2]
    pair   = ranks[0]==ranks[1] or ranks[1]==ranks[2]
    if straight and flush: return (7, "Sảnh Đồng Chất 🌈")
    if triple:             return (6, "Ba Đôi 🎯")
    if straight:           return (5, "Sảnh ➡️")
    if flush:              return (4, "Thùng ♦️")
    if pair:               return (3, "Đôi 👥")
    return (1, f"Bài Cao {fmt(max(hand, key=lieng_rank_val))}")

def lieng_hand_key(hand):
    htype, _ = lieng_hand_type(hand)
    return (htype, *sorted([lieng_rank_val(c) for c in hand], reverse=True))

class LiengView(discord.ui.View):
    def __init__(self, bot, interaction, bet, player_hand, dealer_hand):
        super().__init__(timeout=90)
        self.bot = bot
        self.db  = bot.db
        self.bet = bet
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.uid = interaction.user.id

    @discord.ui.button(label="✅  Theo (Call)", style=discord.ButtonStyle.success)
    async def call(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.uid:
            return await warn(interaction, "❌ Đây không phải ván của bạn!", delay=3)
        await self._resolve(interaction, folded=False)

    @discord.ui.button(label="🏳️  Bỏ (Fold)", style=discord.ButtonStyle.danger)
    async def fold(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.uid:
            return await warn(interaction, "❌ Đây không phải ván của bạn!", delay=3)
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
            e = discord.Embed(title="🏳️  LIÊNG — BỎ BÀI", color=0x95A5A6)
            e.add_field(name="Bài của bạn", value=fmt_hand(self.player_hand), inline=True)
            e.add_field(name="Bài nhà cái", value=fmt_hand(self.dealer_hand), inline=True)
            e.add_field(name="Net", value=f"{CURRENCY} **{net:,}**", inline=False)
            e.add_field(name="Số dư", value=coin(bal), inline=True)
            return await msg.edit(embed=e, view=self)

        for frame in FLIP:
            e = discord.Embed(title="🃏  LIÊNG — SO BÀI...", color=0x3498DB)
            e.add_field(name="👤 Bài bạn", value=fmt_hand(self.player_hand), inline=True)
            e.add_field(name="🏦 Nhà cái", value=frame, inline=True)
            await msg.edit(embed=e, view=self)
            await asyncio.sleep(0.35)

        pk = lieng_hand_key(self.player_hand)
        dk = lieng_hand_key(self.dealer_hand)
        _, pname = lieng_hand_type(self.player_hand)
        _, dname = lieng_hand_type(self.dealer_hand)

        if pk > dk:   won, result = True,  f"🎉 Bạn thắng!\n👤 {pname}  vs  🏦 {dname}"
        elif dk > pk: won, result = False, f"😢 Nhà cái thắng!\n🏦 {dname}  vs  👤 {pname}"
        else:         won, result = False, "🤝 Hòa — nhà cái giữ tiền!"

        net = self.bet if won else -self.bet
        self.db.update_balance(self.uid, net)
        if net > 0: self.db.record_game(self.uid, net, 0)
        else:       self.db.record_game(self.uid, 0, abs(net))
        bal = self.db.get_user(self.uid)["balance"]

        net_str = f"+{net:,}" if net >= 0 else f"{net:,}"
        color = 0x2ECC71 if won else 0xE74C3C
        e = discord.Embed(title="🃏  LIÊNG — KẾT QUẢ", color=color)
        e.add_field(name="👤 Bài bạn", value=fmt_hand(self.player_hand), inline=True)
        e.add_field(name="🏦 Nhà cái", value=fmt_hand(self.dealer_hand), inline=True)
        e.add_field(name="\u200b", value="\u200b", inline=True)
        e.add_field(name="📢 Kết quả", value=result, inline=False)
        e.add_field(name="Net", value=f"{CURRENCY} **{net_str}**", inline=True)
        e.add_field(name="Số dư", value=coin(bal), inline=True)
        e.set_footer(text="Sảnh Đồng Chất > Ba Đôi > Sảnh > Thùng > Đôi > Bài Cao")
        await msg.edit(embed=e, view=self)


# ═══════════════════════════════════════════════════════════════
#  🎴  XÌ DÁCH
# ═══════════════════════════════════════════════════════════════
def xi_value(card):
    r = card_rank(card)
    if r in ["J","Q","K"]: return 10
    if r == "A": return 11
    return int(r)

def xi_total(hand):
    total = sum(xi_value(c) for c in hand)
    aces  = sum(1 for c in hand if card_rank(c) == "A")
    while total > 21 and aces:
        total -= 10; aces -= 1
    return total

def xi_instant(hand):
    if len(hand) != 2: return None
    ranks = [card_rank(c) for c in hand]
    if ranks[0] == ranks[1] == "A":                                   return "xi_ban"
    if "A" in ranks and any(r in ["J","Q","K","10"] for r in ranks):  return "xi_dach"
    return None

class XiDachView(discord.ui.View):
    def __init__(self, bot, interaction, bet, player, dealer, deck):
        super().__init__(timeout=120)
        self.bot = bot; self.db = bot.db
        self.bet = bet; self.player = player
        self.dealer = dealer; self.deck = deck
        self.uid = interaction.user.id
        self.msg = None

    def make_embed(self, reveal=False, result=None, net=None, bal=None, status="playing"):
        pv = xi_total(self.player); dv = xi_total(self.dealer)
        colors  = {"playing":0x1A1A2E,"win":0x2ECC71,"lose":0xE74C3C,
                   "push":0x95A5A6,"xi_dach":0xF4C430,"xi_ban":0xFF6B6B,"flip":0x3498DB}
        titles  = {"playing":"🎴  XÌ DÁCH","win":"🎴  THẮNG! 🎉","lose":"🎴  THUA 😢",
                   "push":"🎴  HÒA","xi_dach":"🎴  XÌ DÁCH! 🎊","xi_ban":"🎴  XÌ BÀN! 🔥",
                   "flip":"🎴  NHÀ CÁI RÚT BÀI..."}
        e = discord.Embed(title=titles.get(status,"🎴 Xì Dách"), color=colors.get(status,0x1A1A2E))
        e.add_field(name=f"👤 Bài bạn  [{pv}]", value=fmt_hand(self.player), inline=False)
        if reveal:
            e.add_field(name=f"🏦 Nhà cái  [{dv}]", value=fmt_hand(self.dealer), inline=False)
        else:
            e.add_field(name="🏦 Nhà cái  [?]", value=f"{fmt(self.dealer[0])}  🂠", inline=False)
        e.add_field(name="\u200b", value="─────────────────", inline=False)
        if result: e.add_field(name="📢 Kết quả", value=result, inline=False)
        if net is not None:
            e.add_field(name="Net", value=f"{CURRENCY} **{'+' if net>=0 else ''}{net:,}**", inline=True)
        if bal is not None:
            e.add_field(name="Số dư", value=coin(bal), inline=True)
        e.set_footer(text=f"Cược: {self.bet:,} {CURRENCY}  •  Xì Bàn=3x | Xì Dách=2x | Nhà cái rút ≤16")
        return e

    async def dealer_draw(self, msg):
        for frame in FLIP:
            e = discord.Embed(title="🎴  NHÀ CÁI LẬT BÀI...", color=0x3498DB)
            e.add_field(name=f"👤 Bài bạn [{xi_total(self.player)}]", value=fmt_hand(self.player), inline=False)
            e.add_field(name="🏦 Nhà cái lật...", value=f"{fmt(self.dealer[0])}  {frame}", inline=False)
            await msg.edit(embed=e, view=self)
            await asyncio.sleep(0.35)
        while xi_total(self.dealer) <= 16:
            self.dealer.append(self.deck.pop())
            await msg.edit(embed=self.make_embed(reveal=True, status="flip"), view=self)
            await asyncio.sleep(0.55)

    async def finish(self, msg):
        pv = xi_total(self.player); dv = xi_total(self.dealer)
        if   pv > 21:   status, result, net = "lose",   "💥 **Quá 21! Thua.**",             -self.bet
        elif dv > 21:   status, result, net = "win",    "💥 **Nhà cái quá 21! Thắng!**",     self.bet
        elif pv > dv:   status, result, net = "win",    f"✅ **{pv} vs {dv} — Thắng!**",     self.bet
        elif pv == dv:  status, result, net = "push",   f"🤝 **Hòa {pv} điểm — hoàn cược.**", 0
        else:           status, result, net = "lose",   f"❌ **{dv} vs {pv} — Nhà cái thắng.**", -self.bet
        self.db.update_balance(self.uid, net)
        if net > 0: self.db.record_game(self.uid, net, 0)
        elif net < 0: self.db.record_game(self.uid, 0, abs(net))
        bal = self.db.get_user(self.uid)["balance"]
        for child in self.children: child.disabled = True
        self.stop()
        await msg.edit(embed=self.make_embed(reveal=True, result=result, net=net, bal=bal, status=status), view=self)

    @discord.ui.button(label="👊  Rút (Hit)", style=discord.ButtonStyle.success)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.uid:
            return await warn(interaction, "❌ Đây không phải ván của bạn!", delay=3)
        await interaction.response.defer()
        msg = await interaction.original_response()
        for frame in FLIP:
            e = self.make_embed()
            e.add_field(name="Rút bài...", value=frame, inline=False)
            await msg.edit(embed=e, view=self); await asyncio.sleep(0.22)
        self.player.append(self.deck.pop())
        if xi_total(self.player) >= 21:
            await self.dealer_draw(msg); await self.finish(msg)
        else:
            await msg.edit(embed=self.make_embed(), view=self)

    @discord.ui.button(label="✋  Dừng (Stand)", style=discord.ButtonStyle.danger)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.uid:
            return await warn(interaction, "❌ Đây không phải ván của bạn!", delay=3)
        await interaction.response.defer()
        msg = await interaction.original_response()
        await self.dealer_draw(msg); await self.finish(msg)

    @discord.ui.button(label="💰  Gấp Đôi (Double)", style=discord.ButtonStyle.primary)
    async def double(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.uid:
            return await warn(interaction, "❌ Đây không phải ván của bạn!", delay=3)
        if len(self.player) != 2:
            return await warn(interaction, "❌ Chỉ gấp đôi được với 2 lá đầu!", delay=4)
        if self.db.get_user(self.uid)["balance"] < self.bet:
            return await warn(interaction, "❌ Không đủ tiền để gấp đôi!", delay=4)
        await interaction.response.defer()
        msg = await interaction.original_response()
        self.bet *= 2
        for frame in FLIP:
            e = self.make_embed()
            e.add_field(name="💰 Gấp đôi...", value=frame, inline=False)
            await msg.edit(embed=e, view=self); await asyncio.sleep(0.22)
        self.player.append(self.deck.pop())
        await msg.edit(embed=self.make_embed(), view=self)
        await asyncio.sleep(0.6)
        await self.dealer_draw(msg); await self.finish(msg)

    async def on_timeout(self):
        for child in self.children: child.disabled = True
        if self.msg:
            try: await self.msg.edit(view=self)
            except: pass


# ═══════════════════════════════════════════════════════════════
#  🀄  TIẾN LÊN — 1v1 vs Bot
#  Fix: chọn bài tự do bằng Select Menu (dropdown)
# ═══════════════════════════════════════════════════════════════
TL_ORDER  = {"3":1,"4":2,"5":3,"6":4,"7":5,"8":6,"9":7,
             "10":8,"J":9,"Q":10,"K":11,"A":12,"2":13}
SUIT_VAL  = {"♠":1,"♣":2,"♦":3,"♥":4}

def tl_key(card):
    return (TL_ORDER.get(card_rank(card),0), SUIT_VAL.get(card_suit(card),0))

def tl_sort(hand):
    return sorted(hand, key=tl_key)

def tl_combo(cards):
    if not cards: return None
    n = len(cards)
    if n == 1: return "single"
    ranks = [card_rank(c) for c in cards]
    vals  = sorted(TL_ORDER.get(r,0) for r in ranks)
    if n == 2 and ranks[0] == ranks[1]: return "pair"
    if n == 4 and len(set(ranks)) == 1: return "four"
    if n >= 3:
        if len(set(vals)) == n and all(vals[i]+1==vals[i+1] for i in range(n-1)): return "seq"
        if n % 2 == 0:
            pairs = [(cards[i],cards[i+1]) for i in range(0,n,2)]
            if all(card_rank(p[0])==card_rank(p[1]) for p in pairs):
                pv = sorted(TL_ORDER.get(card_rank(p[0]),0) for p in pairs)
                if all(pv[i]+1==pv[i+1] for i in range(len(pv)-1)): return "pair_seq"
    return None

def tl_can_beat(prev, new):
    pt = tl_combo(prev); nt = tl_combo(new)
    if pt != nt: return False
    return max(tl_key(c) for c in new) > max(tl_key(c) for c in prev)

def bot_move(hand, current, ctype):
    hand = tl_sort(hand)
    if ctype == "single":
        for c in hand:
            if tl_can_beat(current,[c]): return [c]
    elif ctype == "pair":
        by_rank = {}
        for c in hand: by_rank.setdefault(card_rank(c),[]).append(c)
        for r in sorted(by_rank, key=lambda r: TL_ORDER.get(r,0)):
            if len(by_rank[r]) >= 2:
                p = by_rank[r][:2]
                if tl_can_beat(current,p): return p
    elif ctype == "seq":
        n = len(current)
        for i in range(len(hand)-n+1):
            seq = hand[i:i+n]
            vals = [TL_ORDER.get(card_rank(c),0) for c in seq]
            if all(vals[j]+1==vals[j+1] for j in range(n-1)):
                if tl_can_beat(current,seq): return seq
    return None

def build_card_select(hand, selected):
    """Build a SelectMenu with all cards in hand"""
    options = []
    for c in tl_sort(hand):
        r = card_rank(c); s = card_suit(c)
        label = f"{r}{SUIT_EMO.get(s,s)}"
        desc  = "✅ Đã chọn" if c in selected else f"Rank {TL_ORDER.get(r,0)}"
        options.append(discord.SelectOption(
            label=label, value=c,
            description=desc,
            default=(c in selected),
            emoji="✅" if c in selected else None
        ))
    return options

class TienLenSelectMenu(discord.ui.Select):
    def __init__(self, view_ref):
        self.view_ref = view_ref
        hand = view_ref.player
        options = build_card_select(hand, view_ref.selecting)
        # Discord limit: max 25 options per select
        super().__init__(
            placeholder="🃏 Chọn lá bài muốn đánh (có thể chọn nhiều)...",
            min_values=1,
            max_values=min(len(hand), 10),
            options=options[:25],
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view_ref.uid:
            return await warn(interaction, "❌ Đây không phải ván của bạn!", delay=3)
        self.view_ref.selecting = list(self.values)
        await interaction.response.edit_message(
            embed=self.view_ref.make_embed(), view=self.view_ref
        )

class TienLenView(discord.ui.View):
    def __init__(self, bot, interaction, bet, player_hand, bot_hand):
        super().__init__(timeout=300)
        self.bot      = bot
        self.db       = bot.db
        self.bet      = bet
        self.player   = tl_sort(player_hand)
        self.bot_hand = tl_sort(bot_hand)
        self.uid      = interaction.user.id
        self.current  = None   # cards currently on table
        self.ctype    = None
        self.selecting = []
        self.msg      = None
        self.last_status = ""
        self._rebuild_select()

    def _rebuild_select(self):
        """Rebuild the select menu with current hand"""
        # Remove old select if exists
        to_remove = [c for c in self.children if isinstance(c, TienLenSelectMenu)]
        for c in to_remove: self.remove_item(c)
        if self.player:
            self.add_item(TienLenSelectMenu(self))

    def make_embed(self, status="playing", extra_msg=None):
        colors = {"playing":0x0D3B66, "win":0x2ECC71, "lose":0xE74C3C}
        e = discord.Embed(
            title="🀄  TIẾN LÊN — 1v1",
            color=colors.get(status, 0x0D3B66)
        )
        e.add_field(
            name=f"👤 Bài bạn ({len(self.player)} lá)",
            value=fmt_hand(self.player) if self.player else "*Hết bài!*",
            inline=False
        )
        e.add_field(
            name=f"🤖 Bot ({len(self.bot_hand)} lá)",
            value=f"🂠 × {len(self.bot_hand)}" if self.bot_hand else "*Hết bài!*",
            inline=False
        )
        if self.current:
            e.add_field(name="🃏 Bài trên bàn", value=fmt_hand(self.current), inline=False)
        else:
            e.add_field(name="🃏 Bàn trống", value="*Bạn đánh trước*", inline=False)
        if self.selecting:
            e.add_field(
                name="✅ Đang chọn để đánh",
                value=fmt_hand(self.selecting),
                inline=False
            )
        if extra_msg:
            e.add_field(name="📢", value=extra_msg, inline=False)
        e.set_footer(text=f"Cược: {self.bet:,} {CURRENCY}  •  Dùng dropdown chọn bài → Đánh hoặc Bỏ lượt")
        return e

    @discord.ui.button(label="⚡  Đánh!", style=discord.ButtonStyle.success, row=1)
    async def play_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.uid:
            return await warn(interaction, "❌ Đây không phải ván của bạn!", delay=3)
        if not self.selecting:
            return await warn(interaction, "❌ Chưa chọn lá nào! Dùng dropdown bên trên.", delay=4)

        ct = tl_combo(self.selecting)
        if not ct:
            return await warn(interaction, "❌ Bộ bài không hợp lệ! (đơn / đôi / bộ liên tiếp)", delay=5)

        if self.current and not tl_can_beat(self.current, self.selecting):
            return await warn(interaction, "❌ Bài không đủ mạnh để đánh!", delay=4)

        # Play cards
        for c in self.selecting: self.player.remove(c)
        self.current = self.selecting[:]
        self.ctype   = ct
        self.selecting = []
        self._rebuild_select()

        if not self.player:
            return await self._end(interaction, won=True)

        await interaction.response.defer()
        msg = await interaction.original_response()
        await msg.edit(embed=self.make_embed(), view=self)
        await asyncio.sleep(0.8)

        # Bot turn
        bmove = bot_move(self.bot_hand, self.current, self.ctype)
        if bmove:
            for c in bmove: self.bot_hand.remove(c)
            self.current = bmove; self.ctype = tl_combo(bmove)
            extra = f"🤖 Bot đánh: {fmt_hand(bmove)}"
            await msg.edit(embed=self.make_embed(extra_msg=extra), view=self)
            if not self.bot_hand:
                await asyncio.sleep(0.6)
                return await self._end(interaction, won=False, msg=msg)
        else:
            self.current = None; self.ctype = None
            extra = "🤖 Bot **bỏ lượt** — bàn trống, bạn đánh trước!"
            await msg.edit(embed=self.make_embed(extra_msg=extra), view=self)

        await asyncio.sleep(0.5)
        self._rebuild_select()
        await msg.edit(embed=self.make_embed(), view=self)

    @discord.ui.button(label="🏳️  Bỏ lượt (Pass)", style=discord.ButtonStyle.secondary, row=1)
    async def pass_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.uid:
            return await warn(interaction, "❌ Đây không phải ván của bạn!", delay=3)
        if not self.current:
            return await warn(interaction, "❌ Bàn trống — bạn phải đánh bài!", delay=4)

        self.selecting = []
        await interaction.response.defer()
        msg = await interaction.original_response()
        await asyncio.sleep(0.5)

        # Bot leads
        if self.bot_hand:
            lead = tl_sort(self.bot_hand)[0]
            self.bot_hand.remove(lead)
            self.current = [lead]; self.ctype = "single"
            extra = f"🤖 Bot dẫn đầu: {fmt(lead)}"
            self._rebuild_select()
            await msg.edit(embed=self.make_embed(extra_msg=extra), view=self)
            if not self.bot_hand:
                await asyncio.sleep(0.6)
                return await self._end(interaction, won=False, msg=msg)
        await asyncio.sleep(0.4)
        self._rebuild_select()
        await msg.edit(embed=self.make_embed(), view=self)

    @discord.ui.button(label="🗑️  Bỏ chọn", style=discord.ButtonStyle.danger, row=1)
    async def clear_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.uid:
            return await warn(interaction, "❌ Đây không phải ván của bạn!", delay=3)
        self.selecting = []
        self._rebuild_select()
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    async def _end(self, interaction, won, msg=None):
        for child in self.children: child.disabled = True
        self.stop()
        net = self.bet if won else -self.bet
        self.db.update_balance(self.uid, net)
        if net > 0: self.db.record_game(self.uid, net, 0)
        else:       self.db.record_game(self.uid, 0, abs(net))
        bal = self.db.get_user(self.uid)["balance"]
        net_str = f"+{net:,}" if net >= 0 else f"{net:,}"
        color  = 0x2ECC71 if won else 0xE74C3C
        result = "🎉 **Bạn thắng! Đánh hết bài trước!**" if won else "😢 **Bot thắng! Bạn thua rồi!**"
        e = discord.Embed(title="🀄  TIẾN LÊN — KẾT THÚC", color=color)
        e.add_field(name="Kết quả", value=result, inline=False)
        e.add_field(name="Net",     value=f"{CURRENCY} **{net_str}**", inline=True)
        e.add_field(name="Số dư",   value=coin(bal), inline=True)
        target = msg
        if not target:
            try: target = await interaction.original_response()
            except: return
        await target.edit(embed=e, view=self)

    async def on_timeout(self):
        for child in self.children: child.disabled = True
        if self.msg:
            try: await self.msg.edit(view=self)
            except: pass


# ═══════════════════════════════════════════════════════════════
#  COG — register commands
# ═══════════════════════════════════════════════════════════════
class VietCards(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db  = bot.db

    # ── /bacay ────────────────────────────────────────────
    @app_commands.command(name="bacay", description="🃏 Chơi 3 Cây (Bài Cào) — lật từng lá nhà cái!")
    @app_commands.describe(bet="Số tiền cược")
    async def bacay(self, interaction: discord.Interaction, bet: int):
        data = self.db.get_user(interaction.user.id, interaction.user.display_name)
        err  = clamp_bet(bet, data["balance"])
        if err:
            return await interaction.response.send_message(err, ephemeral=True, delete_after=5)

        deck = make_deck()
        player_hand = [deck.pop() for _ in range(3)]
        dealer_hand = [deck.pop() for _ in range(3)]

        _, pl = ba_cay_hand_rank(player_hand)
        view = BaCayView(self.bot, interaction, bet, player_hand, dealer_hand)

        e = discord.Embed(title="🃏  3 CÂY — BÀI CÀO", color=0xC0392B)
        e.add_field(name="👤 Bài của bạn", value=fmt_hand(player_hand), inline=False)
        e.add_field(name="🏦 Nhà cái",     value="🂠  🂠  🂠  *(chưa lật)*", inline=False)
        e.add_field(name="Điểm của bạn",   value=f"**{pl}**", inline=True)
        e.add_field(name="Cược",           value=coin(bet), inline=True)
        e.set_footer(text="Ấn nút để lật từng lá nhà cái!")

        # FIX 1: ephemeral=True → chỉ mình bạn thấy nút
        await interaction.response.send_message(embed=e, view=view, ephemeral=True)

    # ── /lieng ────────────────────────────────────────────
    @app_commands.command(name="lieng", description="🃏 Chơi Liêng — 3 lá, Theo hoặc Bỏ!")
    @app_commands.describe(bet="Số tiền cược")
    async def lieng(self, interaction: discord.Interaction, bet: int):
        data = self.db.get_user(interaction.user.id, interaction.user.display_name)
        err  = clamp_bet(bet, data["balance"])
        if err:
            return await interaction.response.send_message(err, ephemeral=True, delete_after=5)

        deck = make_deck()
        player_hand = [deck.pop() for _ in range(3)]
        dealer_hand = [deck.pop() for _ in range(3)]
        _, pname = lieng_hand_type(player_hand)

        view = LiengView(self.bot, interaction, bet, player_hand, dealer_hand)
        e = discord.Embed(title="🃏  LIÊNG — 3 LÁ", color=0x6C3483)
        e.add_field(name="👤 Bài của bạn", value=fmt_hand(player_hand), inline=False)
        e.add_field(name="🏦 Nhà cái",     value="🂠  🂠  🂠  *(úp)*", inline=False)
        e.add_field(name="Tay bài",        value=f"**{pname}**", inline=True)
        e.add_field(name="Cược",           value=coin(bet), inline=True)
        e.set_footer(text="Sảnh Đồng Chất > Ba Đôi > Sảnh > Thùng > Đôi > Bài Cao")

        await interaction.response.send_message(embed=e, view=view, ephemeral=True)

    # ── /xidach ───────────────────────────────────────────
    @app_commands.command(name="xidach", description="🎴 Chơi Xì Dách — Blackjack Việt Nam!")
    @app_commands.describe(bet="Số tiền cược")
    async def xidach(self, interaction: discord.Interaction, bet: int):
        data = self.db.get_user(interaction.user.id, interaction.user.display_name)
        err  = clamp_bet(bet, data["balance"])
        if err:
            return await interaction.response.send_message(err, ephemeral=True, delete_after=5)

        deck = make_deck()
        player, dealer = [], []

        e = discord.Embed(title="🎴  XÌ DÁCH — CHIA BÀI...", color=0x1A1A2E)
        e.add_field(name="Đang chia bài...", value="🂠 🂠 🂠 🂠", inline=False)
        # FIX 1: ephemeral
        await interaction.response.send_message(embed=e, ephemeral=True)
        msg = await interaction.original_response()
        await asyncio.sleep(0.5)

        for i in range(4):
            if i % 2 == 0: player.append(deck.pop())
            else:           dealer.append(deck.pop())
            de = discord.Embed(title="🎴  CHIA BÀI...", color=0x1A1A2E)
            de.add_field(name=f"👤 Bài bạn [{xi_total(player)}]",
                value=fmt_hand(player) if player else "🂠", inline=False)
            de.add_field(name="🏦 Nhà cái [?]",
                value=(fmt_hand(dealer)+"  🂠") if len(dealer)==1 else fmt_hand(dealer[:1])+"  🂠" if dealer else "🂠",
                inline=False)
            de.set_footer(text=f"Cược: {bet:,} {CURRENCY}")
            await msg.edit(embed=de)
            await asyncio.sleep(0.4)

        view = XiDachView(self.bot, interaction, bet, player, dealer, deck)
        view.msg = msg

        instant = xi_instant(player)
        if instant == "xi_ban":
            while xi_total(dealer) <= 16: dealer.append(deck.pop())
            net = bet * 2
            view.db.update_balance(interaction.user.id, net)
            view.db.record_game(interaction.user.id, net, 0)
            bal = view.db.get_user(interaction.user.id)["balance"]
            for child in view.children: child.disabled = True
            view.stop()
            await msg.edit(embed=view.make_embed(reveal=True,
                result="🔥 **Xì Bàn! AA! Thắng 3x!**", net=net, bal=bal, status="xi_ban"), view=view)
            return
        elif instant == "xi_dach":
            while xi_total(dealer) <= 16: dealer.append(deck.pop())
            di = xi_instant(dealer)
            if di == "xi_dach":
                net, result, status = 0, "🤝 **Cả hai Xì Dách — Hòa!**", "push"
            else:
                net, result, status = bet, "🎊 **Xì Dách! Thắng 2x!**", "xi_dach"
            view.db.update_balance(interaction.user.id, net)
            if net > 0: view.db.record_game(interaction.user.id, net, 0)
            bal = view.db.get_user(interaction.user.id)["balance"]
            for child in view.children: child.disabled = True
            view.stop()
            await msg.edit(embed=view.make_embed(reveal=True, result=result, net=net, bal=bal, status=status), view=view)
            return

        await msg.edit(embed=view.make_embed(), view=view)

    # ── /tienlen ──────────────────────────────────────────
    @app_commands.command(name="tienlen", description="🀄 Tiến Lên 1v1 với Bot — ai hết bài trước thắng!")
    @app_commands.describe(bet="Số tiền cược")
    async def tienlen(self, interaction: discord.Interaction, bet: int):
        data = self.db.get_user(interaction.user.id, interaction.user.display_name)
        err  = clamp_bet(bet, data["balance"])
        if err:
            return await interaction.response.send_message(err, ephemeral=True, delete_after=5)

        deck = make_deck()
        player_hand = [deck.pop() for _ in range(13)]
        bot_hand    = [deck.pop() for _ in range(13)]

        view = TienLenView(self.bot, interaction, bet, player_hand, bot_hand)

        e = discord.Embed(title="🀄  TIẾN LÊN — 1v1", color=0x0D3B66)
        e.add_field(name="👤 Bài của bạn (13 lá)", value=fmt_hand(view.player), inline=False)
        e.add_field(name="🤖 Bot (13 lá)",          value="🂠 × 13", inline=False)
        e.add_field(name="🃏 Bàn trống",             value="*Dùng dropdown chọn bài → Đánh!*", inline=False)
        e.set_footer(text=f"Cược: {bet:,} {CURRENCY}  •  3 thấp → 2 cao | Chọn bài tuỳ ý qua menu!")

        # FIX 1: ephemeral
        await interaction.response.send_message(embed=e, view=view, ephemeral=True)
        view.msg = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(VietCards(bot))
