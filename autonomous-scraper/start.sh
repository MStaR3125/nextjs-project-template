#!/bin/bash

# Autonomous Web Scraping System - Startup Script
# This script provides easy commands to manage the scraping system

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if Docker is running
check_docker() {
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
}

# Function to check if Docker Compose is available
check_docker_compose() {
    if ! command -v docker-compose >/dev/null 2>&1; then
        print_error "Docker Compose is not installed. Please install Docker Compose and try again."
        exit 1
    fi
}

# Function to create .env file if it doesn't exist
setup_env() {
    if [ ! -f .env ]; then
        print_status "Creating .env file from template..."
        cp .env.example .env
        print_success ".env file created. You may want to customize it before starting the system."
    fi
}

# Function to check system requirements
check_requirements() {
    print_status "Checking system requirements..."
    
    # Check available memory
    if command -v free >/dev/null 2>&1; then
        AVAILABLE_MEM=$(free -m | awk 'NR==2{printf "%.0f", $7}')
        if [ "$AVAILABLE_MEM" -lt 2048 ]; then
            print_warning "Available memory is ${AVAILABLE_MEM}MB. Recommended: 4GB or more."
        fi
    fi
    
    # Check available disk space
    if command -v df >/dev/null 2>&1; then
        AVAILABLE_DISK=$(df -BG . | awk 'NR==2{print $4}' | sed 's/G//')
        if [ "$AVAILABLE_DISK" -lt 5 ]; then
            print_warning "Available disk space is ${AVAILABLE_DISK}GB. Recommended: 10GB or more."
        fi
    fi
    
    # Check if required ports are available
    check_port() {
        local port=$1
        local service=$2
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            print_warning "Port $port is already in use. This may conflict with $service."
        fi
    }
    
    check_port 3000 "Frontend"
    check_port 8000 "Backend API"
    check_port 27017 "MongoDB"
}

# Function to build and start all services
start_system() {
    print_status "Starting Autonomous Web Scraping System..."
    
    check_docker
    check_docker_compose
    setup_env
    check_requirements
    
    print_status "Building and starting Docker containers..."
    docker-compose up --build -d
    
    print_status "Waiting for services to be ready..."
    sleep 10
    
    # Check if services are running
    if docker-compose ps | grep -q "Up"; then
        print_success "System started successfully!"
        echo
        echo "🌐 Frontend Dashboard: http://localhost:3000"
        echo "🔧 Backend API: http://localhost:8000"
        echo "📚 API Documentation: http://localhost:8000/docs"
        echo "🗄️  MongoDB: mongodb://localhost:27017"
        echo
        print_status "Use './start.sh logs' to view logs"
        print_status "Use './start.sh stop' to stop the system"
    else
        print_error "Some services failed to start. Check logs with './start.sh logs'"
        exit 1
    fi
}

# Function to stop all services
stop_system() {
    print_status "Stopping Autonomous Web Scraping System..."
    docker-compose down
    print_success "System stopped successfully!"
}

# Function to restart all services
restart_system() {
    print_status "Restarting Autonomous Web Scraping System..."
    docker-compose restart
    print_success "System restarted successfully!"
}

# Function to view logs
view_logs() {
    local service=$1
    if [ -z "$service" ]; then
        print_status "Showing logs for all services (press Ctrl+C to exit)..."
        docker-compose logs -f
    else
        print_status "Showing logs for $service (press Ctrl+C to exit)..."
        docker-compose logs -f "$service"
    fi
}

# Function to show system status
show_status() {
    print_status "System Status:"
    echo
    docker-compose ps
    echo
    
    # Show resource usage
    print_status "Resource Usage:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
}

# Function to clean up system
cleanup_system() {
    print_warning "This will remove all containers, images, and volumes. Are you sure? (y/N)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        print_status "Cleaning up system..."
        docker-compose down -v --rmi all
        docker system prune -f
        print_success "System cleaned up successfully!"
    else
        print_status "Cleanup cancelled."
    fi
}

