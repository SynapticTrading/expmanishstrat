#!/bin/bash

# Integration Test Runner Script
# Helps run integration tests with common options

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if credentials file exists
if [ ! -f "test_credentials.yaml" ]; then
    echo -e "${RED}❌ Error: test_credentials.yaml not found${NC}"
    echo ""
    echo "Please copy the template and fill in your credentials:"
    echo "  cp test_credentials.yaml.template test_credentials.yaml"
    echo "  # Then edit test_credentials.yaml with your broker credentials"
    exit 1
fi

echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}     Integration Test Runner - Real Broker Testing      ${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo ""

# Function to run tests
run_tests() {
    local test_args="$@"
    echo -e "${YELLOW}Running: pytest $test_args${NC}"
    echo ""
    pytest $test_args
}

# Parse command line arguments
case "${1:-all}" in
    "all")
        echo "Running ALL integration tests..."
        run_tests "-v"
        ;;
    "zerodha")
        echo "Running Zerodha tests only..."
        run_tests "test_zerodha_integration.py -v"
        ;;
    "angelone")
        echo "Running AngelOne tests only..."
        run_tests "test_angelone_integration.py -v"
        ;;
    "auth")
        echo "Running Authentication tests..."
        run_tests "-v -k auth"
        ;;
    "quote")
        echo "Running Market Data (Quote) tests..."
        run_tests "-v -k quote"
        ;;
    "order")
        echo "Running Order (AMO) tests..."
        run_tests "-v -k order"
        ;;
    "pos")
        echo "Running Position tests..."
        run_tests "-v -k pos"
        ;;
    "websocket")
        echo "Running WebSocket tests..."
        run_tests "-v -k websocket"
        ;;
    "quick")
        echo "Running quick tests (auth + quote)..."
        run_tests "-v -k 'auth or quote_01'"
        ;;
    "verbose")
        echo "Running all tests with output..."
        run_tests "-v -s"
        ;;
    "coverage")
        echo "Running tests with coverage report..."
        run_tests "--cov=paper_trading/brokers/adapter --cov-report=html --cov-report=term -v"
        echo ""
        echo -e "${GREEN}✓ Coverage report generated in htmlcov/index.html${NC}"
        ;;
    "list")
        echo "Available test suites:"
        pytest --collect-only -q
        ;;
    "help"|"-h"|"--help")
        cat << EOF
Integration Test Runner

Usage: ./run_tests.sh [COMMAND]

Commands:
  all         Run all integration tests (default)
  zerodha     Run Zerodha tests only
  angelone    Run AngelOne tests only
  auth        Run authentication tests
  quote       Run market data tests
  order       Run order placement tests (AMO)
  pos         Run position tests
  websocket   Run WebSocket tests
  quick       Run quick smoke tests
  verbose     Run with print output (-s)
  coverage    Run with coverage report
  list        List all available tests
  help        Show this help message

Examples:
  ./run_tests.sh                    # Run all tests
  ./run_tests.sh zerodha            # Zerodha only
  ./run_tests.sh auth               # Auth tests only
  ./run_tests.sh quick              # Quick validation
  ./run_tests.sh coverage           # With coverage

Safety:
  - All order tests use AMO (After Market Orders)
  - Orders are auto-cancelled after tests
  - Tests skip during market hours for safety

Requirements:
  - test_credentials.yaml must be configured
  - pytest and dependencies installed
  - Valid broker credentials

EOF
        exit 0
        ;;
    *)
        echo -e "${RED}❌ Unknown command: $1${NC}"
        echo ""
        echo "Run './run_tests.sh help' for available commands"
        exit 1
        ;;
esac

# Show status
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}             ✓ All Tests Passed Successfully            ${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
else
    echo ""
    echo -e "${RED}════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}               ✗ Some Tests Failed                       ${NC}"
    echo -e "${RED}════════════════════════════════════════════════════════${NC}"
    exit 1
fi
