"""
Autonomous Web Scraping Worker

This worker continuously polls the MongoDB database for pending scraping jobs,
processes them using Playwright and BeautifulSoup, and updates the job status
with results or error information.

Features:
- Intelligent job polling with exponential backoff
- Robust web scraping with multiple fallback strategies
- Comprehensive error handling and recovery
- Respect for robots.txt and ethical scraping practices
- Content extraction and analysis
- Screenshot capture capabilities
- Rate limiting and request throttling
- Structured logging for monitoring

Author: Autonomous Scraper Team
Version: 1.0.0
"""

import os
import asyncio
import logging
import json
import time
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urljoin, urlparse, robots
from urllib.robotparser import RobotFileParser

# Core dependencies
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from dotenv import load_dotenv
import structlog

# Web scraping dependencies
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from bs4 import BeautifulSoup, Comment
import httpx
import aiofiles

# Data processing
import pandas as pd
from textstat import flesch_reading_ease, automated_readability_index
import validators
from urllib.parse import urljoin, urlparse

# Utilities
import backoff
from tenacity import retry, stop_after_attempt, wait_exponential
import psutil

# Load environment variables
load_dotenv()

# ==================== CONFIGURATION ====================

class WorkerConfig:
    """Configuration settings for the scraping worker"""
    
    # MongoDB Configuration
    MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "scraperDB")
    COLLECTION_NAME = os.getenv("COLLECTION_NAME", "jobs")
    
    # Worker Configuration
    POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "5"))  # seconds
    MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "3"))
    WORKER_ID = os.getenv("WORKER_ID", f"worker-{os.getpid()}")
    
    # Scraping Configuration
    DEFAULT_TIMEOUT = int(os.getenv("DEFAULT_TIMEOUT", "30"))  # seconds
    MAX_PAGE_SIZE = int(os.getenv("MAX_PAGE_SIZE", "10")) * 1024 * 1024  # 10MB
    USER_AGENT = os.getenv("USER_AGENT", "Autonomous-Scraper-Bot/1.0 (+https://github.com/autonomous-scraper)")
    
    # Browser Configuration
    HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
    BROWSER_TYPE = os.getenv("BROWSER_TYPE", "chromium")  # chromium, firefox, webkit
    
    # Rate Limiting
    MIN_REQUEST_DELAY = float(os.getenv("MIN_REQUEST_DELAY", "1.0"))  # seconds
    MAX_REQUEST_DELAY = float(os.getenv("MAX_REQUEST_DELAY", "5.0"))  # seconds
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # File Storage
    SCREENSHOTS_DIR = os.getenv("SCREENSHOTS_DIR", "/app/temp/screenshots")
    LOGS_DIR = os.getenv("LOGS_DIR", "/app/logs")

config = WorkerConfig()

# ==================== LOGGING SETUP ====================

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = structlog.get_logger(__name__)

# ==================== JOB STATUS CONSTANTS ====================

