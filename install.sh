#!/bin/sh
set -e

echo "Installing advisor-cli..."
echo ""

# 1. Check/install uv
if ! command -v uv >/dev/null 2>&1; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    echo ""
fi

# 2. Install advisor-cli
echo "Installing advisor-cli..."
uv tool install advisor-cli
echo ""

# 3. Auto-setup if API keys in env
if [ -n "$GEMINI_API_KEY" ] || [ -n "$OPENAI_API_KEY" ] || [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "API keys found, configuring..."
    advisor setup -y
    echo ""
    echo "Installing MCP integration..."
    advisor mcp install -y
else
    echo "Installed! Next steps:"
    echo ""
    echo "   advisor setup        # Configure API keys"
    echo "   advisor mcp install  # Add to Claude"
    echo ""
    echo "Or run with API keys:"
    echo "   GEMINI_API_KEY=xxx advisor setup -y"
fi

echo ""
echo "Usage:"
echo "   advisor ask 'your question'"
echo "   advisor compare 'question for multiple models'"
echo "   advisor config show   # View configuration"
echo "   advisor setup         # Change settings"
