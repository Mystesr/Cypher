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
FLIP     = ["🂠", "🀫", "🎴", "🃏"]

def make_deck():
    ranks = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"]
    d = [f"{r}{s}" for s in SUITS for r in ranks]
    random.shuffle(d)
    return d

def card_rank(card):
    for s in SUITS:
        if card.endswith(s): return card[:-len(s)]
    return card[:-1]

def card_suit(card):
    for s in SUITS:
        if card.endswith(s): return s
    return card[-1]

def fmt(card):
    return f"`{card_rank(card)}{SUIT_EMO.get(card_suit(card), card_suit(card))}`"

def fmt_hand(hand):
    return "  ".join(fmt(c) for c in hand)

async def warn(interaction, text, delay=4):
    await interaction.response.send_message(text, ephemeral=True, delete_after=delay)


# ═══════════════════════════════════════════════════════════════
#  PATTERN: Public embed + Private buttons
#
#  Mỗi game có 2 message:
#    1. public_msg  → embed mọi người thấy, KHÔNG có nút
#    2. ctrl_msg    → ephemeral chỉ người chơi thấy, CÓ nút bấm
#
#  Khi có hành động → cập nhật CẢ HAI:
#    - public_msg cập nhật embed (không nút)
#    - ctrl_msg cập nhật nút (disabled khi xong)
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
#  🃏  3 CÂY (BÀI CÀO)
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

def ba_cay_rank(hand):
    sp = ba_cay_special(hand)
    if sp: return (sp[1], sp[0])
    pts = ba_cay_score(hand)
    return (pts, f"**{pts} điểm**")

def ba_cay_tiebreak(h1, h2):
    sv = {"♠":0,"♣":1,"♦":2,"♥":3}
    return max(sv.get(card_suit(c),0) for c in h1) > max(sv.get(card_suit(c),0) for c in h2)

def bacay_public_embed(player_hand, dealer_revealed, bet, result=None, net=None, bal=None, color=0xC0392B, title="🃏  3 CÂY — BÀI CÀO"):
    """Embed mọi người đều thấy"""
    e = discord.Embed(title=title, color=color)
    _, pl = ba_cay_rank(player_hand)
    e.add_field(name="👤 Bài người chơi", value=fmt_hand(player_hand), inline=True)
    e.add_field(name=f"Điểm: {pl}", value="\u200b", inline=True)
    e.add_field(name="\u200b", value="\u200b", inline=True)

    if dealer_revealed is None:
        e.add_field(name="🏦 Nhà cái", value="🂠  🂠  🂠", inline=False)
    else:
        shown  = fmt_hand(dealer_revealed)
        hidden = "  🂠" * (3 - len(dealer_revealed))
        e.add_field(name="🏦 Nhà cái", value=shown + hidden, inline=False)

    if result: e.add_field(name="📢 Kết quả", value=result, inline=False)
    if net is not None:
        e.add_field(name="Net",    value=f"{CURRENCY} **{'+' if net>=0 else ''}{net:,}**", inline=True)
        e.add_field(name="Số dư",  value=coin(bal), inline=True)
    e.set_footer(text=f"Cược: {bet:,} {CURRENCY}  |  3 Tây👑 > 3 Đôi🎯 > 9 > ... > 0  |  Hòa → so chất ♥>♦>♣>♠")
    return e

