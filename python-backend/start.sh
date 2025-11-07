#!/bin/bash

# Rowboat Python Backend Startup Script
# This script provides easy startup and testing options for the Python backend

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
VENV_DIR="venv"
PYTHON_CMD="python3"
API_PORT=8000

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_python() {
    if ! command -v $PYTHON_CMD > /dev/null; then
        log_error "Python 3 is not installed or not in PATH"
        exit 1
    fi

    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
    log_info "Using Python $PYTHON_VERSION"
}

create_virtual_env() {
    if [ ! -d "$VENV_DIR" ]; then
        log_info "Creating virtual environment..."
        $PYTHON_CMD -m venv $VENV_DIR
        log_success "Virtual environment created"
    else
        log_info "Virtual environment already exists"
    fi
}

activate_virtual_env() {
    log_info "Activating virtual environment..."
    source $VENV_DIR/bin/activate
    log_success "Virtual environment activated"
}

install_dependencies() {
    log_info "Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    log_success "Dependencies installed"
}

check_environment() {
    log_info "Checking environment configuration..."

    if [ ! -f ".env" ]; then
        log_warning ".env file not found, copying from .env.example"
        cp .env.example .env
        log_warning "Please update .env with your configuration"
    fi

    # Check required environment variables
    source .env

    if [ -z "$PROVIDER_API_KEY" ]; then
        log_error "PROVIDER_API_KEY is not set in .env file"
        exit 1
    fi

    if [ -z "$PROVIDER_BASE_URL" ]; then
        log_error "PROVIDER_BASE_URL is not set in .env file"
        exit 1
    fi

    log_success "Environment configuration validated"
}

start_backend() {
    log_info "Starting Rowboat Python Backend..."
    log_info "API will be available at: http://localhost:$API_PORT"
    log_info "WebSocket will be available at: ws://localhost:$API_PORT"
    log_info "Health check: http://localhost:$API_PORT/health"
    log_info "API docs: http://localhost:$API_PORT/docs"
    log_info "Press Ctrl+C to stop"

    # Start the backend
    uvicorn src.main:app --host 0.0.0.0 --port $API_PORT --reload
}

run_tests() {
    log_info "Running API compatibility tests..."

    # Check if backend is running
    if ! curl -s "http://localhost:$API_PORT/health" > /dev/null; then
        log_error "Backend is not running. Please start the backend first with: ./start.sh"
        exit 1
    fi

    # Run the compatibility test
    $PYTHON_CMD test_api_compatibility.py

    log_success "API compatibility tests completed"
}

setup_database() {
    log_info "Setting up database..."

    # Run database initialization
    $PYTHON_CMD -c "
from src.database import DatabaseManager
import asyncio
import sys

async def setup():
    try:
        db = DatabaseManager()
        await db.initialize()
        print('Database setup completed successfully')
    except Exception as e:
        print(f'Database setup failed: {e}')
        sys.exit(1)

asyncio.run(setup())
"

    log_success "Database setup completed"
}

show_help() {
    echo "Rowboat Python Backend Startup Script"
    echo ""
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  start      Start the backend server (default)"
    echo "  setup      Setup the environment and database"
    echo "  test       Run API compatibility tests"
    echo "  install    Install dependencies only"
    echo "  clean      Clean up virtual environment and caches"
    echo "  help       Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Start the backend"
    echo "  $0 setup              # Setup environment and start"
    echo "  $0 test               # Run compatibility tests"
    echo "  $0 clean              # Clean up everything"
}

clean_up() {
    log_warning "Cleaning up..."

    if [ -d "$VENV_DIR" ]; then
        log_info "Removing virtual environment..."
        rm -rf $VENV_DIR
    fi

    if [ -d "__pycache__" ]; then
        log_info "Removing Python cache..."
        find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    fi

    if [ -d "src/__pycache__" ]; then
        log_info "Removing source cache..."
        rm -rf src/__pycache__
    fi

    if [ -f "data/rowboat.db" ]; then
        log_info "Removing database file..."
        rm -f data/rowboat.db
    fi

    log_success "Cleanup completed"
}

# Main script logic
case "${1:-start}" in
    "start")
        check_python
        create_virtual_env
        activate_virtual_env
        install_dependencies
        check_environment
        setup_database
        start_backend
        ;;
    "setup")
        check_python
        create_virtual_env
        activate_virtual_env
        install_dependencies
        check_environment
        setup_database
        log_success "Setup completed! You can now run: ./start.sh start"
        ;;
    "test")
        activate_virtual_env 2>/dev/null || {
            log_error "Virtual environment not found. Please run setup first: ./start.sh setup"
            exit 1
        }
        run_tests
        ;;
    "install")
        check_python
        create_virtual_env
        activate_virtual_env
        install_dependencies
        ;;
    "clean")
        clean_up
        ;;
    "help")
        show_help
        ;;
    *)
        log_error "Unknown option: $1"
        show_help
        exit 1
        ;;
esac

# Deactivate virtual environment on exit
trap "deactivate 2>/dev/null || true" EXIT