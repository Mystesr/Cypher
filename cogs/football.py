"""
⚽ FOOTBALL BETTING MODULE
API: api-football.com (free tier — 100 req/day)
Đăng ký: https://dashboard.api-football.com/register

Các loại kèo:
  Kèo chính:
    1x2       — Châu Âu: Thắng/Hòa/Thua
    handicap  — Châu Á: chấp bàn (0 / 0.25 / 0.5 / 0.75 / 1 / 1.25 / 1.5)
    ou_goals  — Tài Xỉu bàn thắng (1.5 / 2 / 2.5 / 3 / 3.5)

  Kèo phụ:
    btts      — Cả hai đội ghi bàn (Yes/No)
    exact     — Tỷ số chính xác (tỷ lệ cao)
    odd_even  — Tổng bàn Chẵn/Lẻ

  Kèo phạt góc:
    ou_corner — Tài Xỉu phạt góc (8.5 / 9.5 / 10.5 / 11.5)
    corner_1x2 — Đội nào nhiều phạt góc hơn (1/X/2)

  Kèo thẻ phạt:
    ou_card   — Tài Xỉu thẻ (thẻ vàng=1đ, thẻ đỏ=2đ, ngưỡng: 2.5/3.5/4.5)
    has_red   — Có thẻ đỏ không (Yes/No)

Thanh toán kèo: tự động khi owner nhập kết quả /matchresult
"""

import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import os
import json
from datetime import datetime, timezone

CURRENCY = "🪙"
API_KEY  = os.getenv("FOOTBALL_API_KEY", "")
BASE_URL = "https://v3.football.api-sports.io"

def coin(n): return f"{CURRENCY} **{n:,}**"

# ─── payout multipliers (house edge ~5%) ─────────────────────
PAYOUTS = {
    # 1x2
    "1x2_1": 2.0, "1x2_x": 3.2, "1x2_2": 2.0,
    # handicap (simplified: cửa chấp = 1.9x, cửa được chấp = 1.9x)
    "hcp_over": 1.9, "hcp_under": 1.9,
    # tài xỉu bàn thắng
    "ou_goals_tai": 1.9, "ou_goals_xiu": 1.9,
    # btts
    "btts_yes": 1.8, "btts_no": 1.8,
    # exact score (cao vì khó)
    "exact": 8.0,
    # chẵn lẻ
    "odd_even_chan": 1.9, "odd_even_le": 1.9,
    # tài xỉu phạt góc
    "ou_corner_tai": 1.9, "ou_corner_xiu": 1.9,
    # corner 1x2
    "corner_1x2_1": 2.0, "corner_1x2_x": 3.0, "corner_1x2_2": 2.0,
    # tài xỉu thẻ phạt
    "ou_card_tai": 1.9, "ou_card_xiu": 1.9,
    # có thẻ đỏ
    "has_red_yes": 4.0, "has_red_no": 1.25,
}

BET_TYPES = {
    "1x2":        "🌍 Kèo Châu Âu (Thắng/Hòa/Thua)",
    "handicap":   "🌏 Kèo Châu Á (Handicap chấp bàn)",
    "ou_goals":   "📊 Tài Xỉu Bàn Thắng",
    "btts":       "⚽ Cả Hai Đội Ghi Bàn",
    "exact":      "🎯 Tỷ Số Chính Xác",
    "odd_even":   "🔢 Tổng Bàn Chẵn/Lẻ",
    "ou_corner":  "🚩 Tài Xỉu Phạt Góc",
    "corner_1x2": "🚩 Đội Nào Nhiều Phạt Góc Hơn",
    "ou_card":    "🟨 Tài Xỉu Thẻ Phạt",
    "has_red":    "🟥 Có Thẻ Đỏ Không",
}

# ─── API helpers ──────────────────────────────────────────────
async def api_get(endpoint: str, params: dict = None):
    headers = {"x-apisports-key": API_KEY}
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{BASE_URL}/{endpoint}", headers=headers, params=params or {}) as r:
            if r.status != 200:
                return None
            data = await r.json()
            return data.get("response", [])

async def search_teams(query: str):
    """Tìm danh sách đội bóng theo tên"""
    return await api_get("teams", {"search": query}) or []

async def search_fixtures(team_id: int):
    """
    Lấy trận tiếp theo của một đội theo team_id.
    Dùng next=10 để lấy tối đa 10 trận sắp tới.
    """
    fixtures = await api_get("fixtures", {
        "team": team_id,
        "next": 10,
        "timezone": "Asia/Ho_Chi_Minh"
    })
    if not fixtures:
        # fallback với season
        current_season = datetime.now(timezone.utc).year
        fixtures = await api_get("fixtures", {
            "team": team_id,
            "season": current_season,
            "timezone": "Asia/Ho_Chi_Minh",
            "status": "NS"
        })
    return fixtures or []

async def get_fixture(fixture_id: int):
    res = await api_get("fixtures", {"id": fixture_id})
    return res[0] if res else None

async def get_fixture_stats(fixture_id: int):
    """Lấy thống kê sau trận (bàn thắng, phạt góc, thẻ)"""
    fix = await get_fixture(fixture_id)
    if not fix: return None
    stats_res = await api_get("fixtures/statistics", {"fixture": fixture_id})
    events_res = await api_get("fixtures/events", {"fixture": fixture_id})
    return {
        "fixture": fix,
        "stats": stats_res or [],
        "events": events_res or [],
    }