class BaCayCtrl(discord.ui.View):
    """Control view — chỉ người chơi thấy"""
    def __init__(self, bot, bet, player_hand, dealer_hand, public_msg):
        super().__init__(timeout=90)
        self.db          = bot.db
        self.bet         = bet
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.public_msg  = public_msg   # message mọi người thấy
        self.uid         = None         # set sau khi biết uid

    @discord.ui.button(label="👀  Lật từng lá nhà cái!", style=discord.ButtonStyle.danger)
    async def reveal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.uid:
            return await warn(interaction, "❌ Đây không phải ván của bạn!", delay=3)

        await interaction.response.defer()
        button.disabled = True
        # Cập nhật ctrl (disable nút)
        await interaction.edit_original_response(view=self)

        # Lật từng lá nhà cái trên public embed
        revealed = []
        for i, card in enumerate(self.dealer_hand):
            for frame in FLIP:
                e = bacay_public_embed(self.player_hand, revealed, self.bet)
                e.add_field(name=f"Lá {i+1} đang lật...", value=frame, inline=False)
                await self.public_msg.edit(embed=e)
                await asyncio.sleep(0.28)
            revealed.append(card)
            await self.public_msg.edit(embed=bacay_public_embed(self.player_hand, revealed, self.bet))
            await asyncio.sleep(0.75)

        # Tính kết quả
        pr, pl = ba_cay_rank(self.player_hand)
        dr, dl = ba_cay_rank(self.dealer_hand)
        if pr > dr:
            won, result = True,  f"🎉 Người chơi thắng!\n👤 {pl}  vs  🏦 {dl}"
        elif dr > pr:
            won, result = False, f"😢 Nhà cái thắng!\n🏦 {dl}  vs  👤 {pl}"
        else:
            if ba_cay_tiebreak(self.player_hand, self.dealer_hand):
                won, result = True,  "🎉 Hòa điểm — người chơi thắng theo **chất bài**!"
            else:
                won, result = False, "😢 Hòa điểm — nhà cái thắng theo **chất bài**!"

        net = self.bet if won else -self.bet
        self.db.update_balance(self.uid, net)
        if net > 0: self.db.record_game(self.uid, net, 0)
        else:       self.db.record_game(self.uid, 0, abs(net))
        bal = self.db.get_user(self.uid)["balance"]

        color = 0x2ECC71 if won else 0xE74C3C
        title = "🃏  3 CÂY — THẮNG! 🎉" if won else "🃏  3 CÂY — THUA 😢"
        self.stop()
        await self.public_msg.edit(embed=bacay_public_embed(
            self.player_hand, self.dealer_hand, self.bet,
            result=result, net=net, bal=bal, color=color, title=title
        ))


# ═══════════════════════════════════════════════════════════════
#  🃏  LIÊNG
# ═══════════════════════════════════════════════════════════════
RANK_ORDER = {"3":1,"4":2,"5":3,"6":4,"7":5,"8":6,"9":7,
              "10":8,"J":9,"Q":10,"K":11,"A":12,"2":13}

def lieng_rv(card): return RANK_ORDER.get(card_rank(card), 0)

def lieng_type(hand):
    ranks  = sorted([lieng_rv(c) for c in hand])
    suits  = [card_suit(c) for c in hand]
    flush  = len(set(suits)) == 1
    st     = ranks[2]-ranks[1]==1 and ranks[1]-ranks[0]==1
    if sorted(ranks)==sorted([RANK_ORDER["A"],RANK_ORDER["2"],RANK_ORDER["3"]]): st=True
    triple = ranks[0]==ranks[1]==ranks[2]
    pair   = ranks[0]==ranks[1] or ranks[1]==ranks[2]
    if st and flush: return (7,"Sảnh Đồng Chất 🌈")
    if triple:       return (6,"Ba Đôi 🎯")
    if st:           return (5,"Sảnh ➡️")
    if flush:        return (4,"Thùng ♦️")
    if pair:         return (3,"Đôi 👥")
    return (1, f"Bài Cao {fmt(max(hand,key=lieng_rv))}")

def lieng_key(hand):
    ht,_ = lieng_type(hand)
    return (ht, *sorted([lieng_rv(c) for c in hand], reverse=True))

def lieng_public_embed(player_hand, bet, dealer_hand=None, result=None, net=None, bal=None,
                        color=0x6C3483, title="🃏  LIÊNG — 3 LÁ"):
    e = discord.Embed(title=title, color=color)
    _, pname = lieng_type(player_hand)
    e.add_field(name="👤 Bài người chơi", value=fmt_hand(player_hand), inline=True)
    e.add_field(name="Tay bài",           value=f"**{pname}**", inline=True)
    e.add_field(name="\u200b", value="\u200b", inline=True)
    if dealer_hand:
        _, dname = lieng_type(dealer_hand)
        e.add_field(name="🏦 Nhà cái", value=fmt_hand(dealer_hand), inline=True)
        e.add_field(name="Tay bài",    value=f"**{dname}**", inline=True)
    else:
        e.add_field(name="🏦 Nhà cái", value="🂠  🂠  🂠  *(úp)*", inline=False)
    if result: e.add_field(name="📢 Kết quả", value=result, inline=False)
    if net is not None:
        e.add_field(name="Net",   value=f"{CURRENCY} **{'+' if net>=0 else ''}{net:,}**", inline=True)
        e.add_field(name="Số dư", value=coin(bal), inline=True)
    e.set_footer(text=f"Cược: {bet:,} {CURRENCY}  |  Sảnh Đồng Chất > Ba Đôi > Sảnh > Thùng > Đôi > Bài Cao")
    return e

