#!/bin/bash
# Safe serial debugging wrapper that runs in background to prevent lockups

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/python_utils/safe_serial_debug.py"
LOG_FILE="/tmp/serial_debug_$$.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

usage() {
    echo "Safe Serial Debugger for Teensy LED Matrix"
    echo ""
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  test              - Quick connection test"
    echo "  monitor [secs]    - Monitor output (default: 5 seconds)"
    echo "  send <cmd>        - Send command and get response"
    echo "  interactive       - Interactive test mode"
    echo "  list             - List available ports"
    echo "  background       - Run monitor in background"
    echo "  kill             - Kill background monitors"
    echo ""
    echo "Options:"
    echo "  --port <port>    - Specify serial port"
    echo "  --baud <rate>    - Baud rate (default: 2000000)"
    echo ""
    echo "Examples:"
    echo "  $0 test"
    echo "  $0 monitor 10"
    echo "  $0 send t"
    echo "  $0 background    # Won't lock up Claude Code"
}

# Function to run command with timeout
run_with_timeout() {
    local timeout_seconds=$1
    shift
    timeout --preserve-status $timeout_seconds "$@"
    local exit_code=$?
    if [ $exit_code -eq 124 ]; then
        echo -e "${YELLOW}Command timed out after ${timeout_seconds} seconds${NC}"
    fi
    return $exit_code
}

# Function to run in background
run_background() {
    echo -e "${GREEN}Starting background serial monitor...${NC}"
    echo "Log file: $LOG_FILE"
    
    nohup timeout 30 python3 "$PYTHON_SCRIPT" --monitor 30 > "$LOG_FILE" 2>&1 &
    local pid=$!
    echo "Background PID: $pid"
    echo ""
    echo "Commands:"
    echo "  tail -f $LOG_FILE    # Watch output"
    echo "  kill $pid            # Stop monitor"
    echo "  $0 kill              # Kill all monitors"
}

# Kill background processes
kill_background() {
    echo "Killing background serial monitors..."
    pkill -f "safe_serial_debug.py"
    echo "Done"
}

# Main command handling
case "$1" in
    test)
        shift
        echo -e "${GREEN}Running connection test...${NC}"
        run_with_timeout 5 python3 "$PYTHON_SCRIPT" --test "$@"
        ;;
        
    monitor)
        duration=${2:-5}
        shift 2
        echo -e "${GREEN}Monitoring for $duration seconds...${NC}"
        run_with_timeout $((duration + 2)) python3 "$PYTHON_SCRIPT" --monitor $duration "$@"
        ;;
        
    send)
        cmd="$2"
        shift 2
        echo -e "${GREEN}Sending command: $cmd${NC}"
        run_with_timeout 3 python3 "$PYTHON_SCRIPT" --send "$cmd" "$@"
        ;;
        
    interactive)
        shift
        echo -e "${YELLOW}Interactive mode - Use Ctrl+C to exit${NC}"
        python3 "$PYTHON_SCRIPT" --interactive "$@"
        ;;
        
    list)
        shift
        python3 "$PYTHON_SCRIPT" --list "$@"
        ;;
        
    background|bg)
        run_background
        ;;
        
    kill)
        kill_background
        ;;
        
    help|--help|-h)
        usage
        ;;
        
    *)
        if [ -z "$1" ]; then
            echo -e "${GREEN}Running default connection test...${NC}"
            run_with_timeout 5 python3 "$PYTHON_SCRIPT" --test
        else
            echo -e "${RED}Unknown command: $1${NC}"
            echo ""
            usage
            exit 1
        fi
        ;;
esac