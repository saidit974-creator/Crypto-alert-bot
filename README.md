# Crypto Telegram Alert Bot — Free

This bot uses:
- Telegram Bot API
- Binance public Spot price API
- GitHub Actions (scheduled every 5 minutes)

No TradingView subscription is required.

## Telegram commands

/add BTC above 120000
/add SUI below 3.5
/list
/del 3
/clear
/help

Alerts are one-shot: after they trigger, they become inactive.

## Security

Never put your Telegram bot token inside the code.
Store it in GitHub Secrets as BOT_TOKEN.

Only the chat ID stored in ALLOWED_CHAT_ID can control the bot.

## Important limitation

GitHub scheduled workflows have a minimum schedule of 5 minutes and can occasionally be delayed under high load. This is excellent for price-level monitoring, but it is not a tick-by-tick or millisecond alert system.