class LiengCtrl(discord.ui.View):
    def __init__(self, bot, bet, player_hand, dealer_hand, public_msg):
        super().__init__(timeout=90)
        self.db = bot.db; self.bet = bet
        self.player_hand = player_hand; self.dealer_hand = dealer_hand
        self.public_msg = public_msg; self.uid = None

    async def _resolve(self, interaction, folded):
        await interaction.response.defer()
        for child in self.children: child.disabled = True
        await interaction.edit_original_response(view=self)
        self.stop()

        if folded:
            net = -self.bet
            self.db.update_balance(self.uid, net)
            self.db.record_game(self.uid, 0, self.bet)
            bal = self.db.get_user(self.uid)["balance"]
            e = lieng_public_embed(self.player_hand, self.bet,
                dealer_hand=self.dealer_hand,
                result="🏳️ Người chơi **bỏ bài** — nhà cái thắng!",
                net=net, bal=bal, color=0x95A5A6, title="🃏  LIÊNG — BỎ BÀI")
            return await self.public_msg.edit(embed=e)

        # Flip animation on public msg
        for frame in FLIP:
            e = lieng_public_embed(self.player_hand, self.bet)
            e.add_field(name="🏦 Nhà cái lật...", value=frame, inline=False)
            await self.public_msg.edit(embed=e)
            await asyncio.sleep(0.32)

        pk = lieng_key(self.player_hand); dk = lieng_key(self.dealer_hand)
        _,pname = lieng_type(self.player_hand); _,dname = lieng_type(self.dealer_hand)
        if pk > dk:   won,result = True,  f"🎉 Người chơi thắng!\n👤 {pname}  vs  🏦 {dname}"
        elif dk > pk: won,result = False, f"😢 Nhà cái thắng!\n🏦 {dname}  vs  👤 {pname}"
        else:         won,result = False, "🤝 Hòa — nhà cái giữ tiền!"

        net = self.bet if won else -self.bet
        self.db.update_balance(self.uid, net)
        if net > 0: self.db.record_game(self.uid, net, 0)
        else:       self.db.record_game(self.uid, 0, abs(net))
        bal = self.db.get_user(self.uid)["balance"]
        color = 0x2ECC71 if won else 0xE74C3C
        title = "🃏  LIÊNG — THẮNG! 🎉" if won else "🃏  LIÊNG — THUA 😢"
        await self.public_msg.edit(embed=lieng_public_embed(
            self.player_hand, self.bet, dealer_hand=self.dealer_hand,
            result=result, net=net, bal=bal, color=color, title=title))

    @discord.ui.button(label="✅  Theo (Call)", style=discord.ButtonStyle.success)
    async def call(self, interaction, button):
        if interaction.user.id != self.uid:
            return await warn(interaction, "❌ Đây không phải ván của bạn!", delay=3)
        await self._resolve(interaction, folded=False)

    @discord.ui.button(label="🏳️  Bỏ (Fold)", style=discord.ButtonStyle.danger)
    async def fold(self, interaction, button):
        if interaction.user.id != self.uid:
            return await warn(interaction, "❌ Đây không phải ván của bạn!", delay=3)
        await self._resolve(interaction, folded=True)


# ═══════════════════════════════════════════════════════════════
#  🎴  XÌ DÁCH
# ═══════════════════════════════════════════════════════════════
def xi_val(card):
    r = card_rank(card)
    if r in ["J","Q","K"]: return 10
    if r == "A": return 11
    return int(r)

def xi_total(hand):
    total = sum(xi_val(c) for c in hand)
    aces  = sum(1 for c in hand if card_rank(c)=="A")
    while total > 21 and aces: total -= 10; aces -= 1
    return total

def xi_instant(hand):
    if len(hand)!=2: return None
    ranks = [card_rank(c) for c in hand]
    if ranks[0]==ranks[1]=="A": return "xi_ban"
    if "A" in ranks and any(r in ["J","Q","K","10"] for r in ranks): return "xi_dach"
    return None

