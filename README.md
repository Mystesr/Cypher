# 🎰 Casino Royale — Discord Gambling Bot

A full-featured private gambling bot for you and your friends, with a real currency system, debt tracking, and owner-only god mode.

---

## ✅ Features

### 💰 Economy
| Command | Description |
|---|---|
| `/balance [user]` | Check your or someone's wallet + stats |
| `/daily` | Claim 500 coins every 24 hours |
| `/work` | Earn 50–300 coins every 1 hour |
| `/transfer <user> <amount>` | Send coins to a friend |
| `/leaderboard` | Top 10 richest players |

### 🤝 Lending & Debt
| Command | Description |
|---|---|
| `/lend <user> <amount>` | Lend coins — recorded as a debt with ID |
| `/paydebt <id>` | Repay a specific debt |
| `/debts` | View all debts owed to you or by you |

### 🎮 Gambling Games
| Command | Description | Payout |
|---|---|---|
| `/slots <bet>` | 3-reel slot machine | Up to 50x |
| `/coinflip <bet> <heads/tails>` | 50/50 flip | 2x |
| `/blackjack <bet>` | Interactive hit/stand vs dealer | 2x |
| `/dice <bet> <over/under/seven>` | Dice total guess | 2x or 5x |
| `/roulette <bet> <type>` | Red/black/number bet | Up to 35x |
| `/crash <bet> <cashout>` | Set your auto cash-out multiplier | Variable |

### 👑 Owner-Only (YOU)
| Command | Description |
|---|---|
| `/setmoney <amount>` | Set **your own** balance to any number |
| `/addmoney <user> <amount>` | Give or remove coins from anyone |
| `/resetuser <user>` | Reset a player back to 1,000 coins |
| `/canceldebt <id>` | Forgive any debt |

---

## 🚀 Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Create `.env` file
```bash
cp env.example .env
```
Fill in:
- `DISCORD_TOKEN` — from https://discord.com/developers/applications
- `OWNER_ID` — your Discord user ID

**To get your user ID:** Enable Developer Mode in Discord settings → right-click your name → Copy User ID

### 3. Invite the bot
In the Discord Developer Portal → OAuth2 → URL Generator:
- Scopes: `bot`, `applications.commands`
- Permissions: `Send Messages`, `Use Slash Commands`, `Read Message History`

### 4. Run
```bash
python bot.py
```

---

## 📁 File Structure
```
gambling-bot/
├── bot.py              # Entry point
├── database.py         # SQLite data layer
├── requirements.txt
├── .env                # Your secrets (never commit!)
├── data/
│   └── casino.db       # Auto-created SQLite database
└── cogs/
    ├── economy.py      # Balance, daily, work, transfer, lend, debt
    ├── gambling.py     # Slots, coinflip, blackjack, dice, roulette, crash
    └── admin.py        # Owner-only commands + /help
```

---

## 🛡️ Security Notes
- Owner commands check your Discord user ID directly — nobody else can use them
- All balance changes are logged in the `transactions` table
- Debt system records lender, borrower, amount, and paid status persistently
- Data lives in `data/casino.db` — back this up to preserve balances
