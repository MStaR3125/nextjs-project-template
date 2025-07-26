"""
Autonomous Web Scraping System - FastAPI Backend

This FastAPI application provides a REST API for managing web scraping jobs.
It handles job creation, status tracking, and data retrieval with MongoDB storage.

Features:
- RESTful API endpoints for job management
- MongoDB integration with async operations
- Comprehensive error handling and validation
- CORS support for frontend integration
- Health checks and monitoring endpoints
- Structured logging for debugging
- Input validation with Pydantic models

Author: Autonomous Scraper Team
Version: 1.0.0
"""

import os
import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

# FastAPI and related imports
from fastapi import FastAPI, HTTPException, status, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

# Pydantic for data validation
from pydantic import BaseModel, HttpUrl, Field, validator
from pydantic_settings import BaseSettings

# MongoDB async driver
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo.errors import PyMongoError
from bson import ObjectId
from bson.errors import InvalidId

# Environment and utilities
from dotenv import load_dotenv
import structlog

# Load environment variables from .env file
load_dotenv()

# ==================== CONFIGURATION ====================

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    """
    # MongoDB Configuration
    mongo_url: str = Field(default="mongodb://localhost:27017", env="MONGO_URL")
    database_name: str = Field(default="scraperDB", env="DATABASE_NAME")
    collection_name: str = Field(default="jobs", env="COLLECTION_NAME")
    
    # API Configuration
    api_title: str = "Autonomous Web Scraping API"
    api_version: str = "1.0.0"
    api_description: str = "REST API for managing web scraping jobs with intelligent agents"
    
    # CORS Configuration
    cors_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    cors_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_headers: List[str] = ["*"]
    
    # Logging Configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Rate Limiting (for future implementation)
    rate_limit_requests: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    rate_limit_window: int = Field(default=60, env="RATE_LIMIT_WINDOW")
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Initialize settings
settings = Settings()

# ==================== LOGGING SETUP ====================

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = structlog.get_logger(__name__)

# ==================== DATABASE MODELS ====================

class JobStatus:
    """Constants for job status values"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class ScrapeJobRequest(BaseModel):
    """
    Request model for creating a new scraping job
    """
    url: HttpUrl = Field(..., description="Target URL to scrape")
    options: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional scraping options (timeout, headers, etc.)"
    )
    
    @validator('url')
    def validate_url(cls, v):
        """Validate URL format and accessibility"""
        url_str = str(v)
        
        # Check for common invalid patterns
        if not url_str.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        
        # Prevent localhost scraping for security (optional)
        if 'localhost' in url_str or '127.0.0.1' in url_str:
            logger.warning(f"Localhost URL submitted: {url_str}")
        
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com",
                "options": {
                    "timeout": 30,
                    "user_agent": "Autonomous Scraper Bot 1.0"
                }
            }
        }

class ScrapeJobResponse(BaseModel):
    """
    Response model for scraping job data
    """
    id: str = Field(..., alias="_id", description="Unique job identifier")
    url: str = Field(..., description="Target URL")
    status: str = Field(..., description="Current job status")
    created_at: datetime = Field(..., alias="createdAt", description="Job creation timestamp")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt", description="Last update timestamp")
    completed_at: Optional[datetime] = Field(None, alias="completedAt", description="Job completion timestamp")
    result: Optional[Dict[str, Any]] = Field(None, description="Scraped data (if completed)")
    error: Optional[str] = Field(None, description="Error message (if failed)")
    options: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Job options")
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "url": "https://example.com",
                "status": "completed",
                "created_at": "2024-01-01T12:00:00Z",
                "updated_at": "2024-01-01T12:01:00Z",
                "completed_at": "2024-01-01T12:01:00Z",
                "result": {
                    "title": "Example Website",
                    "content_length": 1024,
                    "links_found": 15
                },
                "error": None,
                "options": {}
            }
        }

class JobUpdateRequest(BaseModel):
    """
    Request model for updating job status (used by worker)
    """
    status: str = Field(..., description="New job status")
    result: Optional[Dict[str, Any]] = Field(None, description="Scraped data")
    error: Optional[str] = Field(None, description="Error message")
    
    @validator('status')
    def validate_status(cls, v):
        """Validate status is one of the allowed values"""
        allowed_statuses = [JobStatus.PENDING, JobStatus.IN_PROGRESS, JobStatus.COMPLETED, JobStatus.FAILED]
        if v not in allowed_statuses:
            raise ValueError(f'Status must be one of: {", ".join(allowed_statuses)}')
        return v

class HealthResponse(BaseModel):
    """
    Response model for health check endpoint
    """
    status: str = Field(..., description="Service health status")
    timestamp: datetime = Field(..., description="Health check timestamp")
    database: str = Field(..., description="Database connection status")
    version: str = Field(..., description="API version")

# ==================== DATABASE CONNECTION ====================

