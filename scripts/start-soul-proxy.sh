#!/bin/bash
# Soul Engine Ollama Proxy Launcher
# Run this to start the proxy server that wraps Ollama with Soul Engine

SOUL_ENGINE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROXY_SCRIPT="$SOUL_ENGINE_DIR/src/soul_engine/wrappers/ollama_soul_proxy.py"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Soul Engine Ollama Proxy ===${NC}"
echo ""

# Check Ollama is running
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Ollama is not running on localhost:11434${NC}"
    echo "   Start Ollama first: ollama serve"
    exit 1
fi

echo "✅ Ollama detected at localhost:11434"

# Check llama3.2:3b is available
if ! ollama list | grep -q "llama3.2:3b"; then
    echo -e "${YELLOW}⚠️  llama3.2:3b not found. Pulling...${NC}"
    ollama pull llama3.2:3b
fi

echo "✅ llama3.2:3b available"
echo ""

# Start proxy
echo "Starting Soul Engine proxy on port 11435..."
echo "   Hindsight should use: http://host.docker.internal:11435"
echo "   (Update docker-compose.yml HINDSIGHT_API_LLM_BASE_URL)"
echo ""
echo -e "${GREEN}Proxy running. Press Ctrl+C to stop.${NC}"
echo ""

python3 "$PROXY_SCRIPT" --port 11435 --ollama-url http://localhost:11434