def xidach_public_embed(player, dealer, bet, reveal=False, result=None, net=None, bal=None,
                         status="playing"):
    pv = xi_total(player); dv = xi_total(dealer)
    colors = {"playing":0x1A1A2E,"win":0x2ECC71,"lose":0xE74C3C,
              "push":0x95A5A6,"xi_dach":0xF4C430,"xi_ban":0xFF6B6B,"flip":0x3498DB}
    titles = {"playing":"🎴  XÌ DÁCH","win":"🎴  THẮNG! 🎉","lose":"🎴  THUA 😢",
              "push":"🎴  HÒA","xi_dach":"🎴  XÌ DÁCH! 🎊","xi_ban":"🎴  XÌ BÀN! 🔥",
              "flip":"🎴  NHÀ CÁI RÚT BÀI..."}
    e = discord.Embed(title=titles.get(status,"🎴 Xì Dách"), color=colors.get(status,0x1A1A2E))
    e.add_field(name=f"👤 Người chơi  [{pv}]", value=fmt_hand(player), inline=False)
    if reveal:
        e.add_field(name=f"🏦 Nhà cái  [{dv}]", value=fmt_hand(dealer), inline=False)
    else:
        e.add_field(name="🏦 Nhà cái  [?]", value=f"{fmt(dealer[0])}  🂠", inline=False)
    if result: e.add_field(name="📢 Kết quả", value=result, inline=False)
    if net is not None:
        e.add_field(name="Net",   value=f"{CURRENCY} **{'+' if net>=0 else ''}{net:,}**", inline=True)
        e.add_field(name="Số dư", value=coin(bal), inline=True)
    e.set_footer(text=f"Cược: {bet:,} {CURRENCY}  |  Xì Bàn(AA)=3x  Xì Dách=2x  Nhà cái rút ≤16")
    return e

class XiDachCtrl(discord.ui.View):
    def __init__(self, bot, bet, player, dealer, deck, public_msg):
        super().__init__(timeout=120)
        self.db=bot.db; self.bet=bet
        self.player=player; self.dealer=dealer; self.deck=deck
        self.public_msg=public_msg; self.uid=None

    async def dealer_draw(self):
        for frame in FLIP:
            e = xidach_public_embed(self.player, self.dealer, self.bet, status="flip")
            e.add_field(name="🏦 Nhà cái lật...", value=f"{fmt(self.dealer[0])}  {frame}", inline=False)
            await self.public_msg.edit(embed=e)
            await asyncio.sleep(0.32)
        while xi_total(self.dealer) <= 16:
            self.dealer.append(self.deck.pop())
            await self.public_msg.edit(embed=xidach_public_embed(self.player, self.dealer, self.bet, reveal=True, status="flip"))
            await asyncio.sleep(0.55)

    async def finish(self, interaction):
        pv=xi_total(self.player); dv=xi_total(self.dealer)
        if   pv>21:  status,result,net = "lose","💥 **Quá 21! Thua.**",           -self.bet
        elif dv>21:  status,result,net = "win", "💥 **Nhà cái quá 21! Thắng!**",   self.bet
        elif pv>dv:  status,result,net = "win", f"✅ **{pv} vs {dv} — Thắng!**",   self.bet
        elif pv==dv: status,result,net = "push",f"🤝 **Hòa {pv} — hoàn cược.**",   0
        else:        status,result,net = "lose",f"❌ **{dv} vs {pv} — Nhà cái thắng.**", -self.bet
        self.db.update_balance(self.uid, net)
        if net>0: self.db.record_game(self.uid, net, 0)
        elif net<0: self.db.record_game(self.uid, 0, abs(net))
        bal = self.db.get_user(self.uid)["balance"]
        for child in self.children: child.disabled=True
        self.stop()
        # Disable ctrl buttons
        try: await interaction.edit_original_response(view=self)
        except: pass
        await self.public_msg.edit(embed=xidach_public_embed(
            self.player, self.dealer, self.bet, reveal=True,
            result=result, net=net, bal=bal, status=status))

    async def draw_anim(self, interaction):
        """Card flip animation on public msg before drawing"""
        for frame in FLIP:
            e = xidach_public_embed(self.player, self.dealer, self.bet)
            e.add_field(name="Rút bài...", value=frame, inline=False)
            await self.public_msg.edit(embed=e)
            await asyncio.sleep(0.22)

    @discord.ui.button(label="👊  Rút (Hit)", style=discord.ButtonStyle.success)
    async def hit(self, interaction, button):
        if interaction.user.id!=self.uid:
            return await warn(interaction,"❌ Đây không phải ván của bạn!", delay=3)
        await interaction.response.defer()
        await self.draw_anim(interaction)
        self.player.append(self.deck.pop())
        if xi_total(self.player)>=21:
            await self.dealer_draw(); await self.finish(interaction)
        else:
            await self.public_msg.edit(embed=xidach_public_embed(self.player,self.dealer,self.bet))

    @discord.ui.button(label="✋  Dừng (Stand)", style=discord.ButtonStyle.danger)
    async def stand(self, interaction, button):
        if interaction.user.id!=self.uid:
            return await warn(interaction,"❌ Đây không phải ván của bạn!", delay=3)
        await interaction.response.defer()
        await self.dealer_draw(); await self.finish(interaction)

    @discord.ui.button(label="💰  Gấp Đôi", style=discord.ButtonStyle.primary)
    async def double(self, interaction, button):
        if interaction.user.id!=self.uid:
            return await warn(interaction,"❌ Đây không phải ván của bạn!", delay=3)
        if len(self.player)!=2:
            return await warn(interaction,"❌ Chỉ gấp đôi được ngay từ đầu!", delay=4)
        if self.db.get_user(self.uid)["balance"] < self.bet:
            return await warn(interaction,"❌ Không đủ tiền để gấp đôi!", delay=4)
        await interaction.response.defer()
        self.bet*=2
        await self.draw_anim(interaction)
        self.player.append(self.deck.pop())
        await self.public_msg.edit(embed=xidach_public_embed(self.player,self.dealer,self.bet))
        await asyncio.sleep(0.6)
        await self.dealer_draw(); await self.finish(interaction)

    async def on_timeout(self):
        for child in self.children: child.disabled=True