# Function to backup data
backup_data() {
    print_status "Creating backup of MongoDB data..."
    
    BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    # Export MongoDB data
    docker-compose exec -T mongo mongodump --db scraperDB --out /tmp/backup
    docker cp $(docker-compose ps -q mongo):/tmp/backup "$BACKUP_DIR/"
    
    print_success "Backup created in $BACKUP_DIR"
}

# Function to restore data
restore_data() {
    local backup_path=$1
    if [ -z "$backup_path" ]; then
        print_error "Please specify backup path: ./start.sh restore /path/to/backup"
        exit 1
    fi
    
    if [ ! -d "$backup_path" ]; then
        print_error "Backup directory not found: $backup_path"
        exit 1
    fi
    
    print_status "Restoring data from $backup_path..."
    
    # Copy backup to container and restore
    docker cp "$backup_path" $(docker-compose ps -q mongo):/tmp/restore
    docker-compose exec -T mongo mongorestore --db scraperDB --drop /tmp/restore/scraperDB
    
    print_success "Data restored successfully!"
}

# Function to run tests
run_tests() {
    print_status "Running system tests..."
    
    # Test backend API
    print_status "Testing backend API..."
    if curl -f http://localhost:8000/health >/dev/null 2>&1; then
        print_success "Backend API is responding"
    else
        print_error "Backend API is not responding"
    fi
    
    # Test frontend
    print_status "Testing frontend..."
    if curl -f http://localhost:3000 >/dev/null 2>&1; then
        print_success "Frontend is responding"
    else
        print_error "Frontend is not responding"
    fi
    
    # Test MongoDB
    print_status "Testing MongoDB connection..."
    if docker-compose exec -T mongo mongo --eval "db.adminCommand('ping')" >/dev/null 2>&1; then
        print_success "MongoDB is responding"
    else
        print_error "MongoDB is not responding"
    fi
}

# Function to update system
update_system() {
    print_status "Updating system..."
    
    # Pull latest images
    docker-compose pull
    
    # Rebuild and restart
    docker-compose up --build -d
    
    print_success "System updated successfully!"
}

# Function to show help
show_help() {
    echo "Autonomous Web Scraping System - Management Script"
    echo
    echo "Usage: $0 [COMMAND]"
    echo
    echo "Commands:"
    echo "  start       Start the entire system"
    echo "  stop        Stop the entire system"
    echo "  restart     Restart the entire system"
    echo "  status      Show system status and resource usage"
    echo "  logs [SERVICE]  Show logs (all services or specific service)"
    echo "  test        Run system health tests"
    echo "  backup      Create a backup of the database"
    echo "  restore PATH    Restore database from backup"
    echo "  update      Update system to latest version"
    echo "  cleanup     Remove all containers, images, and volumes"
    echo "  help        Show this help message"
    echo
    echo "Services: frontend, backend, worker, mongo"
    echo
    echo "Examples:"
    echo "  $0 start                 # Start the system"
    echo "  $0 logs backend          # Show backend logs"
    echo "  $0 logs                  # Show all logs"
    echo "  $0 backup                # Create backup"
    echo "  $0 restore ./backups/20240101_120000  # Restore from backup"
    echo
}

# Main script logic
case "${1:-}" in
    start)
        start_system
        ;;
    stop)
        stop_system
        ;;
    restart)
        restart_system
        ;;
    status)
        show_status
        ;;
    logs)
        view_logs "$2"
        ;;
    test)
        run_tests
        ;;
    backup)
        backup_data
        ;;
    restore)
        restore_data "$2"
        ;;
    update)
        update_system
        ;;
    cleanup)
        cleanup_system
        ;;
    help|--help|-h)
        show_help
        ;;
    "")
        print_error "No command specified. Use '$0 help' for usage information."
        exit 1
        ;;
    *)
        print_error "Unknown command: $1. Use '$0 help' for usage information."
        exit 1
        ;;
esac
