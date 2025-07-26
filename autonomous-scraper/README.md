# Autonomous Web Scraping Agent System

A comprehensive web-based application powered by intelligent agents that autonomously discover, scrape, process, and monitor web data. Built with modern technologies and containerized for easy deployment.

## 🚀 Features

- **AI-Powered Scraping Agents:** Specialized agents for discovering, scraping, processing, and monitoring web data
- **User-Friendly Dashboard:** Modern React-based UI to submit tasks, monitor job progress, and view scraped data
- **Ethical Scraping:** Respects `robots.txt`, implements request throttling, and follows best practices
- **Scalable Architecture:** Microservices-based design using Docker containers
- **Real-time Monitoring:** Live job status updates and progress tracking
- **Robust Error Handling:** Comprehensive error management and recovery mechanisms
- **Easy Deployment:** One-command setup with Docker Compose

## 🛠 Tech Stack

- **Frontend:** React 18, Tailwind CSS, Modern JavaScript
- **Backend:** Python FastAPI, Pydantic validation, Async/await
- **Database:** MongoDB with Motor async driver
- **Scraping Engine:** Playwright (headless browsers), BeautifulSoup4
- **Containerization:** Docker, Docker Compose
- **Development:** Hot-reload, volume mounting, environment variables

## 📋 Prerequisites

Before running this application, ensure you have:

- **Docker** (version 20.0 or higher)
- **Docker Compose** (version 2.0 or higher)
- **Git** (for cloning the repository)
- At least **4GB RAM** available for containers
- **Ports 3000, 8000, 27017** available on your system

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone <repository-url>
cd autonomous-scraper
```

### 2. Build and Start All Services
```bash
# Build and start all containers in detached mode
docker-compose up --build -d

# View logs from all services
docker-compose logs -f

# View logs from specific service
docker-compose logs -f backend
```

### 3. Access the Application
- **Frontend Dashboard:** [http://localhost:3000](http://localhost:3000)
- **Backend API:** [http://localhost:8000](http://localhost:8000)
- **API Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **MongoDB:** `mongodb://localhost:27017` (if needed for direct access)

## 📖 Usage Guide

### Submitting a Scraping Job
1. Open the dashboard at [http://localhost:3000](http://localhost:3000)
2. Enter a valid URL in the input field
3. Click "Submit Scrape Job"
4. Monitor the job status in the jobs table below

### Job Status Types
- **Pending:** Job created, waiting for worker to process
- **In Progress:** Worker is actively scraping the URL
- **Completed:** Scraping finished successfully, data available
- **Failed:** Scraping encountered an error, check error details

### API Endpoints
- `GET /jobs` - Retrieve all scraping jobs
- `POST /scrape` - Submit a new scraping job
- `GET /jobs/{job_id}` - Get specific job details

## 🔧 Development

### Project Structure
```
autonomous-scraper/
├── docker-compose.yml          # Service orchestration
├── README.md                   # This file
├── frontend/                   # React application
│   ├── Dockerfile             # Frontend container config
│   ├── package.json           # Node.js dependencies
│   └── src/
│       └── App.js             # Main React component
├── backend/                    # FastAPI application
│   ├── Dockerfile             # Backend container config
│   ├── requirements.txt       # Python dependencies
│   └── main.py                # FastAPI application
└── worker/                     # Scraping worker
    ├── Dockerfile             # Worker container config
    ├── requirements.txt       # Python dependencies
    └── worker.py              # Scraping logic
```

### Running in Development Mode
```bash
# Start with hot-reload enabled
docker-compose up --build

# Rebuild specific service
docker-compose build backend
docker-compose up -d backend

# View real-time logs
docker-compose logs -f worker
```

## 🐛 Troubleshooting

### Common Issues

1. **Port Already in Use**
   ```bash
   # Check what's using the port
   lsof -i :3000
   # Kill the process or change port in docker-compose.yml
   ```

2. **MongoDB Connection Failed**
   ```bash
   # Check if MongoDB container is running
   docker-compose ps
   # Restart MongoDB service
   docker-compose restart mongo
   ```

3. **Worker Not Processing Jobs**
   ```bash
   # Check worker logs
   docker-compose logs worker
   # Restart worker service
   docker-compose restart worker
   ```

### Useful Commands
```bash
# Stop all services
docker-compose down

# Stop and remove volumes (clears database)
docker-compose down -v

# Rebuild without cache
docker-compose build --no-cache

# Execute command in running container
docker-compose exec backend bash

# Monitor resource usage
docker stats
```

## 🔄 Production Deployment

### Environment Variables
- `MONGO_URL`: MongoDB connection string
- `DATABASE_NAME`: Database name (default: scraperDB)
- `COLLECTION_NAME`: Collection name (default: jobs)
- `POLL_INTERVAL`: Worker polling interval in seconds
- `REACT_APP_API_URL`: Backend API URL for frontend

### Security Considerations
- **Rate Limiting:** Implement rate limiting for API endpoints
- **Authentication:** Add user authentication for job management
- **Input Validation:** All URLs are validated before processing
- **Network Security:** Services communicate through isolated Docker network

## 📝 License

This project is licensed under the MIT License.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request