# ═══════════════════════════════════════════════════════════════
#  🀄  TIẾN LÊN
# ═══════════════════════════════════════════════════════════════
TL_ORDER = {"3":1,"4":2,"5":3,"6":4,"7":5,"8":6,"9":7,
            "10":8,"J":9,"Q":10,"K":11,"A":12,"2":13}
SUIT_VAL = {"♠":1,"♣":2,"♦":3,"♥":4}

def tl_key(c): return (TL_ORDER.get(card_rank(c),0), SUIT_VAL.get(card_suit(c),0))
def tl_sort(h): return sorted(h, key=tl_key)

def tl_combo(cards):
    if not cards: return None
    n=len(cards); ranks=[card_rank(c) for c in cards]
    vals=sorted(TL_ORDER.get(r,0) for r in ranks)
    if n==1: return "single"
    if n==2 and ranks[0]==ranks[1]: return "pair"
    if n==4 and len(set(ranks))==1: return "four"
    if n>=3:
        if len(set(vals))==n and all(vals[i]+1==vals[i+1] for i in range(n-1)): return "seq"
        if n%2==0:
            pairs=[(cards[i],cards[i+1]) for i in range(0,n,2)]
            if all(card_rank(p[0])==card_rank(p[1]) for p in pairs):
                pv=sorted(TL_ORDER.get(card_rank(p[0]),0) for p in pairs)
                if all(pv[i]+1==pv[i+1] for i in range(len(pv)-1)): return "pair_seq"
    return None

def tl_beats(prev, new):
    if tl_combo(prev)!=tl_combo(new): return False
    return max(tl_key(c) for c in new) > max(tl_key(c) for c in prev)

def bot_move(hand, current, ctype):
    hand=tl_sort(hand)
    if ctype=="single":
        for c in hand:
            if tl_beats(current,[c]): return [c]
    elif ctype=="pair":
        by_r={}
        for c in hand: by_r.setdefault(card_rank(c),[]).append(c)
        for r in sorted(by_r,key=lambda r:TL_ORDER.get(r,0)):
            if len(by_r[r])>=2:
                p=by_r[r][:2]
                if tl_beats(current,p): return p
    elif ctype=="seq":
        n=len(current)
        for i in range(len(hand)-n+1):
            seq=hand[i:i+n]
            vals=[TL_ORDER.get(card_rank(c),0) for c in seq]
            if all(vals[j]+1==vals[j+1] for j in range(n-1)):
                if tl_beats(current,seq): return seq
    return None

def tienlen_public_embed(player, bot_hand, current, selecting, bet, extra=None, status="playing"):
    colors={"playing":0x0D3B66,"win":0x2ECC71,"lose":0xE74C3C}
    e=discord.Embed(title="🀄  TIẾN LÊN — 1v1", color=colors.get(status,0x0D3B66))
    e.add_field(name=f"👤 Người chơi ({len(player)} lá)",
        value=fmt_hand(player) if player else "*Hết bài!*", inline=False)
    e.add_field(name=f"🤖 Bot ({len(bot_hand)} lá)",
        value=f"🂠 × {len(bot_hand)}" if bot_hand else "*Hết bài!*", inline=False)
    if current:
        e.add_field(name="🃏 Bài trên bàn", value=fmt_hand(current), inline=False)
    else:
        e.add_field(name="🃏 Bàn trống", value="*Người chơi đánh trước*", inline=False)
    if selecting:
        e.add_field(name="✅ Đang chuẩn bị đánh", value=fmt_hand(selecting), inline=False)
    if extra:
        e.add_field(name="📢", value=extra, inline=False)
    e.set_footer(text=f"Cược: {bet:,} {CURRENCY}  |  3 thấp → 2 cao  |  Đơn / Đôi / Bộ liên tiếp")
    return e

