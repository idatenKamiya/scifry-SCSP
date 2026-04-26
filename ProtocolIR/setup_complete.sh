#!/bin/bash
# Complete data collection and training setup
# Run: bash setup_complete.sh

set -e  # Exit on error

echo "================================================================================"
echo "PROTOCOLIR COMPLETE SETUP"
echo "================================================================================"

# Step 1: Verify installation
echo ""
echo "Step 1: Verifying installation..."
python3 test_installation.py

if [ $? -ne 0 ]; then
    echo "✗ Installation verification failed"
    exit 1
fi

# Step 2: Check API key
echo ""
echo "Step 2: Checking API configuration..."

LLM_PROVIDER="${PROTOCOLIR_LLM_PROVIDER:-ollama}"
echo "  Provider: $LLM_PROVIDER"

if [ "$LLM_PROVIDER" = "anthropic" ]; then
    if [ -z "$ANTHROPIC_API_KEY" ]; then
        echo "⚠ ANTHROPIC_API_KEY not set"
        echo "  Set with: export ANTHROPIC_API_KEY='your_key'"
    else
        echo "✓ ANTHROPIC_API_KEY is set"
    fi
else
    OLLAMA_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
    echo "  Checking Ollama at: $OLLAMA_URL"
    if curl -s --max-time 3 "$OLLAMA_URL/api/tags" > /dev/null; then
        echo "✓ Ollama is reachable"
    else
        echo "⚠ Ollama is not reachable at $OLLAMA_URL"
        echo "  Start it first: ollama serve"
    fi
fi

# Step 3: Fetch data
echo ""
echo "Step 3: Fetching protocol data..."
if python3 data_fetcher.py; then
    echo "✓ Data fetching complete"
else
    echo "⚠ Data fetching had issues (non-critical)"
fi

# Step 4: Train reward model
echo ""
echo "Step 4: Training reward model..."
if python3 train_reward_model.py; then
    echo "✓ Reward model training complete"
else
    echo "⚠ Reward model training had issues (non-critical)"
fi

# Step 5: Run demo
echo ""
echo "Step 5: Running demo with expanded data..."
if python3 main.py --demo; then
    echo "✓ Demo complete"
    echo ""
    echo "Output files generated:"
    ls -lh outputs/
else
    echo "⚠ Demo had issues"
fi

echo ""
echo "================================================================================"
echo "✓ SETUP COMPLETE"
echo "================================================================================"
echo ""
echo "Next steps:"
echo "1. Review outputs/summary.txt for demo results"
echo "2. Review outputs/audit_report.md for detailed analysis"
echo "3. Check models/learned_weights.json for trained reward model"
echo ""
echo "Ready for hackathon demo!"
echo "================================================================================"
