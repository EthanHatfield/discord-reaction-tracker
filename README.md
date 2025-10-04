# Discord Reaction Tracker

A Discord bot that tracks and analyzes user reactions across server channels using modern slash commands. Monitor user engagement, generate detailed reports, and gain insights into your community's reaction patterns.

## ✨ Features

- **Real-time Reaction Tracking**: Automatically tracks reactions on messages
- **Historical Scanning**: Scan existing message history for past reactions  
- **Slash Commands**: Modern Discord slash command interface
- **Detailed Reports**: Generate comprehensive reaction statistics
- **Emoji Analytics**: Track most popular emojis and usage patterns
- **Configurable Rate Limiting**: Optimized for Discord's API limits
- **Persistent Storage**: SQLite database for reliable data storage

## 📋 Commands

All commands use Discord's slash command interface (`/`):

- `/scan` - Start scanning message history for reactions
- `/scan_stop` - Stop the scanning process
- `/scan_status` - Check scanning progress
- `/report [days] [emoji]` - Generate detailed reaction reports
- `/emoji_stats [days]` - Show emoji usage statistics  
- `/help` - Show command information
- `/start` - Start tracking reactions
- `/stop` - Stop tracking reactions
- `/status` - Check tracking status
- `/debug_db` - Show database statistics

## 🚀 Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/discord-reaction-tracker.git
   ```
2. Navigate to the project directory:
   ```
   cd discord-reaction-tracker
   ```
3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Configuration

1. Copy the `.env.example` file to `.env`:
   ```
   cp .env.example .env
   ```
2. Edit the `.env` file and add your Discord bot token and other configuration values.
3. The following environment variables are supported:
   - `DISCORD_BOT_TOKEN` (required): Your Discord bot token
   - `REACTION_TIMEFRAME` (optional): Timeframe in seconds for tracking reactions (default: 3600)
   - `LOG_CHANNEL_ID` (optional): Channel ID for logging
   - `MESSAGE_DELAY` (optional): Delay between processing messages in seconds (default: 1.0)
   - `REACTION_DELAY` (optional): Delay between processing reactions in seconds (default: 0.5)
   - `CHANNEL_DELAY` (optional): Delay between processing channels in seconds (default: 5.0)
   - `MIN_RATE_LIMIT_DELAY` (optional): Minimum delay when rate limited in seconds (default: 5.0)

## 🔧 Usage

To run the bot, execute the following command:
```bash
python src/bot.py
```

The bot will automatically:
1. Connect to Discord using your bot token
2. Register slash commands with all servers the bot is in
3. Start tracking reactions in real-time
4. Begin scanning historical messages (if `/scan` is used)

## 🤖 Bot Permissions

Ensure your bot has these permissions:
- Read Messages/View Channels
- Use Slash Commands  
- Read Message History
- Add Reactions (optional, for testing)

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.