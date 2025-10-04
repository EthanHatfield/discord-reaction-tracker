# Discord Reaction Tracker

This project is a Discord bot that tracks the number of reactions each user earns within a specified timeframe. It provides an easy way to monitor user engagement through reactions in Discord channels.

## Features

- Tracks user reactions to messages in real-time.
- Allows configuration of the tracking timeframe.
- Provides a summary of reactions earned by each user.

## Installation

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

Before running the bot, you need to set up your configuration. Open `src/config.py` and add your Discord bot token and any other necessary parameters.

## Usage

To run the bot, execute the following command:
```
python src/bot.py
```

Make sure your bot has the necessary permissions to read messages and manage reactions in the channels you want to track.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.