class JobStatus:
    """Job status constants"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

# ==================== SCRAPING AGENTS ====================

class RobotsChecker:
    """
    Agent responsible for checking robots.txt compliance
    """
    
    def __init__(self):
        self.cache = {}  # Cache robots.txt files
        self.cache_ttl = 3600  # 1 hour TTL
    
    async def can_fetch(self, url: str, user_agent: str = "*") -> bool:
        """
        Check if the URL can be fetched according to robots.txt
        """
        try:
            parsed_url = urlparse(url)
            robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
            
            # Check cache first
            cache_key = f"{robots_url}:{user_agent}"
            if cache_key in self.cache:
                cached_data, timestamp = self.cache[cache_key]
                if time.time() - timestamp < self.cache_ttl:
                    return cached_data
            
            # Fetch robots.txt
            async with httpx.AsyncClient(timeout=10.0) as client:
                try:
                    response = await client.get(robots_url)
                    if response.status_code == 200:
                        rp = RobotFileParser()
                        rp.set_url(robots_url)
                        rp.read()
                        
                        can_fetch = rp.can_fetch(user_agent, url)
                        
                        # Cache the result
                        self.cache[cache_key] = (can_fetch, time.time())
                        
                        logger.info("Robots.txt check completed", 
                                  url=url, can_fetch=can_fetch)
                        return can_fetch
                    else:
                        # If robots.txt doesn't exist, assume we can fetch
                        logger.info("No robots.txt found, allowing fetch", url=url)
                        return True
                        
                except Exception as e:
                    logger.warning("Error fetching robots.txt", 
                                 robots_url=robots_url, error=str(e))
                    return True  # Default to allowing if we can't check
                    
        except Exception as e:
            logger.error("Error in robots.txt check", url=url, error=str(e))
            return True  # Default to allowing on error

class ContentExtractor:
    """
    Agent responsible for extracting and analyzing content from web pages
    """
    
    def __init__(self):
        self.extractors = {
            'title': self._extract_title,
            'meta_description': self._extract_meta_description,
            'headings': self._extract_headings,
            'links': self._extract_links,
            'images': self._extract_images,
            'text_content': self._extract_text_content,
            'forms': self._extract_forms,
            'tables': self._extract_tables,
            'social_media': self._extract_social_media,
            'contact_info': self._extract_contact_info
        }
    
    async def extract_content(self, html: str, base_url: str) -> Dict[str, Any]:
        """
        Extract comprehensive content from HTML
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Remove comments
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()
            
            results = {}
            
            # Run all extractors
            for name, extractor in self.extractors.items():
                try:
                    results[name] = await extractor(soup, base_url)
                except Exception as e:
                    logger.warning(f"Error in {name} extraction", error=str(e))
                    results[name] = None
            
            # Add content analysis
            results['analysis'] = await self._analyze_content(soup)
            
            # Add page statistics
            results['statistics'] = await self._calculate_statistics(soup, html)
            
            return results
            
        except Exception as e:
            logger.error("Error in content extraction", error=str(e))
            return {"error": str(e)}
    
    async def _extract_title(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Extract page title"""
        title_tag = soup.find('title')
        return title_tag.get_text().strip() if title_tag else None
    
    async def _extract_meta_description(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Extract meta description"""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        return meta_desc.get('content', '').strip() if meta_desc else None
    
    async def _extract_headings(self, soup: BeautifulSoup, base_url: str) -> Dict[str, List[str]]:
        """Extract all headings (h1-h6)"""
        headings = {}
        for i in range(1, 7):
            tag_name = f'h{i}'
            tags = soup.find_all(tag_name)
            headings[tag_name] = [tag.get_text().strip() for tag in tags]
        return headings
    
    async def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        """Extract all links"""
        links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            absolute_url = urljoin(base_url, href)
            links.append({
                'text': link.get_text().strip(),
                'href': href,
                'absolute_url': absolute_url,
                'is_external': urlparse(absolute_url).netloc != urlparse(base_url).netloc
            })
        return links
    
    async def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        """Extract all images"""
        images = []
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if src:
                absolute_url = urljoin(base_url, src)
                images.append({
                    'src': src,
                    'absolute_url': absolute_url,
                    'alt': img.get('alt', ''),
                    'title': img.get('title', '')
                })
        return images
    
    async def _extract_text_content(self, soup: BeautifulSoup, base_url: str) -> Dict[str, Any]:
        """Extract and analyze text content"""
        # Get all text content
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return {
            'full_text': text,
            'word_count': len(text.split()),
            'character_count': len(text),
            'paragraph_count': len(soup.find_all('p'))
        }
    
    async def _extract_forms(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
        """Extract form information"""
        forms = []
        for form in soup.find_all('form'):
            form_data = {
                'action': form.get('action', ''),
                'method': form.get('method', 'get').lower(),
                'inputs': []
            }
            
            # Extract form inputs
            for input_tag in form.find_all(['input', 'textarea', 'select']):
                input_data = {
                    'type': input_tag.get('type', 'text'),
                    'name': input_tag.get('name', ''),
                    'id': input_tag.get('id', ''),
                    'placeholder': input_tag.get('placeholder', ''),
                    'required': input_tag.has_attr('required')
                }
                form_data['inputs'].append(input_data)
            
            forms.append(form_data)
        
        return forms
    
    async def _extract_tables(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
        """Extract table data"""
        tables = []
        for table in soup.find_all('table'):
            table_data = {
                'headers': [],
                'rows': [],
                'caption': ''
            }
            
            # Extract caption
            caption = table.find('caption')
            if caption:
                table_data['caption'] = caption.get_text().strip()
            
            # Extract headers
            header_row = table.find('tr')
            if header_row:
                headers = header_row.find_all(['th', 'td'])
                table_data['headers'] = [header.get_text().strip() for header in headers]
            
            # Extract rows
            rows = table.find_all('tr')[1:]  # Skip header row
            for row in rows:
                cells = row.find_all(['td', 'th'])
                row_data = [cell.get_text().strip() for cell in cells]
                table_data['rows'].append(row_data)
            
            tables.append(table_data)
        
        return tables
    
    async def _extract_social_media(self, soup: BeautifulSoup, base_url: str) -> Dict[str, List[str]]:
        """Extract social media links"""
        social_platforms = {
            'facebook': ['facebook.com', 'fb.com'],
            'twitter': ['twitter.com', 'x.com'],
            'linkedin': ['linkedin.com'],
            'instagram': ['instagram.com'],
            'youtube': ['youtube.com', 'youtu.be'],
            'tiktok': ['tiktok.com'],
            'pinterest': ['pinterest.com']
        }
        
        social_links = {platform: [] for platform in social_platforms}
        
        for link in soup.find_all('a', href=True):
            href = link['href'].lower()
            for platform, domains in social_platforms.items():
                if any(domain in href for domain in domains):
                    social_links[platform].append(link['href'])
        
        return social_links
    
    async def _extract_contact_info(self, soup: BeautifulSoup, base_url: str) -> Dict[str, List[str]]:
        """Extract contact information"""
        import re
        
        text = soup.get_text()
        
        # Email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        
        # Phone pattern (basic)
        phone_pattern = r'(\+?1?[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})'
        phones = re.findall(phone_pattern, text)
        phone_numbers = [''.join(phone) for phone in phones]
        
        return {
            'emails': list(set(emails)),
            'phones': list(set(phone_numbers))
        }
    
    async def _analyze_content(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Analyze content quality and characteristics"""
        text = soup.get_text()
        
        analysis = {
            'readability_score': 0,
            'reading_level': 'unknown',
            'has_structured_data': False,
            'has_breadcrumbs': False,
            'has_navigation': False
        }
        
        try:
            # Readability analysis
            if len(text) > 100:  # Only analyze if there's enough text
                analysis['readability_score'] = flesch_reading_ease(text)
                analysis['automated_readability_index'] = automated_readability_index(text)
        except:
            pass
        
        # Check for structured data
        structured_data_selectors = [
            'script[type="application/ld+json"]',
            '[itemscope]',
            '[property^="og:"]',
            '[name^="twitter:"]'
        ]
        
        for selector in structured_data_selectors:
            if soup.select(selector):
                analysis['has_structured_data'] = True
                break
        
        # Check for breadcrumbs
        breadcrumb_selectors = [
            '.breadcrumb',
            '.breadcrumbs',
            '[aria-label*="breadcrumb"]',
            'nav ol',
            'nav ul'
        ]
        
        for selector in breadcrumb_selectors:
            if soup.select(selector):
                analysis['has_breadcrumbs'] = True
                break
        
        # Check for navigation
        nav_elements = soup.find_all(['nav', 'header', 'menu'])
        analysis['has_navigation'] = len(nav_elements) > 0
        
        return analysis
    
    async def _calculate_statistics(self, soup: BeautifulSoup, html: str) -> Dict[str, Any]:
        """Calculate page statistics"""
        return {
            'html_size': len(html),
            'dom_elements': len(soup.find_all()),
            'links_count': len(soup.find_all('a')),
            'images_count': len(soup.find_all('img')),
            'forms_count': len(soup.find_all('form')),
            'tables_count': len(soup.find_all('table')),
            'scripts_count': len(soup.find_all('script')),
            'stylesheets_count': len(soup.find_all('link', rel='stylesheet'))
        }

class ScreenshotAgent:
    """
    Agent responsible for capturing screenshots of web pages
    """
    
    def __init__(self):
        self.screenshots_dir = config.SCREENSHOTS_DIR
        os.makedirs(self.screenshots_dir, exist_ok=True)
    
    async def capture_screenshot(self, page: Page, job_id: str) -> Optional[str]:
        """
        Capture a screenshot of the current page
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{job_id}_{timestamp}.png"
            filepath = os.path.join(self.screenshots_dir, filename)
            
            # Capture full page screenshot
            await page.screenshot(
                path=filepath,
                full_page=True,
                type='png'
            )
            
            logger.info("Screenshot captured", job_id=job_id, filepath=filepath)
            return filepath
            
        except Exception as e:
            logger.error("Error capturing screenshot", job_id=job_id, error=str(e))
            return None

class ScrapingWorker:
    """
    Main scraping worker that orchestrates all agents
    """
    
    def __init__(self):
        self.client = None
        self.database = None
        self.jobs_collection = None
        self.browser = None
        self.context = None
        
        # Initialize agents
        self.robots_checker = RobotsChecker()
        self.content_extractor = ContentExtractor()
        self.screenshot_agent = ScreenshotAgent()
        
        # Worker state
        self.is_running = False
        self.current_jobs = set()
        self.last_activity = datetime.now()
        
        # Performance tracking
        self.jobs_processed = 0
        self.jobs_succeeded = 0
        self.jobs_failed = 0
        self.start_time = datetime.now()
    
    async def initialize(self):
        """Initialize database connection and browser"""
        try:
            logger.info("Initializing scraping worker", worker_id=config.WORKER_ID)
            
            # Connect to MongoDB
            self.client = AsyncIOMotorClient(config.MONGO_URL)
            self.database = self.client[config.DATABASE_NAME]
            self.jobs_collection = self.database[config.COLLECTION_NAME]
            
            # Test database connection
            await self.client.admin.command('ping')
            logger.info("Connected to MongoDB successfully")
            
            # Initialize browser
            await self._initialize_browser()
            
            logger.info("Worker initialization completed")
            
        except Exception as e:
            logger.error("Failed to initialize worker", error=str(e))
            raise
    
    async def _initialize_browser(self):
        """Initialize Playwright browser"""
        try:
            playwright = await async_playwright().start()
            
            # Choose browser type
            if config.BROWSER_TYPE == "firefox":
                browser_type = playwright.firefox
            elif config.BROWSER_TYPE == "webkit":
                browser_type = playwright.webkit
            else:
                browser_type = playwright.chromium
            
            # Launch browser
            self.browser = await browser_type.launch(
                headless=config.HEADLESS,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor'
                ]
            )
            
            # Create browser context
            self.context = await self.browser.new_context(
                user_agent=config.USER_AGENT,
                viewport={'width': 1920, 'height': 1080},
                ignore_https_errors=True
            )
            
            logger.info("Browser initialized successfully", browser_type=config.BROWSER_TYPE)
            
        except Exception as e:
            logger.error("Failed to initialize browser", error=str(e))
            raise
    
    async def start(self):
        """Start the worker main loop"""
        self.is_running = True
        logger.info("Starting scraping worker main loop")
        
        try:
            while self.is_running:
                await self._process_jobs()
                await asyncio.sleep(config.POLL_INTERVAL)
                
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        except Exception as e:
            logger.error("Error in worker main loop", error=str(e))
        finally:
            await self.shutdown()
    
    async def _process_jobs(self):
        """Process pending jobs"""
        try:
            # Check if we can take more jobs
            if len(self.current_jobs) >= config.MAX_CONCURRENT_JOBS:
                return
            
            # Find pending jobs
            jobs_to_process = config.MAX_CONCURRENT_JOBS - len(self.current_jobs)
            
            cursor = self.jobs_collection.find(
                {"status": JobStatus.PENDING}
            ).sort("createdAt", 1).limit(jobs_to_process)
            
            jobs = await cursor.to_list(length=jobs_to_process)
            
            if not jobs:
                return
            
            logger.info(f"Found {len(jobs)} pending jobs to process")
            
            # Process jobs concurrently
            tasks = []
            for job in jobs:
                if job["_id"] not in self.current_jobs:
                    self.current_jobs.add(job["_id"])
                    task = asyncio.create_task(self._process_single_job(job))
                    tasks.append(task)
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                
        except Exception as e:
            logger.error("Error processing jobs", error=str(e))
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def _process_single_job(self, job: Dict):
        """Process a single scraping job"""
        job_id = job["_id"]
        url = job["url"]
        
        try:
            logger.info("Starting job processing", job_id=str(job_id), url=url)
            
            # Update job status to in_progress
            await self._update_job_status(job_id, JobStatus.IN_PROGRESS)
            
            # Check robots.txt compliance
            if not await self.robots_checker.can_fetch(url, config.USER_AGENT):
                raise Exception("Robots.txt disallows fetching this URL")
            
            # Add delay for rate limiting
            await asyncio.sleep(config.MIN_REQUEST_DELAY)
            
            # Scrape the page
            result = await self._scrape_page(job_id, url, job.get("options", {}))
            
            # Update job with results
            await self._update_job_status(
                job_id, 
                JobStatus.COMPLETED, 
                result=result
            )
            
            self.jobs_succeeded += 1
            logger.info("Job completed successfully", job_id=str(job_id))
            
        except Exception as e:
            logger.error("Job failed", job_id=str(job_id), error=str(e))
            
            # Update job with error
            await self._update_job_status(
                job_id,
                JobStatus.FAILED,
                error=str(e)
            )
            
            self.jobs_failed += 1
            
        finally:
            # Remove job from current jobs set
            self.current_jobs.discard(job_id)
            self.jobs_processed += 1
            self.last_activity = datetime.now()
    
    async def _scrape_page(self, job_id: ObjectId, url: str, options: Dict) -> Dict[str, Any]:
        """Scrape a single web page"""
        page = None
        
        try:
            # Create new page
            page = await self.context.new_page()
            
            # Set timeout
            timeout = options.get('timeout', config.DEFAULT_TIMEOUT) * 1000  # Convert to ms
            page.set_default_timeout(timeout)
            
            # Navigate to page
            logger.info("Navigating to page", job_id=str(job_id), url=url)
            
            response = await page.goto(
                url,
                wait_until='domcontentloaded',
                timeout=timeout
            )
            
            if not response:
                raise Exception("Failed to load page - no response")
            
            if response.status >= 400:
                raise Exception(f"HTTP {response.status}: {response.status_text}")
            
            # Wait for page to be fully loaded
            await page.wait_for_load_state('networkidle', timeout=timeout)
            
            # Get page content
            html_content = await page.content()
            
            if len(html_content) > config.MAX_PAGE_SIZE:
                raise Exception(f"Page size ({len(html_content)} bytes) exceeds maximum allowed size")
            
            # Extract content using ContentExtractor
            extracted_content = await self.content_extractor.extract_content(html_content, url)
            
            # Capture screenshot
            screenshot_path = await self.screenshot_agent.capture_screenshot(page, str(job_id))
            
            # Compile results
            result = {
                'url': url,
                'status_code': response.status,
                'content_type': response.headers.get('content-type', ''),
                'content_length': len(html_content),
                'scraped_at': datetime.now(timezone.utc).isoformat(),
                'screenshot_path': screenshot_path,
                'content': extracted_content,
                'performance': {
                    'load_time': None,  # Could be calculated if needed
                    'dom_elements': extracted_content.get('statistics', {}).get('dom_elements', 0)
                }
            }
            
            logger.info("Page scraped successfully", 
                       job_id=str(job_id), 
                       content_length=len(html_content))
            
            return result
            
        except Exception as e:
            logger.error("Error scraping page", job_id=str(job_id), url=url, error=str(e))
            raise
            
        finally:
            if page:
                await page.close()
    
    async def _update_job_status(self, job_id: ObjectId, status: str, result: Dict = None, error: str = None):
        """Update job status in database"""
        try:
            update_doc = {
                "status": status,
                "updatedAt": datetime.now(timezone.utc)
            }
            
            if status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                update_doc["completedAt"] = datetime.now(timezone.utc)
            
            if result:
                update_doc["result"] = result
            
            if error:
                update_doc["error"] = error
            
            await self.jobs_collection.update_one(
                {"_id": job_id},
                {"$set": update_doc}
            )
            
            logger.debug("Job status updated", job_id=str(job_id), status=status)
            
        except Exception as e:
            logger.error("Failed to update job status", job_id=str(job_id), error=str(e))
    
    async def get_worker_stats(self) -> Dict[str, Any]:
        """Get worker performance statistics"""
        uptime = datetime.now() - self.start_time
        
        return {
            'worker_id': config.WORKER_ID,
            'status': 'running' if self.is_running else 'stopped',
            'uptime_seconds': uptime.total_seconds(),
            'jobs_processed': self.jobs_processed,
            'jobs_succeeded': self.jobs_succeeded,
            'jobs_failed': self.jobs_failed,
            'success_rate': (self.jobs_succeeded / max(self.jobs_processed, 1)) * 100,
            'current_jobs': len(self.current_jobs),
            'last_activity': self.last_activity.isoformat(),
            'memory_usage': psutil.Process().memory_info().rss / 1024 / 1024,  # MB
            'cpu_percent': psutil.Process().cpu_percent()
        }
    
    async def shutdown(self):
        """Gracefully shutdown the worker"""
        logger.info("Shutting down worker")
        
        self.is_running = False
        
        # Wait for current jobs to complete
        while self.current_jobs:
            logger.info(f"Waiting for {len(self.current_jobs)} jobs to complete")
            await asyncio.sleep(1)
        
        # Close browser
        if self.context:
            await self.context.close()
        
        if self.browser:
            await self.browser.close()
        
        # Close database connection
        if self.client:
            self.client.close()
        
        # Log final statistics
        stats = await self.get_worker_stats()
        logger.info("Worker shutdown completed", stats=stats)

# ==================== MAIN ENTRY POINT ====================

async def main():
    """Main entry point for the worker"""
    worker = ScrapingWorker()
    
    try:
        # Initialize worker
        await worker.initialize()
        
        # Start processing jobs
        await worker.start()
        
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error("Fatal error in worker", error=str(e))
        raise
    finally:
        await worker.shutdown()

if __name__ == "__main__":
    # Set up signal handlers for graceful shutdown
    import signal
    
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        # The main loop will handle the shutdown
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_
