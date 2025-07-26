#!/usr/bin/env python3
"""
Autonomous Web Scraping System - Integration Test Suite

This script tests the entire system to ensure all components are working correctly.
It performs end-to-end testing of the API, database, and worker functionality.

Usage:
    python test_system.py

Requirements:
    - System must be running (use ./start.sh start)
    - Python 3.7+ with requests library
"""

import sys
import time
import json
import requests
from datetime import datetime
from typing import Dict, List, Optional

# Test configuration
API_BASE_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"
TEST_TIMEOUT = 60  # seconds
POLL_INTERVAL = 2  # seconds

class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

class TestResult:
    """Test result container"""
    def __init__(self, name: str, passed: bool, message: str = "", duration: float = 0.0):
        self.name = name
        self.passed = passed
        self.message = message
        self.duration = duration

class SystemTester:
    """Main test runner for the scraping system"""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.start_time = time.time()
    
    def print_header(self, text: str):
        """Print a formatted header"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{text.center(60)}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")
    
    def print_test(self, name: str):
        """Print test name"""
        print(f"{Colors.CYAN}Testing: {name}...{Colors.END}", end=" ")
    
    def print_result(self, result: TestResult):
        """Print test result"""
        if result.passed:
            print(f"{Colors.GREEN}✓ PASS{Colors.END} ({result.duration:.2f}s)")
            if result.message:
                print(f"  {Colors.WHITE}{result.message}{Colors.END}")
        else:
            print(f"{Colors.RED}✗ FAIL{Colors.END} ({result.duration:.2f}s)")
            if result.message:
                print(f"  {Colors.RED}{result.message}{Colors.END}")
    
    def run_test(self, name: str, test_func):
        """Run a single test and record results"""
        self.print_test(name)
        start_time = time.time()
        
        try:
            result = test_func()
            if isinstance(result, bool):
                result = TestResult(name, result, "", time.time() - start_time)
            elif isinstance(result, tuple):
                passed, message = result
                result = TestResult(name, passed, message, time.time() - start_time)
            else:
                result.duration = time.time() - start_time
        except Exception as e:
            result = TestResult(name, False, f"Exception: {str(e)}", time.time() - start_time)
        
        self.results.append(result)
        self.print_result(result)
        return result.passed
    
    def test_api_health(self) -> TestResult:
        """Test API health endpoint"""
        try:
            response = requests.get(f"{API_BASE_URL}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    return TestResult("API Health", True, f"Database: {data.get('database', 'unknown')}")
                else:
                    return TestResult("API Health", False, f"Unhealthy status: {data.get('status')}")
            else:
                return TestResult("API Health", False, f"HTTP {response.status_code}")
        except requests.exceptions.RequestException as e:
            return TestResult("API Health", False, f"Connection error: {str(e)}")
    
    def test_frontend_accessibility(self) -> TestResult:
        """Test frontend accessibility"""
        try:
            response = requests.get(FRONTEND_URL, timeout=10)
            if response.status_code == 200:
                if "Autonomous" in response.text:
                    return TestResult("Frontend Access", True, "Frontend is serving content")
                else:
                    return TestResult("Frontend Access", False, "Frontend content not found")
            else:
                return TestResult("Frontend Access", False, f"HTTP {response.status_code}")
        except requests.exceptions.RequestException as e:
            return TestResult("Frontend Access", False, f"Connection error: {str(e)}")
    
    def test_api_endpoints(self) -> TestResult:
        """Test basic API endpoints"""
        endpoints = [
            ("/", "GET"),
            ("/jobs", "GET"),
            ("/stats", "GET")
        ]
        
        failed_endpoints = []
        
        for endpoint, method in endpoints:
            try:
                response = requests.request(method, f"{API_BASE_URL}{endpoint}", timeout=10)
                if response.status_code not in [200, 201]:
                    failed_endpoints.append(f"{method} {endpoint}: HTTP {response.status_code}")
            except Exception as e:
                failed_endpoints.append(f"{method} {endpoint}: {str(e)}")
        
        if failed_endpoints:
            return TestResult("API Endpoints", False, "; ".join(failed_endpoints))
        else:
            return TestResult("API Endpoints", True, f"All {len(endpoints)} endpoints working")
    
    def test_job_creation(self) -> TestResult:
        """Test job creation via API"""
        test_url = "https://httpbin.org/html"  # Simple test page
        
        try:
            payload = {"url": test_url}
            response = requests.post(
                f"{API_BASE_URL}/scrape",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 201:
                job_data = response.json()
                job_id = job_data.get("id")
                if job_id:
                    return TestResult("Job Creation", True, f"Job created with ID: {job_id[:8]}...")
                else:
                    return TestResult("Job Creation", False, "No job ID returned")
            else:
                return TestResult("Job Creation", False, f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            return TestResult("Job Creation", False, f"Error: {str(e)}")
    
    def test_job_processing(self) -> TestResult:
        """Test end-to-end job processing"""
        test_url = "https://httpbin.org/html"
        
        try:
            # Create job
            payload = {"url": test_url}
            response = requests.post(f"{API_BASE_URL}/scrape", json=payload, timeout=10)
            
            if response.status_code != 201:
                return TestResult("Job Processing", False, f"Failed to create job: HTTP {response.status_code}")
            
            job_data = response.json()
            job_id = job_data.get("id")
            
            if not job_id:
                return TestResult("Job Processing", False, "No job ID returned")
            
            # Poll for completion
            start_time = time.time()
            while time.time() - start_time < TEST_TIMEOUT:
                response = requests.get(f"{API_BASE_URL}/jobs/{job_id}", timeout=10)
                
                if response.status_code == 200:
                    job_status = response.json()
                    status = job_status.get("status")
                    
                    if status == "completed":
                        result_data = job_status.get("result", {})
                        if result_data and "content" in result_data:
                            return TestResult("Job Processing", True, 
                                           f"Job completed successfully in {time.time() - start_time:.1f}s")
                        else:
                            return TestResult("Job Processing", False, "Job completed but no content found")
                    
                    elif status == "failed":
                        error = job_status.get("error", "Unknown error")
                        return TestResult("Job Processing", False, f"Job failed: {error}")
                    
                    # Still processing, wait and try again
                    time.sleep(POLL_INTERVAL)
                else:
                    return TestResult("Job Processing", False, f"Error checking job status: HTTP {response.status_code}")
            
            return TestResult("Job Processing", False, f"Job did not complete within {TEST_TIMEOUT}s timeout")
            
        except Exception as e:
            return TestResult("Job Processing", False, f"Error: {str(e)}")
    
    def test_database_operations(self) -> TestResult:
        """Test database operations through API"""
        try:
            # Get initial job count
            response = requests.get(f"{API_BASE_URL}/jobs", timeout=10)
            if response.status_code != 200:
                return TestResult("Database Operations", False, f"Failed to fetch jobs: HTTP {response.status_code}")
            
            initial_jobs = response.json()
            initial_count = len(initial_jobs)
            
            # Create a test job
            test_url = "https://httpbin.org/json"
            payload = {"url": test_url}
            response = requests.post(f"{API_BASE_URL}/scrape", json=payload, timeout=10)
            
            if response.status_code != 201:
                return TestResult("Database Operations", False, f"Failed to create job: HTTP {response.status_code}")
            
            # Check if job count increased
            response = requests.get(f"{API_BASE_URL}/jobs", timeout=10)
            if response.status_code != 200:
                return TestResult("Database Operations", False, "Failed to fetch jobs after creation")
            
            new_jobs = response.json()
            new_count = len(new_jobs)
            
            if new_count > initial_count:
                return TestResult("Database Operations", True, 
                               f"Job count increased from {initial_count} to {new_count}")
            else:
                return TestResult("Database Operations", False, 
                               f"Job count did not increase (was {initial_count}, now {new_count})")
                
        except Exception as e:
            return TestResult("Database Operations", False, f"Error: {str(e)}")
    
    def test_worker_functionality(self) -> TestResult:
        """Test worker by creating job and waiting for processing"""
        test_url = "https://httpbin.org/user-agent"
        
        try:
            # Create job
            payload = {"url": test_url}
            response = requests.post(f"{API_BASE_URL}/scrape", json=payload, timeout=10)
            
            if response.status_code != 201:
                return TestResult("Worker Functionality", False, f"Failed to create job: HTTP {response.status_code}")
            
            job_data = response.json()
            job_id = job_data.get("id")
            
            # Wait for worker to pick up and process the job
            start_time = time.time()
            status_changes = []
            
            while time.time() - start_time < TEST_TIMEOUT:
                response = requests.get(f"{API_BASE_URL}/jobs/{job_id}", timeout=10)
                
                if response.status_code == 200:
                    job_status = response.json()
                    current_status = job_status.get("status")
                    
                    if current_status not in [s[0] for s in status_changes]:
                        status_changes.append((current_status, time.time() - start_time))
                    
                    if current_status in ["completed", "failed"]:
                        break
                    
                    time.sleep(POLL_INTERVAL)
                else:
                    return TestResult("Worker Functionality", False, f"Error checking job: HTTP {response.status_code}")
            
            if len(status_changes) >= 2:  # Should go from pending -> in_progress -> completed/failed
                status_summary = " -> ".join([f"{s[0]}({s[1]:.1f}s)" for s in status_changes])
                return TestResult("Worker Functionality", True, f"Worker processed job: {status_summary}")
            else:
                return TestResult("Worker Functionality", False, f"Worker did not process job properly: {status_changes}")
                
        except Exception as e:
            return TestResult("Worker Functionality", False, f"Error: {str(e)}")
    
    def test_error_handling(self) -> TestResult:
        """Test system error handling"""
        test_cases = [
            ("Invalid URL", {"url": "not-a-valid-url"}),
            ("Missing URL", {}),
            ("Unreachable URL", {"url": "https://this-domain-should-not-exist-12345.com"})
        ]
        
        results = []
        
        for test_name, payload in test_cases:
            try:
                response = requests.post(f"{API_BASE_URL}/scrape", json=payload, timeout=10)
                
                if test_name == "Invalid URL" and response.status_code == 422:
                    results.append(f"✓ {test_name}: Properly rejected")
                elif test_name == "Missing URL" and response.status_code == 422:
                    results.append(f"✓ {test_name}: Properly rejected")
                elif test_name == "Unreachable URL" and response.status_code == 201:
                    # This should create a job that fails during processing
                    job_data = response.json()
                    job_id = job_data.get("id")
                    
                    # Wait a bit for processing
                    time.sleep(5)
                    
                    status_response = requests.get(f"{API_BASE_URL}/jobs/{job_id}", timeout=10)
                    if status_response.status_code == 200:
                        job_status = status_response.json()
                        if job_status.get("status") == "failed":
                            results.append(f"✓ {test_name}: Job properly failed")
                        else:
                            results.append(f"✗ {test_name}: Job should have failed")
                    else:
                        results.append(f"✗ {test_name}: Could not check job status")
                else:
                    results.append(f"✗ {test_name}: Unexpected response {response.status_code}")
                    
            except Exception as e:
                results.append(f"✗ {test_name}: Exception {str(e)}")
        
        failed_tests = [r for r in results if r.startswith("✗")]
        
        if failed_tests:
            return TestResult("Error Handling", False, "; ".join(failed_tests))
        else:
            return TestResult("Error Handling", True, f"All {len(test_cases)} error cases handled correctly")
    
    def test_performance(self) -> TestResult:
        """Test basic performance metrics"""
        try:
            # Test API response time
            start_time = time.time()
            response = requests.get(f"{API_BASE_URL}/health", timeout=10)
            api_response_time = time.time() - start_time
            
            if response.status_code != 200:
                return TestResult("Performance", False, "Health endpoint not responding")
            
            # Test job creation time
            start_time = time.time()
            payload = {"url": "https://httpbin.org/html"}
            response = requests.post(f"{API_BASE_URL}/scrape", json=payload, timeout=10)
            job_creation_time = time.time() - start_time
            
            if response.status_code != 201:
                return TestResult("Performance", False, "Job creation failed")
            
            metrics = [
                f"API response: {api_response_time:.3f}s",
                f"Job creation: {job_creation_time:.3f}s"
            ]
            
            # Check if performance is acceptable
            if api_response_time > 2.0:
                return TestResult("Performance", False, f"API too slow: {api_response_time:.3f}s")
            
            if job_creation_time > 5.0:
                return TestResult("Performance", False, f"Job creation too slow: {job_creation_time:.3f}s")
            
            return TestResult("Performance", True, "; ".join(metrics))
            
        except Exception as e:
            return TestResult("Performance", False, f"Error: {str(e)}")
    
    def run_all_tests(self):
        """Run all system tests"""
        self.print_header("AUTONOMOUS WEB SCRAPING SYSTEM - TEST SUITE")
        
        print(f"{Colors.WHITE}Starting comprehensive system tests...{Colors.END}")
        print(f"{Colors.WHITE}API Base URL: {API_BASE_URL}{Colors.END}")
        print(f"{Colors.WHITE}Frontend URL: {FRONTEND_URL}{Colors.END}")
        print(f"{Colors.WHITE}Test Timeout: {TEST_TIMEOUT}s{Colors.END}")
        
        # Define test suite
        tests = [
            ("API Health Check", self.test_api_health),
            ("Frontend Accessibility", self.test_frontend_accessibility),
            ("API Endpoints", self.test_api_endpoints),
            ("Database Operations", self.test_database_operations),
            ("Job Creation", self.test_job_creation),
            ("Worker Functionality", self.test_worker_functionality),
            ("Job Processing (E2E)", self.test_job_processing),
            ("Error Handling", self.test_error_handling),
            ("Performance Metrics", self.test_performance)
        ]
        
        # Run tests
        passed_tests = 0
        for test_name, test_func in tests:
            if self.run_test(test_name, test_func):
                passed_tests += 1
        
        # Print summary
        self.print_summary(passed_tests, len(tests))
    
    def print_summary(self, passed: int, total: int):
        """Print test summary"""
        total_time = time.time() - self.start_time
        
        self.print_header("TEST SUMMARY")
        
        if passed == total:
            print(f"{Colors.GREEN}{Colors.BOLD}🎉 ALL TESTS PASSED! 🎉{Colors.END}")
            print(f"{Colors.GREEN}✓ {passed}/{total} tests successful{Colors.END}")
        else:
            print(f"{Colors.RED}{Colors.BOLD}❌ SOME TESTS FAILED ❌{Colors.END}")
            print(f"{Colors.RED}✗ {total - passed}/{total} tests failed{Colors.END}")
            print(f"{Colors.GREEN}✓ {passed}/{total} tests passed{Colors.END}")
        
        print(f"\n{Colors.WHITE}Total execution time: {total_time:.2f}s{Colors.END}")
        
        # Print failed tests details
        failed_tests = [r for r in self.results if not r.passed]
        if failed_tests:
            print(f"\n{Colors.RED}{Colors.BOLD}Failed Tests:{Colors.END}")
            for test in failed_tests:
                print(f"{Colors.RED}  ✗ {test.name}: {test.message}{Colors.END}")
        
        print(f"\n{Colors.BLUE}System Status: {'HEALTHY' if passed == total else 'NEEDS ATTENTION'}{Colors.END}")
        
        return passed == total

def main():
    """Main entry point"""
    print(f"{Colors.BOLD}{Colors.PURPLE}Autonomous Web Scraping System - Test Suite{Colors.END}")
    print(f"{Colors.WHITE}Testing system functionality and performance...{Colors.END}\n")
    
    # Check if system is likely running
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print(f"{Colors.RED}❌ System appears to be down. Please start it with: ./start.sh start{Colors.END}")
            sys.exit(1)
    except requests.exceptions.RequestException:
        print(f"{Colors.RED}❌ Cannot connect to system. Please ensure it's running: ./start.sh start{Colors.END}")
        sys.exit(1)
    
    # Run tests
    tester = SystemTester()
    success = tester.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