class TLSelectMenu(discord.ui.Select):
    def __init__(self, view_ref):
        self.vr = view_ref
        hand = view_ref.player
        options = []
        for c in tl_sort(hand):
            r=card_rank(c); s=card_suit(c)
            label=f"{r}{SUIT_EMO.get(s,s)}"
            options.append(discord.SelectOption(
                label=label, value=c,
                description="✅ Đã chọn" if c in view_ref.selecting else f"Rank {TL_ORDER.get(r,0)}",
                default=(c in view_ref.selecting),
                emoji="✅" if c in view_ref.selecting else None
            ))
        super().__init__(
            placeholder="🃏 Chọn lá bài muốn đánh...",
            min_values=1, max_values=min(len(hand),10),
            options=options[:25], row=0
        )
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id!=self.vr.uid:
            return await warn(interaction,"❌ Đây không phải ván của bạn!", delay=3)
        self.vr.selecting=list(self.values)
        self.vr._rebuild_select()
        # Update ctrl (dropdown) + public (show selecting)
        await self.vr.public_msg.edit(embed=tienlen_public_embed(
            self.vr.player, self.vr.bot_hand, self.vr.current,
            self.vr.selecting, self.vr.bet))
        await interaction.response.edit_message(view=self.vr)

class TienLenCtrl(discord.ui.View):
    def __init__(self, bot, bet, player_hand, bot_hand, public_msg):
        super().__init__(timeout=300)
        self.db=bot.db; self.bet=bet
        self.player=tl_sort(player_hand); self.bot_hand=tl_sort(bot_hand)
        self.public_msg=public_msg; self.uid=None
        self.current=None; self.ctype=None; self.selecting=[]
        self._rebuild_select()

    def _rebuild_select(self):
        for c in [x for x in self.children if isinstance(x,TLSelectMenu)]: self.remove_item(c)
        if self.player: self.add_item(TLSelectMenu(self))

    async def _sync(self, interaction, extra=None):
        """Update both public embed and ctrl view"""
        await self.public_msg.edit(embed=tienlen_public_embed(
            self.player, self.bot_hand, self.current, self.selecting, self.bet, extra=extra))
        self._rebuild_select()
        try: await interaction.edit_original_response(view=self)
        except: pass

    @discord.ui.button(label="⚡  Đánh!", style=discord.ButtonStyle.success, row=1)
    async def play_btn(self, interaction, button):
        if interaction.user.id!=self.uid:
            return await warn(interaction,"❌ Đây không phải ván của bạn!", delay=3)
        if not self.selecting:
            return await warn(interaction,"❌ Chưa chọn lá nào! Dùng dropdown bên trên.", delay=4)
        ct=tl_combo(self.selecting)
        if not ct:
            return await warn(interaction,"❌ Bộ bài không hợp lệ! (đơn/đôi/bộ liên tiếp)", delay=5)
        if self.current and not tl_beats(self.current, self.selecting):
            return await warn(interaction,"❌ Bài không đủ mạnh!", delay=4)

        for c in self.selecting: self.player.remove(c)
        self.current=self.selecting[:]; self.ctype=ct; self.selecting=[]

        await interaction.response.defer()
        if not self.player:
            return await self._end(interaction, won=True)

        await self._sync(interaction)
        await asyncio.sleep(0.8)

        bmove=bot_move(self.bot_hand, self.current, self.ctype)
        if bmove:
            for c in bmove: self.bot_hand.remove(c)
            self.current=bmove; self.ctype=tl_combo(bmove)
            extra=f"🤖 Bot đánh: {fmt_hand(bmove)}"
            await self._sync(interaction, extra=extra)
            if not self.bot_hand:
                await asyncio.sleep(0.6)
                return await self._end(interaction, won=False)
        else:
            self.current=None; self.ctype=None
            extra="🤖 Bot **bỏ lượt** — bàn trống, bạn đánh trước!"
            await self._sync(interaction, extra=extra)

    @discord.ui.button(label="🏳️  Bỏ lượt (Pass)", style=discord.ButtonStyle.secondary, row=1)
    async def pass_btn(self, interaction, button):
        if interaction.user.id!=self.uid:
            return await warn(interaction,"❌ Đây không phải ván của bạn!", delay=3)
        if not self.current:
            return await warn(interaction,"❌ Bàn trống — phải đánh bài!", delay=4)
        self.selecting=[]
        await interaction.response.defer()
        await asyncio.sleep(0.4)
        if self.bot_hand:
            lead=tl_sort(self.bot_hand)[0]
            self.bot_hand.remove(lead)
            self.current=[lead]; self.ctype="single"
            extra=f"🤖 Bot dẫn đầu: {fmt(lead)}"
            await self._sync(interaction, extra=extra)
            if not self.bot_hand:
                await asyncio.sleep(0.6)
                return await self._end(interaction, won=False)
        await asyncio.sleep(0.3)
        await self._sync(interaction)

    @discord.ui.button(label="🗑️  Bỏ chọn", style=discord.ButtonStyle.danger, row=1)
    async def clear_btn(self, interaction, button):
        if interaction.user.id!=self.uid:
            return await warn(interaction,"❌ Đây không phải ván của bạn!", delay=3)
        self.selecting=[]
        self._rebuild_select()
        await self.public_msg.edit(embed=tienlen_public_embed(
            self.player, self.bot_hand, self.current, self.selecting, self.bet))
        await interaction.response.edit_message(view=self)

    async def _end(self, interaction, won):
        for child in self.children: child.disabled=True
        self.stop()
        net=self.bet if won else -self.bet
        self.db.update_balance(self.uid, net)
        if net>0: self.db.record_game(self.uid, net, 0)
        else:     self.db.record_game(self.uid, 0, abs(net))
        bal=self.db.get_user(self.uid)["balance"]
        net_str=f"+{net:,}" if net>=0 else f"{net:,}"
        color=0x2ECC71 if won else 0xE74C3C
        result="🎉 **Người chơi thắng! Đánh hết bài trước!**" if won else "😢 **Bot thắng!**"
        e=discord.Embed(title="🀄  TIẾN LÊN — KẾT THÚC",color=color)
        e.add_field(name="Kết quả",value=result,inline=False)
        e.add_field(name="Net",value=f"{CURRENCY} **{net_str}**",inline=True)
        e.add_field(name="Số dư",value=coin(bal),inline=True)
        await self.public_msg.edit(embed=e)
        try: await interaction.edit_original_response(view=self)
        except: pass

    async def on_timeout(self):
        for child in self.children: child.disabled=True