class DatabaseManager:
    """
    Manages MongoDB connection and operations
    """
    
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.database: Optional[AsyncIOMotorDatabase] = None
        self.jobs_collection: Optional[AsyncIOMotorCollection] = None
    
    async def connect(self):
        """Establish connection to MongoDB"""
        try:
            logger.info("Connecting to MongoDB", mongo_url=settings.mongo_url)
            
            self.client = AsyncIOMotorClient(
                settings.mongo_url,
                serverSelectionTimeoutMS=5000,  # 5 second timeout
                connectTimeoutMS=10000,         # 10 second connection timeout
                socketTimeoutMS=20000,          # 20 second socket timeout
            )
            
            # Test the connection
            await self.client.admin.command('ping')
            
            self.database = self.client[settings.database_name]
            self.jobs_collection = self.database[settings.collection_name]
            
            # Create indexes for better performance
            await self._create_indexes()
            
            logger.info("Successfully connected to MongoDB")
            
        except Exception as e:
            logger.error("Failed to connect to MongoDB", error=str(e))
            raise
    
    async def disconnect(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    async def _create_indexes(self):
        """Create database indexes for optimal performance"""
        try:
            # Index on status for filtering
            await self.jobs_collection.create_index("status")
            
            # Index on createdAt for sorting
            await self.jobs_collection.create_index([("createdAt", -1)])
            
            # Compound index for status and creation time
            await self.jobs_collection.create_index([("status", 1), ("createdAt", -1)])
            
            logger.info("Database indexes created successfully")
            
        except Exception as e:
            logger.warning("Failed to create database indexes", error=str(e))
    
    async def health_check(self) -> bool:
        """Check if database connection is healthy"""
        try:
            await self.client.admin.command('ping')
            return True
        except Exception:
            return False

# Global database manager instance
db_manager = DatabaseManager()

# ==================== LIFESPAN MANAGEMENT ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan events (startup and shutdown)
    """
    # Startup
    logger.info("Starting Autonomous Web Scraping API")
    await db_manager.connect()
    
    yield
    
    # Shutdown
    logger.info("Shutting down Autonomous Web Scraping API")
    await db_manager.disconnect()

# ==================== FASTAPI APPLICATION ====================

# Create FastAPI application instance
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
)

# ==================== EXCEPTION HANDLERS ====================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """Handle request validation errors"""
    logger.warning("Request validation error", errors=exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Invalid request data",
            "errors": exc.errors()
        }
    )

@app.exception_handler(PyMongoError)
async def mongodb_exception_handler(request, exc):
    """Handle MongoDB errors"""
    logger.error("MongoDB error", error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Database operation failed",
            "error": "Internal server error"
        }
    )

# ==================== UTILITY FUNCTIONS ====================

def serialize_job(job_doc: Dict) -> Dict:
    """
    Convert MongoDB document to API response format
    """
    if not job_doc:
        return None
    
    # Convert ObjectId to string
    job_doc["_id"] = str(job_doc["_id"])
    
    # Ensure datetime objects are properly formatted
    for field in ["createdAt", "updatedAt", "completedAt"]:
        if field in job_doc and job_doc[field]:
            if not isinstance(job_doc[field], datetime):
                continue
            # Ensure timezone awareness
            if job_doc[field].tzinfo is None:
                job_doc[field] = job_doc[field].replace(tzinfo=timezone.utc)
    
    return job_doc

async def get_job_by_id(job_id: str) -> Dict:
    """
    Retrieve a job by its ID with error handling
    """
    try:
        # Validate ObjectId format
        if not ObjectId.is_valid(job_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid job ID format"
            )
        
        job = await db_manager.jobs_collection.find_one({"_id": ObjectId(job_id)})
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        return serialize_job(job)
        
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid job ID format"
        )

# ==================== API ENDPOINTS ====================

@app.get("/", summary="Root endpoint")
async def root():
    """
    Root endpoint providing API information
    """
    return {
        "message": "Autonomous Web Scraping API",
        "version": settings.api_version,
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health", response_model=HealthResponse, summary="Health check")
async def health_check():
    """
    Health check endpoint for monitoring and load balancers
    """
    db_healthy = await db_manager.health_check()
    
    return HealthResponse(
        status="healthy" if db_healthy else "unhealthy",
        timestamp=datetime.now(timezone.utc),
        database="connected" if db_healthy else "disconnected",
        version=settings.api_version
    )

@app.get("/jobs", response_model=List[ScrapeJobResponse], summary="Get all jobs")
async def get_jobs(
    status_filter: Optional[str] = Query(None, description="Filter jobs by status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of jobs to return"),
    skip: int = Query(0, ge=0, description="Number of jobs to skip for pagination")
):
    """
    Retrieve all scraping jobs with optional filtering and pagination
    
    - **status_filter**: Filter jobs by status (pending, in_progress, completed, failed)
    - **limit**: Maximum number of jobs to return (1-1000)
    - **skip**: Number of jobs to skip for pagination
    """
    try:
        logger.info("Fetching jobs", status_filter=status_filter, limit=limit, skip=skip)
        
        # Build query filter
        query = {}
        if status_filter:
            query["status"] = status_filter
        
        # Execute query with pagination
        cursor = db_manager.jobs_collection.find(query).sort("createdAt", -1).skip(skip).limit(limit)
        jobs = await cursor.to_list(length=limit)
        
        # Serialize jobs for response
        serialized_jobs = [serialize_job(job) for job in jobs]
        
        logger.info("Successfully fetched jobs", count=len(serialized_jobs))
        return serialized_jobs
        
    except Exception as e:
        logger.error("Error fetching jobs", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve jobs"
        )

@app.get("/jobs/{job_id}", response_model=ScrapeJobResponse, summary="Get job by ID")
async def get_job(job_id: str):
    """
    Retrieve a specific scraping job by its ID
    
    - **job_id**: Unique identifier of the job
    """
    logger.info("Fetching job by ID", job_id=job_id)
    job = await get_job_by_id(job_id)
    return job

@app.post("/scrape", response_model=ScrapeJobResponse, status_code=status.HTTP_201_CREATED, summary="Create scraping job")
async def create_scrape_job(job_request: ScrapeJobRequest):
    """
    Create a new web scraping job
    
    - **url**: Target URL to scrape (must be valid HTTP/HTTPS URL)
    - **options**: Optional scraping parameters (timeout, headers, etc.)
    """
    try:
        logger.info("Creating new scrape job", url=str(job_request.url))
        
        # Create job document
        now = datetime.now(timezone.utc)
        job_doc = {
            "url": str(job_request.url),
            "status": JobStatus.PENDING,
            "createdAt": now,
            "updatedAt": now,
            "completedAt": None,
            "result": None,
            "error": None,
            "options": job_request.options or {}
        }
        
        # Insert job into database
        result = await db_manager.jobs_collection.insert_one(job_doc)
        
        # Retrieve the created job
        created_job = await db_manager.jobs_collection.find_one({"_id": result.inserted_id})
        serialized_job = serialize_job(created_job)
        
        logger.info("Successfully created scrape job", job_id=str(result.inserted_id))
        return serialized_job
        
    except Exception as e:
        logger.error("Error creating scrape job", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create scraping job"
        )

@app.put("/jobs/{job_id}", response_model=ScrapeJobResponse, summary="Update job status")
async def update_job(job_id: str, update_request: JobUpdateRequest):
    """
    Update a scraping job's status and results (typically used by worker)
    
    - **job_id**: Unique identifier of the job
    - **status**: New job status
    - **result**: Scraped data (if completed)
    - **error**: Error message (if failed)
    """
    try:
        logger.info("Updating job", job_id=job_id, status=update_request.status)
        
        # Validate job exists
        await get_job_by_id(job_id)
        
        # Prepare update document
        now = datetime.now(timezone.utc)
        update_doc = {
            "status": update_request.status,
            "updatedAt": now
        }
        
        # Add completion timestamp for completed/failed jobs
        if update_request.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
            update_doc["completedAt"] = now
        
        # Add result or error based on status
        if update_request.result is not None:
            update_doc["result"] = update_request.result
        
        if update_request.error is not None:
            update_doc["error"] = update_request.error
        
        # Update job in database
        await db_manager.jobs_collection.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": update_doc}
        )
        
        # Return updated job
        updated_job = await get_job_by_id(job_id)
        
        logger.info("Successfully updated job", job_id=job_id)
        return updated_job
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating job", job_id=job_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update job"
        )

@app.delete("/jobs/{job_id}", summary="Delete job")
async def delete_job(job_id: str):
    """
    Delete a scraping job
    
    - **job_id**: Unique identifier of the job to delete
    """
    try:
        logger.info("Deleting job", job_id=job_id)
        
        # Validate job exists
        await get_job_by_id(job_id)
        
        # Delete job from database
        result = await db_manager.jobs_collection.delete_one({"_id": ObjectId(job_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        logger.info("Successfully deleted job", job_id=job_id)
        return {"message": "Job deleted successfully", "job_id": job_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting job", job_id=job_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete job"
        )

@app.get("/stats", summary="Get system statistics")
async def get_stats():
    """
    Get system statistics and job counts
    """
    try:
        logger.info("Fetching system statistics")
        
        # Get job counts by status
        pipeline = [
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}}
        ]
        
        status_counts = {}
        async for doc in db_manager.jobs_collection.aggregate(pipeline):
            status_counts[doc["_id"]] = doc["count"]
        
        # Get total job count
        total_jobs = await db_manager.jobs_collection.count_documents({})
        
        # Get recent job activity (last 24 hours)
        from datetime import timedelta
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        recent_jobs = await db_manager.jobs_collection.count_documents({
            "createdAt": {"$gte": yesterday}
        })
        
        stats = {
            "total_jobs": total_jobs,
            "recent_jobs_24h": recent_jobs,
            "status_counts": status_counts,
            "timestamp": datetime.now(timezone.utc)
        }
        
        logger.info("Successfully fetched statistics", stats=stats)
        return stats
        
    except Exception as e:
        logger.error("Error fetching statistics", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )

# ==================== MAIN ENTRY POINT ====================

if __name__ == "__main__":
    import uvicorn
    
    # Run the application directly (for development)
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Enable auto-reload for development
        log_level=settings.log_level.lower()
    )
