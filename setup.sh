#!/bin/bash

echo "🚀 Setting up Bunny CDN Cache Purge Bot for Replit..."

echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

if [ ! -f .env ]; then
    echo "⚠️  Creating .env file from template..."
    cp .env.example .env
    echo "❗ Please add your TELEGRAM_BOT_TOKEN to the .env file or use Replit Secrets"
else
    echo "✅ .env file already exists"
fi

echo "✨ Setup complete!"
echo ""
echo "📝 Next steps:"
echo "1. Add your TELEGRAM_BOT_TOKEN to Replit Secrets or .env file"
echo "2. Click the 'Run' button to start the bot"
echo ""