# ─── DB helpers (extend existing DB) ─────────────────────────
def db_create_bet_tables(db):
    c = db.conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS football_matches (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            fixture_id  INTEGER UNIQUE,
            home_team   TEXT,
            away_team   TEXT,
            league      TEXT,
            match_time  TEXT,
            status      TEXT DEFAULT 'open',
            result_data TEXT DEFAULT NULL,
            created_by  INTEGER,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS football_bets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id    INTEGER,
            user_id     INTEGER,
            bet_type    TEXT,
            bet_choice  TEXT,
            bet_param   TEXT DEFAULT NULL,
            amount      INTEGER,
            payout_mult REAL,
            status      TEXT DEFAULT 'pending',
            payout      INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now'))
        );
    """)
    db.conn.commit()

def db_add_match(db, fixture_id, home, away, league, match_time, created_by):
    c = db.conn.cursor()
    c.execute("""
        INSERT OR IGNORE INTO football_matches
        (fixture_id, home_team, away_team, league, match_time, created_by)
        VALUES (?,?,?,?,?,?)
    """, (fixture_id, home, away, league, match_time, created_by))
    db.conn.commit()
    c.execute("SELECT id FROM football_matches WHERE fixture_id=?", (fixture_id,))
    r = c.fetchone()
    return r["id"] if r else None

def db_get_match(db, match_id):
    c = db.conn.cursor()
    c.execute("SELECT * FROM football_matches WHERE id=?", (match_id,))
    r = c.fetchone()
    return dict(r) if r else None

def db_get_open_matches(db):
    c = db.conn.cursor()
    c.execute("SELECT * FROM football_matches WHERE status='open' ORDER BY match_time")
    return [dict(r) for r in c.fetchall()]

def db_place_bet(db, match_id, user_id, bet_type, choice, param, amount, mult):
    c = db.conn.cursor()
    c.execute("""
        INSERT INTO football_bets
        (match_id, user_id, bet_type, bet_choice, bet_param, amount, payout_mult)
        VALUES (?,?,?,?,?,?,?)
    """, (match_id, user_id, bet_type, choice, param, amount, mult))
    db.conn.commit()
    return c.lastrowid

def db_get_match_bets(db, match_id):
    c = db.conn.cursor()
    c.execute("SELECT * FROM football_bets WHERE match_id=?", (match_id,))
    return [dict(r) for r in c.fetchall()]

def db_user_bet_on_match(db, user_id, match_id, bet_type):
    c = db.conn.cursor()
    c.execute("""SELECT id FROM football_bets
                 WHERE user_id=? AND match_id=? AND bet_type=? AND status='pending'""",
              (user_id, match_id, bet_type))
    return c.fetchone() is not None

def db_settle_match(db, match_id, result_data: dict):
    c = db.conn.cursor()
    c.execute("UPDATE football_matches SET status='settled', result_data=? WHERE id=?",
              (json.dumps(result_data), match_id))
    db.conn.commit()

def db_settle_bet(db, bet_id, status, payout):
    c = db.conn.cursor()
    c.execute("UPDATE football_bets SET status=?, payout=? WHERE id=?",
              (status, payout, bet_id))
    db.conn.commit()

# ─── Result evaluation ────────────────────────────────────────
def evaluate_bet(bet: dict, result: dict) -> tuple[bool, int]:
    """
    result dict keys:
      goals_home, goals_away,
      corners_home, corners_away,
      yellow_home, yellow_away,
      red_home, red_away
    Returns (won: bool, payout: int)
    """
    t      = bet["bet_type"]
    choice = bet["bet_choice"]
    param  = bet["bet_param"]
    amount = bet["amount"]
    mult   = bet["payout_mult"]

    gh = result["goals_home"]; ga = result["goals_away"]
    ch = result.get("corners_home", 0); ca = result.get("corners_away", 0)
    yh = result.get("yellow_home", 0); ya = result.get("yellow_away", 0)
    rh = result.get("red_home", 0);    ra = result.get("red_away", 0)
    total_goals   = gh + ga
    total_corners = ch + ca
    # card points: vàng=1đ, đỏ=2đ (mỗi cầu thủ max 3đ)
    total_cards   = yh + ya + (rh + ra) * 2
    has_red       = (rh + ra) > 0

    won = False
    if t == "1x2":
        if   choice == "1" and gh > ga: won = True
        elif choice == "x" and gh == ga: won = True
        elif choice == "2" and ga > gh: won = True

    elif t == "handicap":
        # param = "home:0.5" hoặc "away:1.0" (đội được chấp : mức chấp)
        # choice = "over" (đội chấp thắng sau khi cộng chấp) / "under"
        fav, hcp = param.split(":")
        hcp = float(hcp)
        if fav == "home":
            diff = gh - ga - hcp   # home phải thắng hơn hcp
        else:
            diff = ga - gh - hcp   # away phải thắng hơn hcp
        if choice == "over":
            won = diff > 0
        elif choice == "under":
            won = diff < 0
        # diff == 0 → hoàn tiền (hòa kèo) → won stays False but payout = amount

    elif t == "ou_goals":
        line = float(param)
        if   choice == "tai"  and total_goals > line: won = True
        elif choice == "xiu"  and total_goals < line: won = True
        elif total_goals == line: won = None  # hoàn tiền

    elif t == "btts":
        scored_both = gh > 0 and ga > 0
        if   choice == "yes" and scored_both:  won = True
        elif choice == "no"  and not scored_both: won = True

    elif t == "exact":
        # param = "2:1"
        eh, ea = map(int, param.split(":"))
        won = (gh == eh and ga == ea)

    elif t == "odd_even":
        is_even = total_goals % 2 == 0
        if   choice == "chan" and is_even:      won = True
        elif choice == "le"   and not is_even:  won = True

    elif t == "ou_corner":
        line = float(param)
        if   choice == "tai" and total_corners > line: won = True
        elif choice == "xiu" and total_corners < line: won = True
        elif total_corners == line: won = None

    elif t == "corner_1x2":
        if   choice == "1" and ch > ca:  won = True
        elif choice == "x" and ch == ca: won = True
        elif choice == "2" and ca > ch:  won = True

    elif t == "ou_card":
        line = float(param)
        if   choice == "tai" and total_cards > line: won = True
        elif choice == "xiu" and total_cards < line: won = True
        elif total_cards == line: won = None

    elif t == "has_red":
        if   choice == "yes" and has_red:  won = True
        elif choice == "no"  and not has_red: won = True

    if won is None:   # hoàn tiền
        return "refund", amount
    if won:
        return "won", int(amount * mult)
    return "lost", 0

# ─── Embeds ───────────────────────────────────────────────────
def match_embed(m: dict, bets: list = None):
    status_ico = {"open":"🟢","settled":"✅","cancelled":"❌"}.get(m["status"],"⚪")
    e = discord.Embed(
        title=f"⚽  {m['home_team']}  vs  {m['away_team']}",
        description=f"🏆 {m['league']}\n🕐 {m['match_time']}  •  {status_ico} {m['status'].upper()}",
        color=0x2ECC71 if m["status"]=="open" else 0x95A5A6
    )
    e.add_field(name="Match ID", value=f"`#{m['id']}`", inline=True)
    if bets:
        total_pool = sum(b["amount"] for b in bets)
        e.add_field(name="Tổng cược", value=coin(total_pool), inline=True)
        e.add_field(name="Số kèo", value=f"**{len(bets)}**", inline=True)
    if m.get("result_data"):
        r = json.loads(m["result_data"])
        e.add_field(
            name="📊 Kết quả",
            value=(
                f"⚽ Bàn thắng: **{r['goals_home']} - {r['goals_away']}**\n"
                f"🚩 Phạt góc: **{r.get('corners_home',0)} - {r.get('corners_away',0)}**\n"
                f"🟨 Thẻ vàng: **{r.get('yellow_home',0)} - {r.get('yellow_away',0)}**\n"
                f"🟥 Thẻ đỏ: **{r.get('red_home',0)} - {r.get('red_away',0)}**"
            ),
            inline=False
        )
    e.set_footer(text="Dùng /bet để đặt kèo  |  /matchresult để nhập kết quả")
    return e

# ─── Select menus for bet placement ──────────────────────────
class BetTypeSelect(discord.ui.Select):
    def __init__(self, match_id):
        self.match_id = match_id
        options = [
            discord.SelectOption(label="🌍 Kèo Châu Âu (1X2)",        value="1x2",        description="Thắng / Hòa / Thua"),
            discord.SelectOption(label="🌏 Kèo Châu Á (Handicap)",     value="handicap",   description="Chấp bàn"),
            discord.SelectOption(label="📊 Tài Xỉu Bàn Thắng",         value="ou_goals",   description="Over/Under goals"),
            discord.SelectOption(label="⚽ Cả Hai Đội Ghi Bàn",        value="btts",       description="BTTS Yes/No"),
            discord.SelectOption(label="🎯 Tỷ Số Chính Xác",           value="exact",      description="Đoán đúng tỷ số (x8)"),
            discord.SelectOption(label="🔢 Chẵn/Lẻ Bàn Thắng",        value="odd_even",   description="Tổng bàn Chẵn hay Lẻ"),
            discord.SelectOption(label="🚩 Tài Xỉu Phạt Góc",          value="ou_corner",  description="Over/Under corners"),
            discord.SelectOption(label="🚩 Đội Nhiều Phạt Góc Hơn",    value="corner_1x2", description="1/X/2 corners"),
            discord.SelectOption(label="🟨 Tài Xỉu Thẻ Phạt",          value="ou_card",    description="Vàng=1đ Đỏ=2đ"),
            discord.SelectOption(label="🟥 Có Thẻ Đỏ Không",           value="has_red",    description="Yes/No red card"),
        ]
        super().__init__(placeholder="Chọn loại kèo muốn cược...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        view: BetView = self.view
        view.bet_type = self.values[0]
        view.step = "choice"
        view.clear_items()
        view.add_item(BetChoiceSelect(self.match_id, view.bet_type, view.match))
        await interaction.response.edit_message(
            embed=view.step_embed(), view=view
        )

class BetChoiceSelect(discord.ui.Select):
    def __init__(self, match_id, bet_type, match):
        self.match_id = match_id
        self.bet_type = bet_type
        home = match["home_team"]; away = match["away_team"]

        opts_map = {
            "1x2": [
                discord.SelectOption(label=f"1️⃣ {home} thắng",  value="1"),
                discord.SelectOption(label="🤝 Hòa",             value="x"),
                discord.SelectOption(label=f"2️⃣ {away} thắng",  value="2"),
            ],
            "handicap": [
                discord.SelectOption(label=f"{home} chấp 0.25", value="home:0.25|over"),
                discord.SelectOption(label=f"{home} chấp 0.5",  value="home:0.5|over"),
                discord.SelectOption(label=f"{home} chấp 0.75", value="home:0.75|over"),
                discord.SelectOption(label=f"{home} chấp 1.0",  value="home:1.0|over"),
                discord.SelectOption(label=f"{away} chấp 0.25", value="away:0.25|over"),
                discord.SelectOption(label=f"{away} chấp 0.5",  value="away:0.5|over"),
                discord.SelectOption(label=f"Đồng banh (0)",    value="home:0|over"),
            ],
            "ou_goals": [
                discord.SelectOption(label="Tài 1.5 (>1 bàn)",   value="tai|1.5"),
                discord.SelectOption(label="Xỉu 1.5 (≤1 bàn)",   value="xiu|1.5"),
                discord.SelectOption(label="Tài 2.5 (>2 bàn)",   value="tai|2.5"),
                discord.SelectOption(label="Xỉu 2.5 (≤2 bàn)",   value="xiu|2.5"),
                discord.SelectOption(label="Tài 3.5 (>3 bàn)",   value="tai|3.5"),
                discord.SelectOption(label="Xỉu 3.5 (≤3 bàn)",   value="xiu|3.5"),
            ],
            "btts": [
                discord.SelectOption(label="✅ Có — Cả 2 đội ghi bàn", value="yes"),
                discord.SelectOption(label="❌ Không",                   value="no"),
            ],
            "exact": [
                discord.SelectOption(label="1-0", value="1:0"), discord.SelectOption(label="2-0", value="2:0"),
                discord.SelectOption(label="2-1", value="2:1"), discord.SelectOption(label="3-0", value="3:0"),
                discord.SelectOption(label="3-1", value="3:1"), discord.SelectOption(label="3-2", value="3:2"),
                discord.SelectOption(label="0-0", value="0:0"), discord.SelectOption(label="1-1", value="1:1"),
                discord.SelectOption(label="2-2", value="2:2"), discord.SelectOption(label="0-1", value="0:1"),
                discord.SelectOption(label="0-2", value="0:2"), discord.SelectOption(label="1-2", value="1:2"),
            ],
            "odd_even": [
                discord.SelectOption(label="🔵 Chẵn (0, 2, 4...)", value="chan"),
                discord.SelectOption(label="🔴 Lẻ (1, 3, 5...)",   value="le"),
            ],
            "ou_corner": [
                discord.SelectOption(label="Tài 8.5 (≥9 góc)",   value="tai|8.5"),
                discord.SelectOption(label="Xỉu 8.5 (≤8 góc)",   value="xiu|8.5"),
                discord.SelectOption(label="Tài 9.5 (≥10 góc)",  value="tai|9.5"),
                discord.SelectOption(label="Xỉu 9.5 (≤9 góc)",   value="xiu|9.5"),
                discord.SelectOption(label="Tài 10.5 (≥11 góc)", value="tai|10.5"),
                discord.SelectOption(label="Xỉu 10.5 (≤10 góc)", value="xiu|10.5"),
                discord.SelectOption(label="Tài 11.5 (≥12 góc)", value="tai|11.5"),
                discord.SelectOption(label="Xỉu 11.5 (≤11 góc)", value="xiu|11.5"),
            ],
            "corner_1x2": [
                discord.SelectOption(label=f"🚩 {home} nhiều hơn", value="1"),
                discord.SelectOption(label="🤝 Bằng nhau",         value="x"),
                discord.SelectOption(label=f"🚩 {away} nhiều hơn", value="2"),
            ],
            "ou_card": [
                discord.SelectOption(label="Tài 2.5 điểm thẻ",  value="tai|2.5"),
                discord.SelectOption(label="Xỉu 2.5 điểm thẻ",  value="xiu|2.5"),
                discord.SelectOption(label="Tài 3.5 điểm thẻ",  value="tai|3.5"),
                discord.SelectOption(label="Xỉu 3.5 điểm thẻ",  value="xiu|3.5"),
                discord.SelectOption(label="Tài 4.5 điểm thẻ",  value="tai|4.5"),
                discord.SelectOption(label="Xỉu 4.5 điểm thẻ",  value="xiu|4.5"),
            ],
            "has_red": [
                discord.SelectOption(label="🟥 Có — Xuất hiện ít nhất 1 thẻ đỏ (x4)", value="yes"),
                discord.SelectOption(label="✅ Không — Không có thẻ đỏ (x1.25)",       value="no"),
            ],
        }
        super().__init__(
            placeholder="Chọn cửa cược...",
            options=opts_map.get(bet_type, [discord.SelectOption(label="N/A", value="na")]),
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        view: BetView = self.view
        raw = self.values[0]

        # Parse choice & param
        if self.bet_type == "handicap":
            param_raw, choice = raw.rsplit("|", 1)
            view.bet_choice = choice
            view.bet_param  = param_raw
        elif self.bet_type in ("ou_goals", "ou_corner", "ou_card"):
            choice, param = raw.split("|")
            view.bet_choice = choice
            view.bet_param  = param
        elif self.bet_type == "exact":
            view.bet_choice = raw
            view.bet_param  = raw
        else:
            view.bet_choice = raw
            view.bet_param  = None

        view.step = "amount"
        view.clear_items()
        # Amount buttons
        for amt in [100, 500, 1000, 5000, 10000]:
            view.add_item(AmountButton(amt))
        view.add_item(ConfirmButton())
        view.add_item(CancelButton())
        await interaction.response.edit_message(embed=view.step_embed(), view=view)

class AmountButton(discord.ui.Button):
    def __init__(self, amount):
        super().__init__(label=f"{amount:,} 🪙", style=discord.ButtonStyle.secondary, row=1)
        self.amount = amount
    async def callback(self, interaction: discord.Interaction):
        view: BetView = self.view
        view.bet_amount = self.amount
        await interaction.response.edit_message(embed=view.step_embed(), view=view)

class ConfirmButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="✅ Đặt Kèo!", style=discord.ButtonStyle.success, row=2)
    async def callback(self, interaction: discord.Interaction):
        view: BetView = self.view
        if not view.bet_amount:
            return await interaction.response.send_message("❌ Chọn số tiền cược!", ephemeral=True, delete_after=4)
        db = view.db
        data = db.get_user(interaction.user.id)
        if data["balance"] < view.bet_amount:
            return await interaction.response.send_message(
                f"❌ Không đủ tiền! Bạn có {coin(data['balance'])}.", ephemeral=True, delete_after=5)
        if db_user_bet_on_match(db, interaction.user.id, view.match_id, view.bet_type):
            return await interaction.response.send_message(
                f"❌ Bạn đã đặt kèo **{view.bet_type}** cho trận này rồi!", ephemeral=True, delete_after=5)

        # Determine payout multiplier
        key = f"{view.bet_type}_{view.bet_choice}"
        if view.bet_type in ("ou_goals","ou_corner","ou_card"):
            key = f"{view.bet_type}_{view.bet_choice}"
        elif view.bet_type == "exact":
            key = "exact"
        mult = PAYOUTS.get(key, 1.9)

        db.update_balance(interaction.user.id, -view.bet_amount)
        bet_id = db_place_bet(db, view.match_id, interaction.user.id,
                              view.bet_type, view.bet_choice, view.bet_param,
                              view.bet_amount, mult)
        db.log_transaction(interaction.user.id, -view.bet_amount, "football_bet",
                           f"Kèo #{bet_id} trận #{view.match_id}")

        for child in view.children: child.disabled = True
        view.stop()

        e = discord.Embed(title="✅  Đặt Kèo Thành Công!", color=0x2ECC71)
        e.add_field(name="Trận", value=f"{view.match['home_team']} vs {view.match['away_team']}", inline=False)
        e.add_field(name="Loại kèo", value=BET_TYPES.get(view.bet_type, view.bet_type), inline=False)
        choice_display = view.bet_choice
        if view.bet_param and view.bet_param != view.bet_choice:
            choice_display += f" ({view.bet_param})"
        e.add_field(name="Cửa cược", value=f"**{choice_display.upper()}**", inline=True)
        e.add_field(name="Tiền cược", value=coin(view.bet_amount), inline=True)
        e.add_field(name="Tỷ lệ thắng", value=f"**{mult}x**", inline=True)
        e.add_field(name="Thắng nhận", value=coin(int(view.bet_amount * mult)), inline=True)
        e.set_footer(text=f"Bet ID #{bet_id}  |  Kết quả tự động sau trận")
        await interaction.response.edit_message(embed=e, view=view)

class CancelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="❌ Hủy", style=discord.ButtonStyle.danger, row=2)
    async def callback(self, interaction: discord.Interaction):
        self.view.stop()
        await interaction.response.edit_message(
            content="*Đã hủy đặt kèo.*", embed=None, view=None)

class BetView(discord.ui.View):
    def __init__(self, db, match: dict):
        super().__init__(timeout=180)
        self.db         = db
        self.match      = match
        self.match_id   = match["id"]
        self.step       = "type"
        self.bet_type   = None
        self.bet_choice = None
        self.bet_param  = None
        self.bet_amount = None
        self.add_item(BetTypeSelect(self.match_id))

    def step_embed(self):
        e = discord.Embed(
            title=f"⚽  Đặt Kèo — {self.match['home_team']} vs {self.match['away_team']}",
            color=0xF4C430
        )
        e.add_field(name="Bước hiện tại", value={
            "type":   "1️⃣ Chọn loại kèo",
            "choice": "2️⃣ Chọn cửa cược",
            "amount": "3️⃣ Chọn số tiền",
        }.get(self.step,""), inline=False)

        if self.bet_type:
            e.add_field(name="Loại kèo", value=BET_TYPES.get(self.bet_type,""), inline=True)
        if self.bet_choice:
            display = self.bet_choice
            if self.bet_param and self.bet_param != self.bet_choice:
                display += f" ({self.bet_param})"
            e.add_field(name="Cửa", value=f"**{display.upper()}**", inline=True)
        if self.bet_amount:
            key = f"{self.bet_type}_{self.bet_choice}"
            if self.bet_type == "exact": key = "exact"
            mult = PAYOUTS.get(key, 1.9)
            e.add_field(name="Tiền cược", value=coin(self.bet_amount), inline=True)
            e.add_field(name="Tỷ lệ", value=f"**{mult}x**", inline=True)
            e.add_field(name="Thắng nhận", value=coin(int(self.bet_amount * mult)), inline=True)
        return e


# ─── Result input modal ───────────────────────────────────────
class ResultModal(discord.ui.Modal, title="Nhập Kết Quả Trận Đấu"):
    goals_home  = discord.ui.TextInput(label="Bàn thắng đội nhà",  placeholder="vd: 2", max_length=2)
    goals_away  = discord.ui.TextInput(label="Bàn thắng đội khách", placeholder="vd: 1", max_length=2)
    corners_home = discord.ui.TextInput(label="Phạt góc đội nhà",  placeholder="vd: 6", max_length=2)
    corners_away = discord.ui.TextInput(label="Phạt góc đội khách + Thẻ (home_yellow,away_yellow,home_red,away_red)",
                                         placeholder="vd: 4 + 2,3,0,1", max_length=20)
    cards_input = discord.ui.TextInput(
        label="Thẻ phạt (vàng_nhà, vàng_khách, đỏ_nhà, đỏ_khách)",
        placeholder="vd: 2,1,0,0", max_length=20
    )

    def __init__(self, bot, match_id, channel):
        super().__init__()
        self.bot = bot; self.match_id = match_id; self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        db = self.bot.db
        match = db_get_match(db, self.match_id)
        if not match:
            return await interaction.response.send_message("❌ Match không tồn tại!", ephemeral=True)
        if match["status"] != "open":
            return await interaction.response.send_message("❌ Match đã được thanh toán!", ephemeral=True)

        try:
            gh = int(self.goals_home.value.strip())
            ga = int(self.goals_away.value.strip())
            ch = int(self.corners_home.value.strip())
            ca = int(self.corners_away.value.strip())
            cards = [int(x.strip()) for x in self.cards_input.value.split(",")]
            yh, ya, rh, ra = cards[0], cards[1], cards[2], cards[3]
        except:
            return await interaction.response.send_message(
                "❌ Nhập sai định dạng! Vui lòng thử lại.", ephemeral=True)

        result = {"goals_home":gh,"goals_away":ga,"corners_home":ch,
                  "corners_away":ca,"yellow_home":yh,"yellow_away":ya,
                  "red_home":rh,"red_away":ra}
        db_settle_match(db, self.match_id, result)

        bets = db_get_match_bets(db, self.match_id)
        total_out = 0; win_count = 0; lose_count = 0; refund_count = 0

        payout_lines = []
        for bet in bets:
            outcome, payout = evaluate_bet(bet, result)
            db_settle_bet(db, bet["id"], outcome, payout)
            if outcome == "won":
                db.update_balance(bet["user_id"], payout)
                db.record_game(bet["user_id"], payout - bet["amount"], 0)
                db.log_transaction(bet["user_id"], payout, "football_win",
                                   f"Thắng kèo #{bet['id']}")
                win_count += 1; total_out += payout
                try:
                    u = await self.bot.fetch_user(bet["user_id"])
                    payout_lines.append(f"✅ {u.display_name} thắng {coin(payout)} ({bet['bet_type']})")
                except: pass
            elif outcome == "refund":
                db.update_balance(bet["user_id"], payout)
                db.log_transaction(bet["user_id"], payout, "football_refund",
                                   f"Hoàn kèo #{bet['id']}")
                refund_count += 1
            else:
                db.record_game(bet["user_id"], 0, bet["amount"])
                lose_count += 1

        # Announce in channel
        e = discord.Embed(
            title=f"🏁  KẾT QUẢ TRẬN — {match['home_team']} vs {match['away_team']}",
            color=0x3498DB
        )
        e.add_field(name="⚽ Tỷ số",      value=f"**{gh} - {ga}**", inline=True)
        e.add_field(name="🚩 Phạt góc",   value=f"**{ch} - {ca}**", inline=True)
        e.add_field(name="🟨 Thẻ vàng",   value=f"**{yh} - {ya}**", inline=True)
        e.add_field(name="🟥 Thẻ đỏ",     value=f"**{rh} - {ra}**", inline=True)
        e.add_field(name="🟨 Điểm thẻ",   value=f"**{yh+ya+(rh+ra)*2}** điểm", inline=True)
        e.add_field(name="\u200b",         value="\u200b", inline=True)
        e.add_field(name="📊 Tổng kết",
            value=f"✅ Thắng: **{win_count}**\n❌ Thua: **{lose_count}**\n🔄 Hoàn: **{refund_count}**",
            inline=False)
        if payout_lines:
            e.add_field(name="💰 Chi trả", value="\n".join(payout_lines[:10]), inline=False)

        await self.channel.send(embed=e)
        await interaction.response.send_message("✅ Đã nhập kết quả và thanh toán kèo!", ephemeral=True)



# ─── Team select view (when multiple teams found) ────────────
async def _send_fixtures(interaction, team_id: int, team_name: str):
    """Fetch and send upcoming fixtures for a team"""
    fixtures = await search_fixtures(team_id)
    if not fixtures:
        await interaction.followup.send(
            f"❌ **{team_name}** không có trận sắp tới!\n"
            "(Giải đấu chưa lên lịch hoặc mùa giải chưa bắt đầu)",
            ephemeral=True
        )
        return
    e = discord.Embed(title=f"⚽  Lịch thi đấu: {team_name}", color=0x3498DB)
    lines = []
    for f in fixtures[:8]:
        fix    = f["fixture"]
        home   = f["teams"]["home"]["name"]
        away   = f["teams"]["away"]["name"]
        league = f["league"]["name"]
        dt     = datetime.fromisoformat(fix["date"].replace("Z", "+00:00"))
        time_str = dt.strftime("%d/%m/%Y %H:%M UTC")
        lines.append(
            f"🆔 `{fix['id']}` — **{home}** vs **{away}**\n"
            f"   📅 {time_str}   🏆 {league}"
        )
    e.description = "\n\n".join(lines)
    e.set_footer(text="Dùng /addmatch <fixture_id> để tạo kèo cho trận này")
    await interaction.followup.send(embed=e, ephemeral=True)

class TeamSelectMenu(discord.ui.Select):
    def __init__(self, teams, bot):
        self.bot = bot
        options = []
        for t in teams[:25]:
            tid   = t["team"]["id"]
            tname = t["team"]["name"]
            country = t["team"].get("country", "")
            options.append(discord.SelectOption(
                label=tname[:100],
                value=str(tid),
                description=f"{country} — ID: {tid}"[:100]
            ))
        super().__init__(
            placeholder="Chọn đội bóng...",
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        team_id   = int(self.values[0])
        team_name = next(
            o.label for o in self.options if o.value == self.values[0]
        )
        await _send_fixtures(interaction, team_id, team_name)

class TeamSelectView(discord.ui.View):
    def __init__(self, teams, bot):
        super().__init__(timeout=60)
        self.add_item(TeamSelectMenu(teams, bot))

# ─── COG ──────────────────────────────────────────────────────
class Football(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db  = bot.db
        db_create_bet_tables(self.db)

    # ── /searchmatch ───────────────────────────────────────
    @app_commands.command(name="searchmatch", description="⚽ Tìm trận đấu để tạo kèo")
    @app_commands.describe(team="Tên đội bóng hoặc giải đấu")
    async def searchmatch(self, interaction: discord.Interaction, team: str):
        await interaction.response.defer()
        if not API_KEY:
            return await interaction.followup.send(
                "❌ Chưa cấu hình `FOOTBALL_API_KEY`!\n"
                "Đăng ký free tại: https://dashboard.api-football.com/register\n"
                "Sau đó thêm vào Railway/env: `FOOTBALL_API_KEY=your_key`",
                ephemeral=True
            )


        # Step 1: tìm đội theo tên
        teams_found = await search_teams(team)
        if not teams_found:
            return await interaction.followup.send(
                f"❌ Không tìm thấy đội **{team}**!\n"
                "💡 Thử tên tiếng Anh: *Arsenal, Barcelona, Manchester United...*",
                ephemeral=True
            )

        # Nếu nhiều đội → show select menu
        if len(teams_found) > 1:
            view = TeamSelectView(teams_found[:10], self.bot)
            e = discord.Embed(
                title=f"⚽  Tìm thấy {len(teams_found)} đội bóng",
                description="Chọn đội để xem lịch thi đấu:",
                color=0x3498DB
            )
            for t in teams_found[:5]:
                e.add_field(
                    name=t["team"]["name"],
                    value=f"🌍 {t['team']['country']}  |  🆔 ID: {t['team']['id']}",
                    inline=False
                )
            return await interaction.followup.send(embed=e, view=view, ephemeral=True)

        # 1 đội → lấy trận luôn
        team_id   = teams_found[0]["team"]["id"]
        team_name = teams_found[0]["team"]["name"]
        await _send_fixtures(interaction, team_id, team_name)


    # ── /addmatch ──────────────────────────────────────────
    @app_commands.command(name="addmatch", description="⚽ Tạo kèo cho một trận đấu")
    @app_commands.describe(fixture_id="ID trận đấu (lấy từ /searchmatch)")
    async def addmatch(self, interaction: discord.Interaction, fixture_id: int):
        await interaction.response.defer()
        if not API_KEY:
            return await interaction.followup.send("❌ Chưa cấu hình FOOTBALL_API_KEY!", ephemeral=True)

        fix = await get_fixture(fixture_id)
        if not fix:
            return await interaction.followup.send("❌ Không tìm thấy trận này!", ephemeral=True)

        home   = fix["teams"]["home"]["name"]
        away   = fix["teams"]["away"]["name"]
        league = fix["league"]["name"]
        dt_str = fix["fixture"]["date"]
        dt     = datetime.fromisoformat(dt_str.replace("Z","+00:00"))
        time_vn = dt.strftime("%d/%m/%Y %H:%M") + " (UTC)"

        match_id = db_add_match(self.db, fixture_id, home, away, league, time_vn, interaction.user.id)
        if not match_id:
            return await interaction.followup.send("❌ Trận này đã được tạo rồi!", ephemeral=True)

        match = db_get_match(self.db, match_id)
        e = match_embed(match)
        e.set_footer(text=f"Dùng /bet {match_id} để đặt kèo!")
        await interaction.followup.send(embed=e)

    # ── /matches ───────────────────────────────────────────
    @app_commands.command(name="matches", description="⚽ Xem danh sách trận đang mở kèo")
    async def matches(self, interaction: discord.Interaction):
        open_matches = db_get_open_matches(self.db)
        if not open_matches:
            return await interaction.response.send_message("❌ Không có trận nào đang mở kèo!", ephemeral=True)

        e = discord.Embed(title="⚽  Trận Đang Mở Kèo", color=0x2ECC71)
        for m in open_matches[:10]:
            bets = db_get_match_bets(self.db, m["id"])
            pool = sum(b["amount"] for b in bets)
            e.add_field(
                name=f"#{m['id']}  {m['home_team']} vs {m['away_team']}",
                value=f"🏆 {m['league']}  |  📅 {m['match_time']}\n💰 Pool: {coin(pool)}  |  🎯 {len(bets)} kèo",
                inline=False
            )
        e.set_footer(text="Dùng /bet <match_id> để đặt kèo")
        await interaction.response.send_message(embed=e)

    # ── /bet ───────────────────────────────────────────────
    @app_commands.command(name="bet", description="⚽ Đặt kèo bóng đá")
    @app_commands.describe(match_id="ID trận đấu (xem /matches)")
    async def bet(self, interaction: discord.Interaction, match_id: int):
        self.db.get_user(interaction.user.id, interaction.user.display_name)
        match = db_get_match(self.db, match_id)
        if not match:
            return await interaction.response.send_message("❌ Không tìm thấy trận này!", ephemeral=True)
        if match["status"] != "open":
            return await interaction.response.send_message("❌ Trận này đã đóng kèo!", ephemeral=True)

        view = BetView(self.db, match)
        # ephemeral so only bettor sees the UI
        await interaction.response.send_message(
            embed=view.step_embed(), view=view, ephemeral=True
        )

    # ── /mybets ────────────────────────────────────────────
    @app_commands.command(name="mybets", description="⚽ Xem kèo bóng đá của bạn")
    async def mybets(self, interaction: discord.Interaction):
        self.db.get_user(interaction.user.id, interaction.user.display_name)
        c = self.db.conn.cursor()
        c.execute("""
            SELECT fb.*, fm.home_team, fm.away_team
            FROM football_bets fb
            JOIN football_matches fm ON fb.match_id = fm.id
            WHERE fb.user_id = ?
            ORDER BY fb.created_at DESC LIMIT 10
        """, (interaction.user.id,))
        rows = [dict(r) for r in c.fetchall()]

        if not rows:
            return await interaction.response.send_message("❌ Bạn chưa đặt kèo nào!", ephemeral=True)

        e = discord.Embed(title="⚽  Kèo Của Bạn", color=0x3498DB)
        status_ico = {"pending":"⏳","won":"✅","lost":"❌","refund":"🔄"}
        for b in rows:
            ico = status_ico.get(b["status"],"⚪")
            result_str = ""
            if b["status"] == "won":   result_str = f"→ **+{b['payout']:,}** 🪙"
            elif b["status"] == "lost": result_str = f"→ **-{b['amount']:,}** 🪙"
            elif b["status"] == "refund": result_str = "→ Hoàn tiền"
            choice_disp = b["bet_choice"]
            if b["bet_param"] and b["bet_param"] != b["bet_choice"]:
                choice_disp += f" ({b['bet_param']})"
            e.add_field(
                name=f"{ico} #{b['id']}  {b['home_team']} vs {b['away_team']}",
                value=(
                    f"Kèo: **{BET_TYPES.get(b['bet_type'],b['bet_type'])}**\n"
                    f"Cửa: **{choice_disp.upper()}**  |  Cược: {coin(b['amount'])}  |  "
                    f"Tỷ lệ: **{b['payout_mult']}x**  {result_str}"
                ),
                inline=False
            )
        await interaction.response.send_message(embed=e, ephemeral=True)

    # ── /matchresult ───────────────────────────────────────
    @app_commands.command(name="matchresult", description="⚽ [Nhập kết quả trận & tự động thanh toán kèo]")
    @app_commands.describe(match_id="ID trận đấu")
    async def matchresult(self, interaction: discord.Interaction, match_id: int):
        match = db_get_match(self.db, match_id)
        if not match:
            return await interaction.response.send_message("❌ Match không tồn tại!", ephemeral=True)
        if match["status"] != "open":
            return await interaction.response.send_message("❌ Match đã được thanh toán rồi!", ephemeral=True)

        modal = ResultModal(self.bot, match_id, interaction.channel)
        await interaction.response.send_modal(modal)

    # ── /autosettle ────────────────────────────────────────
    @app_commands.command(name="autosettle", description="⚽ Tự động lấy kết quả từ API và thanh toán kèo")
    @app_commands.describe(match_id="ID trận đấu")
    async def autosettle(self, interaction: discord.Interaction, match_id: int):
        await interaction.response.defer(ephemeral=True)
        match = db_get_match(self.db, match_id)
        if not match:
            return await interaction.followup.send("❌ Match không tồn tại!", ephemeral=True)
        if match["status"] != "open":
            return await interaction.followup.send("❌ Match đã được thanh toán!", ephemeral=True)
        if not API_KEY:
            return await interaction.followup.send("❌ Chưa cấu hình FOOTBALL_API_KEY!", ephemeral=True)

        data = await get_fixture_stats(match["fixture_id"])
        if not data:
            return await interaction.followup.send("❌ Không lấy được dữ liệu trận từ API!", ephemeral=True)

        fix = data["fixture"]
        fstatus = fix["fixture"]["status"]["short"]
        if fstatus not in ("FT","AET","PEN"):
            return await interaction.followup.send(
                f"❌ Trận chưa kết thúc! Trạng thái hiện tại: **{fstatus}**", ephemeral=True)

        gh = fix["score"]["fulltime"]["home"] or 0
        ga = fix["score"]["fulltime"]["away"] or 0

        # Parse stats
        def get_stat(stats_list, team_id, stat_name):
            for team_stats in stats_list:
                if team_stats["team"]["id"] == team_id:
                    for s in team_stats["statistics"]:
                        if s["type"] == stat_name:
                            return int(s["value"] or 0)
            return 0

        home_id = fix["teams"]["home"]["id"]
        away_id = fix["teams"]["away"]["id"]
        stats   = data["stats"]
        ch = get_stat(stats, home_id, "Corner Kicks")
        ca = get_stat(stats, away_id, "Corner Kicks")
        yh = get_stat(stats, home_id, "Yellow Cards")
        ya = get_stat(stats, away_id, "Yellow Cards")
        rh = get_stat(stats, home_id, "Red Cards")
        ra = get_stat(stats, away_id, "Red Cards")

        result = {"goals_home":gh,"goals_away":ga,"corners_home":ch,
                  "corners_away":ca,"yellow_home":yh,"yellow_away":ya,
                  "red_home":rh,"red_away":ra}
        db_settle_match(self.db, match_id, result)

        bets = db_get_match_bets(self.db, match_id)
        win_count = lose_count = refund_count = 0
        payout_lines = []

        for bet in bets:
            outcome, payout = evaluate_bet(bet, result)
            db_settle_bet(self.db, bet["id"], outcome, payout)
            if outcome == "won":
                self.db.update_balance(bet["user_id"], payout)
                self.db.record_game(bet["user_id"], payout - bet["amount"], 0)
                win_count += 1
                try:
                    u = await self.bot.fetch_user(bet["user_id"])
                    payout_lines.append(f"✅ {u.display_name} +{payout:,} 🪙")
                except: pass
            elif outcome == "refund":
                self.db.update_balance(bet["user_id"], payout)
                refund_count += 1
            else:
                self.db.record_game(bet["user_id"], 0, bet["amount"])
                lose_count += 1

        e = discord.Embed(
            title=f"🏁  AUTO SETTLE — {match['home_team']} vs {match['away_team']}",
            color=0x3498DB
        )
        e.add_field(name="⚽ Tỷ số",    value=f"**{gh} - {ga}**", inline=True)
        e.add_field(name="🚩 Phạt góc", value=f"**{ch} - {ca}**", inline=True)
        e.add_field(name="🃏 Thẻ",      value=f"🟨{yh}-{ya}  🟥{rh}-{ra}", inline=True)
        e.add_field(name="📊 Kết quả",
            value=f"✅ Thắng: **{win_count}**  ❌ Thua: **{lose_count}**  🔄 Hoàn: **{refund_count}**",
            inline=False)
        if payout_lines:
            e.add_field(name="💰 Chi trả", value="\n".join(payout_lines[:10]), inline=False)
        await interaction.channel.send(embed=e)
        await interaction.followup.send("✅ Đã tự động thanh toán!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Football(bot))