# ═══════════════════════════════════════════════════════════════
#  COG
# ═══════════════════════════════════════════════════════════════
class VietCards(commands.Cog):
    def __init__(self, bot):
        self.bot=bot; self.db=bot.db

    # ── /bacay ────────────────────────────────────────────
    @app_commands.command(name="bacay", description="🃏 Chơi 3 Cây (Bài Cào)")
    @app_commands.describe(bet="Số tiền cược")
    async def bacay(self, interaction: discord.Interaction, bet: int):
        data=self.db.get_user(interaction.user.id, interaction.user.display_name)
        err=clamp_bet(bet, data["balance"])
        if err:
            return await interaction.response.send_message(err, ephemeral=True, delete_after=5)

        deck=make_deck()
        ph=[deck.pop() for _ in range(3)]
        dh=[deck.pop() for _ in range(3)]

        # 1. Gửi public embed (mọi người thấy, không nút)
        await interaction.response.send_message(embed=bacay_public_embed(ph, None, bet))
        public_msg = await interaction.original_response()

        # 2. Gửi ctrl riêng cho người chơi (ephemeral, có nút)
        view=BaCayCtrl(self.bot, bet, ph, dh, public_msg)
        view.uid=interaction.user.id
        await interaction.followup.send(
            "🎮 **Điều khiển của bạn** — chỉ mình bạn thấy:",
            view=view, ephemeral=True
        )

    # ── /lieng ────────────────────────────────────────────
    @app_commands.command(name="lieng", description="🃏 Chơi Liêng — 3 lá so tay bài!")
    @app_commands.describe(bet="Số tiền cược")
    async def lieng(self, interaction: discord.Interaction, bet: int):
        data=self.db.get_user(interaction.user.id, interaction.user.display_name)
        err=clamp_bet(bet, data["balance"])
        if err:
            return await interaction.response.send_message(err, ephemeral=True, delete_after=5)

        deck=make_deck()
        ph=[deck.pop() for _ in range(3)]
        dh=[deck.pop() for _ in range(3)]

        await interaction.response.send_message(embed=lieng_public_embed(ph, bet))
        public_msg=await interaction.original_response()

        view=LiengCtrl(self.bot, bet, ph, dh, public_msg)
        view.uid=interaction.user.id
        await interaction.followup.send(
            "🎮 **Điều khiển của bạn** — chỉ mình bạn thấy:",
            view=view, ephemeral=True
        )

    # ── /xidach ───────────────────────────────────────────
    @app_commands.command(name="xidach", description="🎴 Chơi Xì Dách — Blackjack Việt Nam!")
    @app_commands.describe(bet="Số tiền cược")
    async def xidach(self, interaction: discord.Interaction, bet: int):
        data=self.db.get_user(interaction.user.id, interaction.user.display_name)
        err=clamp_bet(bet, data["balance"])
        if err:
            return await interaction.response.send_message(err, ephemeral=True, delete_after=5)

        deck=make_deck()
        player,dealer=[],[]

        # Gửi public embed trước
        e=discord.Embed(title="🎴  XÌ DÁCH — CHIA BÀI...",color=0x1A1A2E)
        e.add_field(name="Đang chia bài...",value="🂠 🂠 🂠 🂠",inline=False)
        await interaction.response.send_message(embed=e)
        public_msg=await interaction.original_response()
        await asyncio.sleep(0.5)

        for i in range(4):
            if i%2==0: player.append(deck.pop())
            else:       dealer.append(deck.pop())
            de=discord.Embed(title="🎴  CHIA BÀI...",color=0x1A1A2E)
            de.add_field(name=f"👤 Người chơi [{xi_total(player)}]",
                value=fmt_hand(player) if player else "🂠",inline=False)
            de.add_field(name="🏦 Nhà cái [?]",
                value=(fmt_hand(dealer)+"  🂠") if len(dealer)==1 else fmt_hand(dealer[:1])+"  🂠" if dealer else "🂠",
                inline=False)
            de.set_footer(text=f"Cược: {bet:,} {CURRENCY}")
            await public_msg.edit(embed=de)
            await asyncio.sleep(0.4)

        view=XiDachCtrl(self.bot, bet, player, dealer, deck, public_msg)
        view.uid=interaction.user.id

        instant=xi_instant(player)
        if instant=="xi_ban":
            while xi_total(dealer)<=16: dealer.append(deck.pop())
            net=bet*2
            view.db.update_balance(interaction.user.id, net)
            view.db.record_game(interaction.user.id, net, 0)
            bal=view.db.get_user(interaction.user.id)["balance"]
            await public_msg.edit(embed=xidach_public_embed(player,dealer,bet,reveal=True,
                result="🔥 **Xì Bàn! AA! Thắng 3x!**",net=net,bal=bal,status="xi_ban"))
            return
        elif instant=="xi_dach":
            while xi_total(dealer)<=16: dealer.append(deck.pop())
            di=xi_instant(dealer)
            if di=="xi_dach": net,result,status=0,"🤝 **Cả hai Xì Dách — Hòa!**","push"
            else:              net,result,status=bet,"🎊 **Xì Dách! Thắng 2x!**","xi_dach"
            view.db.update_balance(interaction.user.id, net)
            if net>0: view.db.record_game(interaction.user.id, net, 0)
            bal=view.db.get_user(interaction.user.id)["balance"]
            await public_msg.edit(embed=xidach_public_embed(player,dealer,bet,reveal=True,
                result=result,net=net,bal=bal,status=status))
            return

        await public_msg.edit(embed=xidach_public_embed(player,dealer,bet))
        await interaction.followup.send(
            "🎮 **Điều khiển của bạn** — chỉ mình bạn thấy:",
            view=view, ephemeral=True
        )

    # ── /tienlen ──────────────────────────────────────────
    @app_commands.command(name="tienlen", description="🀄 Tiến Lên 1v1 với Bot!")
    @app_commands.describe(bet="Số tiền cược")
    async def tienlen(self, interaction: discord.Interaction, bet: int):
        data=self.db.get_user(interaction.user.id, interaction.user.display_name)
        err=clamp_bet(bet, data["balance"])
        if err:
            return await interaction.response.send_message(err, ephemeral=True, delete_after=5)

        deck=make_deck()
        ph=[deck.pop() for _ in range(13)]
        bh=[deck.pop() for _ in range(13)]

        view=TienLenCtrl(self.bot, bet, ph, bh, None)
        view.uid=interaction.user.id

        await interaction.response.send_message(embed=tienlen_public_embed(
            view.player, view.bot_hand, None, [], bet))
        public_msg=await interaction.original_response()
        view.public_msg=public_msg

        await interaction.followup.send(
            "🎮 **Điều khiển của bạn** — chỉ mình bạn thấy:\n"
            "*(Dùng dropdown chọn bài, rồi ấn Đánh!)*",
            view=view, ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(VietCards(bot))
