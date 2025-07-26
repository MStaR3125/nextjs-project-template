# Autonomous Web Scraping System - Project Structure

This document provides a comprehensive overview of the project structure, components, and their relationships.

## 📁 Directory Structure

```
autonomous-scraper/
├── 📄 README.md                    # Main project documentation
├── 📄 PROJECT_STRUCTURE.md         # This file - project overview
├── 📄 docker-compose.yml           # Docker orchestration configuration
├── 📄 .env.example                 # Environment variables template
├── 📄 .gitignore                   # Git ignore rules
├── 🔧 start.sh                     # System management script
├── 🧪 test_system.py               # Comprehensive test suite
│
├── 📁 frontend/                     # React frontend application
│   ├── 📄 Dockerfile               # Frontend container configuration
│   ├── 📄 package.json             # Node.js dependencies and scripts
│   ├── 📁 public/
│   │   └── 📄 index.html            # HTML template with Tailwind CSS
│   └── 📁 src/
│       ├── 📄 index.js              # React application entry point
│       ├── 📄 index.css             # Tailwind CSS and custom styles
│       └── 📄 App.js                # Main React component with dashboard
│
├── 📁 backend/                      # FastAPI backend application
│   ├── 📄 Dockerfile               # Backend container configuration
│   ├── 📄 requirements.txt         # Python dependencies
│   └── 📄 main.py                  # FastAPI application with REST API
│
└── 📁 worker/                       # Python scraping worker
    ├── 📄 Dockerfile               # Worker container configuration
    ├── 📄 requirements.txt         # Python scraping dependencies
    └── 📄 worker.py                # Scraping worker with intelligent agents
```

## 🏗️ System Architecture

### Components Overview

1. **Frontend (React + Tailwind CSS)**
   - Modern, responsive web dashboard
   - Job submission and monitoring interface
   - Real-time status updates
   - Clean, icon-free design

2. **Backend (FastAPI + MongoDB)**
   - RESTful API for job management
   - Async operations with Motor driver
   - Comprehensive error handling
   - API documentation with Swagger

3. **Worker (Python + Playwright + BeautifulSoup)**
   - Intelligent scraping agents
   - Browser automation with Playwright
   - Content extraction and analysis
   - Ethical scraping practices

4. **Database (MongoDB)**
   - Job storage and management
   - Persistent data with Docker volumes
   - Indexed for optimal performance

### Data Flow

```
User → Frontend → Backend API → MongoDB ← Worker
  ↑                                         ↓
  └─────── Real-time Updates ←──────────────┘
```

## 🔧 Key Features

### Frontend Features
- **Job Submission**: Easy URL input with validation
- **Real-time Monitoring**: Live job status updates
- **Pagination**: Handle large job lists efficiently
- **Filtering**: Filter jobs by status
- **Auto-refresh**: Configurable automatic updates
- **Responsive Design**: Works on all device sizes
- **Error Handling**: User-friendly error messages

### Backend Features
- **RESTful API**: Standard HTTP methods and status codes
- **Async Operations**: High-performance async/await patterns
- **Data Validation**: Pydantic models for request/response validation
- **Error Handling**: Comprehensive exception handling
- **Health Checks**: System monitoring endpoints
- **CORS Support**: Cross-origin resource sharing
- **API Documentation**: Auto-generated Swagger docs

### Worker Features
- **Intelligent Agents**: Specialized agents for different tasks
- **Robots.txt Compliance**: Ethical scraping practices
- **Content Extraction**: Comprehensive data extraction
- **Screenshot Capture**: Visual page capture
- **Rate Limiting**: Respectful request throttling
- **Error Recovery**: Robust error handling and retry logic
- **Performance Monitoring**: Resource usage tracking

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose installed
- At least 4GB RAM available
- Ports 3000, 8000, 27017 available

### Starting the System
```bash
# Navigate to project directory
cd autonomous-scraper

# Start all services
./start.sh start

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Testing the System
```bash
# Run comprehensive tests
python test_system.py

