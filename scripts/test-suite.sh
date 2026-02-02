#!/bin/bash
# Complete TTS capability test suite
# This script runs automated tests to verify the TTS capability is working correctly

set -e  # Exit on error

echo "=========================================="
echo "TTS Capability Test Suite"
echo "=========================================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo -e "\n${YELLOW}Running: $test_name${NC}"
    
    if eval "$test_command"; then
        echo -e "${GREEN}✓ PASSED${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAILED${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

# Test 1: Health Check
run_test "Health Check" '
    response=$(curl -s http://localhost:10200/health)
    echo "$response" | jq -e ".status" > /dev/null
'

# Test 2: Health endpoint returns hardware info
run_test "Hardware Detection in Health" '
    response=$(curl -s http://localhost:10200/health)
    echo "$response" | jq -e ".hardware.architecture" > /dev/null &&
    echo "$response" | jq -e ".hardware.ram_mb" > /dev/null &&
    echo "$response" | jq -e ".hardware.cpu_cores" > /dev/null &&
    echo "$response" | jq -e ".hardware.gpu_type" > /dev/null
'

# Test 3: Capability Metadata
run_test "Capability Metadata" '
    response=$(curl -s http://localhost:10200/.well-known/capability.json)
    echo "$response" | jq -e ".name" > /dev/null &&
    echo "$response" | jq -e ".resources" > /dev/null &&
    echo "$response" | jq -e ".hardware" > /dev/null
'

# Test 4: Model Status Check
echo -e "\n${YELLOW}Checking Model Status...${NC}"
MODEL_STATUS=$(curl -s http://localhost:10200/health | jq -r .model_loaded)
if [ "$MODEL_STATUS" = "true" ]; then
    echo -e "${GREEN}✓ Voice model is loaded${NC}"
    MODEL_LOADED=true
else
    echo -e "${YELLOW}⚠ No voice model loaded - synthesis tests will be skipped${NC}"
    MODEL_LOADED=false
fi

# Test 5: Basic Synthesis (only if model is loaded)
if [ "$MODEL_LOADED" = true ]; then
    run_test "Basic Synthesis" '
        curl -s -X POST http://localhost:10200/synthesize \
          -H "Content-Type: application/json" \
          -d "{\"text\":\"Test successful\"}" \
          --output /tmp/test_basic.wav &&
        [ -f /tmp/test_basic.wav ] &&
        [ -s /tmp/test_basic.wav ]
    '

    # Test 6: Verify WAV format
    if command -v file &> /dev/null; then
        run_test "WAV Format Validation" '
            file /tmp/test_basic.wav | grep -q "WAVE audio"
        '
    else
        echo -e "${YELLOW}⚠ Skipping WAV validation - 'file' command not available${NC}"
    fi

    # Test 7: Longer text synthesis
    run_test "Long Text Synthesis" '
        curl -s -X POST http://localhost:10200/synthesize \
          -H "Content-Type: application/json" \
          -d "{\"text\":\"The eZansi Edge AI platform enables artificial intelligence capabilities on edge devices with automatic hardware detection.\"}" \
          --output /tmp/test_long.wav &&
        [ -f /tmp/test_long.wav ] &&
        [ -s /tmp/test_long.wav ] &&
        [ $(stat -f%z /tmp/test_long.wav 2>/dev/null || stat -c%s /tmp/test_long.wav) -gt $(stat -f%z /tmp/test_basic.wav 2>/dev/null || stat -c%s /tmp/test_basic.wav) ]
    '

    # Test 8: Empty text error handling
    run_test "Empty Text Error Handling" '
        response=$(curl -s -w "%{http_code}" -X POST http://localhost:10200/synthesize \
          -H "Content-Type: application/json" \
          -d "{\"text\":\"\"}" \
          -o /dev/null)
        [ "$response" = "422" ]
    '
else
    echo -e "${YELLOW}⚠ Skipping synthesis tests - no voice model loaded${NC}"
fi

# Test 9: Invalid JSON error handling
run_test "Invalid JSON Error Handling" '
    response=$(curl -s -w "%{http_code}" -X POST http://localhost:10200/synthesize \
      -H "Content-Type: application/json" \
      -d "invalid json" \
      -o /dev/null)
    [ "$response" = "422" ]
'

# Test 10: API Documentation accessibility
run_test "API Documentation Available" '
    curl -s http://localhost:10200/docs | grep -q "Swagger"
'

# Summary
echo -e "\n=========================================="
echo "Test Suite Summary"
echo "=========================================="
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
echo "=========================================="

# Cleanup test files
rm -f /tmp/test_basic.wav /tmp/test_long.wav 2>/dev/null

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}✓ ALL TESTS PASSED!${NC}\n"
    exit 0
else
    echo -e "\n${RED}✗ SOME TESTS FAILED${NC}\n"
    exit 1
fi
