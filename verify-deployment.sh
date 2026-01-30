#!/bin/bash
# v1.0 Deployment Verification Script

set -e

echo "═══════════════════════════════════════════════════"
echo "v1.0 Deployment Verification"
echo "═══════════════════════════════════════════════════"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check functions
check_pass() {
    echo -e "${GREEN}✓${NC} $1"
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# 1. Check Python version
echo "1. Checking Python version..."
if python3 --version 2>&1 | grep -qE "3\.(11|12|13)"; then
    PYTHON_VERSION=$(python3 --version)
    check_pass "Python version OK: $PYTHON_VERSION"
else
    check_fail "Python 3.11+ required"
    exit 1
fi
echo ""

# 2. Check virtual environment
echo "2. Checking virtual environment..."
if [ -d "venv" ]; then
    check_pass "Virtual environment exists"
else
    check_warn "Virtual environment not found - run: python3 -m venv venv"
fi
echo ""

# 3. Check dependencies (if venv activated)
echo "3. Checking dependencies..."
if [ -n "$VIRTUAL_ENV" ]; then
    if pip list 2>/dev/null | grep -q "websockets"; then
        check_pass "Dependencies installed"
    else
        check_warn "Dependencies not installed - run: pip install -e ."
    fi
else
    check_warn "Virtual environment not activated - run: source venv/bin/activate"
fi
echo ""

# 4. Check Docker
echo "4. Checking Docker and Signal API..."
if docker ps 2>/dev/null | grep -q "signal-api"; then
    check_pass "Signal API container running"
else
    check_fail "Signal API container not running - run: docker-compose up -d"
fi
echo ""

# 5. Check configuration
echo "5. Checking configuration..."
if [ -f ".env" ]; then
    check_pass ".env file exists"
    if grep -q "AUTHORIZED_NUMBER" .env; then
        check_pass "AUTHORIZED_NUMBER configured"
    else
        check_warn "AUTHORIZED_NUMBER not set in .env"
    fi
else
    check_fail ".env file missing - copy from .env.example"
fi
echo ""

# 6. Check test suite (if pytest available)
echo "6. Checking test suite..."
if [ -n "$VIRTUAL_ENV" ] && command -v pytest &> /dev/null; then
    echo "   Running quick test check..."
    if pytest --collect-only -q 2>&1 | grep -q "test"; then
        TEST_COUNT=$(pytest --collect-only -q 2>&1 | grep -oE "[0-9]+ test" | head -1)
        check_pass "Test suite OK: $TEST_COUNT"
    else
        check_warn "Could not verify test suite"
    fi
else
    check_warn "pytest not available - install with: pip install -e '.[dev]'"
fi
echo ""

# 7. Check project structure
echo "7. Checking project structure..."
REQUIRED_DIRS=("src" "tests" "config" ".planning")
ALL_EXIST=true
for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        check_pass "$dir/ exists"
    else
        check_fail "$dir/ missing"
        ALL_EXIST=false
    fi
done
echo ""

# 8. Summary
echo "═══════════════════════════════════════════════════"
echo "Deployment Readiness Summary"
echo "═══════════════════════════════════════════════════"
echo ""

if $ALL_EXIST && [ -f ".env" ]; then
    echo -e "${GREEN}Ready for deployment!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. source venv/bin/activate"
    echo "  2. pip install -e '.[dev]'"
    echo "  3. pytest --cov=src"
    echo "  4. python -m src.daemon.service"
    echo ""
    echo "See DEPLOYMENT.md for complete instructions."
else
    echo -e "${YELLOW}Setup incomplete${NC}"
    echo ""
    echo "Fix the issues above, then run this script again."
fi
echo ""