# View system status
./start.sh status

# View logs
./start.sh logs
```

## 📊 API Endpoints

### Core Endpoints
- `GET /` - API information
- `GET /health` - Health check
- `GET /jobs` - List all jobs (with pagination and filtering)
- `GET /jobs/{job_id}` - Get specific job details
- `POST /scrape` - Create new scraping job
- `PUT /jobs/{job_id}` - Update job status (worker use)
- `DELETE /jobs/{job_id}` - Delete job
- `GET /stats` - System statistics

## 🔄 Job Lifecycle

1. **Creation**: User submits URL via frontend
2. **Storage**: Backend validates and stores job in MongoDB
3. **Discovery**: Worker polls database for pending jobs
4. **Processing**: Worker scrapes URL using Playwright
5. **Extraction**: Content extracted using BeautifulSoup
6. **Storage**: Results stored back to MongoDB
7. **Notification**: Frontend displays updated status

### Job Status Flow
```
pending → in_progress → completed
                    ↘ failed
```

## 🛠️ Management Commands

```bash
# System Management
./start.sh start      # Start all services
./start.sh stop       # Stop all services
./start.sh restart    # Restart all services
./start.sh status     # Show system status

# Monitoring
./start.sh logs       # View all logs
./start.sh logs backend  # View specific service logs

# Maintenance
./start.sh backup     # Backup database
./start.sh cleanup    # Clean up system
./start.sh test       # Run health tests
```

## 🔒 Security Features

- **Non-root containers**: All services run as non-root users
- **Input validation**: Comprehensive URL and data validation
- **Rate limiting**: Request throttling to prevent abuse
- **Network isolation**: Services communicate via Docker network
- **Robots.txt compliance**: Respects website scraping policies
- **Error sanitization**: Sensitive information not exposed

## 📈 Performance Features

- **Async operations**: Non-blocking I/O throughout
- **Database indexing**: Optimized queries with indexes
- **Connection pooling**: Efficient database connections
- **Resource monitoring**: CPU and memory tracking
- **Concurrent processing**: Multiple worker jobs simultaneously

## 🧪 Testing Strategy

The system includes comprehensive testing:
- **Health checks**: Service availability testing
- **API testing**: Endpoint functionality verification
- **End-to-end testing**: Complete workflow validation
- **Error handling**: Failure scenario testing
- **Performance testing**: Response time validation

## 📝 Configuration

### Environment Variables
Key configuration options in `.env`:
- `MONGO_URL`: Database connection
- `POLL_INTERVAL`: Worker polling frequency
- `MAX_CONCURRENT_JOBS`: Worker job limit
- `DEFAULT_TIMEOUT`: Scraping timeout
- `LOG_LEVEL`: Logging verbosity

### Customization
- **Worker behavior**: Modify polling, timeouts, concurrency
- **API settings**: CORS, rate limiting, authentication
- **Frontend**: Styling, refresh intervals, pagination
- **Database**: Indexing, connection pooling

## 🚀 Deployment Options

### Development
```bash
./start.sh start
```

### Production
- Docker Swarm for multi-node deployment
- Kubernetes for enterprise orchestration
- Cloud services (AWS ECS, Google Cloud Run)
- Traditional servers with reverse proxy

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Submit pull request

### Code Standards
- Python: PEP 8 compliance
- JavaScript: ESLint configuration
- Documentation: Comprehensive comments
- Testing: Test coverage requirements

## 📞 Support

### Troubleshooting
- Check logs: `./start.sh logs`
- Run tests: `python test_system.py`
- Verify status: `./start.sh status`
- Review documentation: `README.md`

### Common Issues
- Port conflicts: Check port availability
- Memory issues: Increase Docker limits
- Permission errors: Check file permissions
- Network problems: Verify Docker network

---

**Version**: 1.0.0  
**Last Updated**: January 2024  
**Maintainer**: Autonomous Scraper Team
