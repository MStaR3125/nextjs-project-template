/**
 * Autonomous Web Scraping System - Frontend Dashboard
 * 
 * This React application provides a modern, user-friendly interface for:
 * - Submitting web scraping jobs
 * - Monitoring job progress and status
 * - Viewing scraped data and results
 * - Managing the scraping queue
 * 
 * Features:
 * - Real-time job status updates
 * - Responsive design with Tailwind CSS
 * - Error handling and user feedback
 * - Clean, modern UI without external icons
 */

import React, { useState, useEffect, useCallback } from 'react';

// Main App Component
const App = () => {
  // ==================== STATE MANAGEMENT ====================
  
  // Jobs data and loading states
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [jobsLoading, setJobsLoading] = useState(true);
  
  // Form state for new job submission
  const [urlInput, setUrlInput] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  // UI state for messages and notifications
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState(''); // 'success', 'error', 'info'
  
  // Pagination and filtering
  const [currentPage, setCurrentPage] = useState(1);
  const [jobsPerPage] = useState(10);
  const [statusFilter, setStatusFilter] = useState('all');
  
  // Auto-refresh toggle
  const [autoRefresh, setAutoRefresh] = useState(true);

  // ==================== API CONFIGURATION ====================
  
  // Backend API base URL - can be configured via environment variables
  const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  // ==================== UTILITY FUNCTIONS ====================
  
  /**
   * Display a message to the user with automatic dismissal
   * @param {string} msg - Message to display
   * @param {string} type - Message type ('success', 'error', 'info')
   */
  const showMessage = useCallback((msg, type = 'info') => {
    setMessage(msg);
    setMessageType(type);
    
    // Auto-dismiss message after 5 seconds
    setTimeout(() => {
      setMessage('');
      setMessageType('');
    }, 5000);
  }, []);

  /**
   * Format date string for display
   * @param {string} dateString - ISO date string
   * @returns {string} Formatted date and time
   */
  const formatDate = (dateString) => {
    try {
      return new Date(dateString).toLocaleString();
    } catch (error) {
      return 'Invalid Date';
    }
  };

  /**
   * Get status badge styling based on job status
   * @param {string} status - Job status
   * @returns {string} Tailwind CSS classes
   */
  const getStatusBadge = (status) => {
    const baseClasses = 'px-3 py-1 rounded-full text-sm font-medium';
    
    switch (status?.toLowerCase()) {
      case 'pending':
        return `${baseClasses} bg-yellow-900 text-yellow-200 border border-yellow-700`;
      case 'in progress':
      case 'processing':
        return `${baseClasses} bg-blue-900 text-blue-200 border border-blue-700`;
      case 'completed':
        return `${baseClasses} bg-green-900 text-green-200 border border-green-700`;
      case 'failed':
        return `${baseClasses} bg-red-900 text-red-200 border border-red-700`;
      default:
        return `${baseClasses} bg-gray-900 text-gray-200 border border-gray-700`;
    }
  };

  // ==================== API FUNCTIONS ====================
  
  /**
   * Fetch all jobs from the backend API
   * Includes error handling and loading states
   */
  const fetchJobs = useCallback(async () => {
    try {
      setJobsLoading(true);
      
      const response = await fetch(`${API_BASE_URL}/jobs`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      
      // Sort jobs by creation date (newest first)
      const sortedJobs = data.sort((a, b) => 
        new Date(b.createdAt) - new Date(a.createdAt)
      );
      
      setJobs(sortedJobs);
      
      // Show success message only on manual refresh
      if (!autoRefresh) {
        showMessage(`Loaded ${sortedJobs.length} jobs successfully`, 'success');
      }
      
    } catch (error) {
      console.error('Error fetching jobs:', error);
      showMessage(`Failed to load jobs: ${error.message}`, 'error');
    } finally {
      setJobsLoading(false);
    }
  }, [API_BASE_URL, autoRefresh, showMessage]);

  /**
   * Submit a new scraping job to the backend
   * @param {Event} e - Form submission event
   */
  const handleSubmitJob = async (e) => {
    e.preventDefault();
    
    // Validate URL input
    if (!urlInput.trim()) {
      showMessage('Please enter a valid URL', 'error');
      return;
    }

    // Basic URL validation
    try {
      new URL(urlInput);
    } catch (error) {
      showMessage('Please enter a valid URL format (e.g., https://example.com)', 'error');
      return;
    }

    setIsSubmitting(true);
    
    try {
      const response = await fetch(`${API_BASE_URL}/scrape`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          url: urlInput.trim() 
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
      }

      const newJob = await response.json();
      
      // Add new job to the beginning of the jobs list
      setJobs(prevJobs => [newJob, ...prevJobs]);
      
      // Clear form and show success message
      setUrlInput('');
      showMessage(`Scraping job submitted successfully! Job ID: ${newJob._id}`, 'success');
      
    } catch (error) {
      console.error('Error submitting job:', error);
      showMessage(`Failed to submit job: ${error.message}`, 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  /**
   * Delete a specific job
   * @param {string} jobId - ID of the job to delete
   */
  const handleDeleteJob = async (jobId) => {
    if (!window.confirm('Are you sure you want to delete this job?')) {
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      // Remove job from local state
      setJobs(prevJobs => prevJobs.filter(job => job._id !== jobId));
      showMessage('Job deleted successfully', 'success');
      
    } catch (error) {
      console.error('Error deleting job:', error);
      showMessage(`Failed to delete job: ${error.message}`, 'error');
    }
  };

  // ==================== EFFECTS ====================
  
  /**
   * Initial data loading on component mount
   */
  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  /**
   * Auto-refresh jobs every 10 seconds when enabled
   */
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      fetchJobs();
    }, 10000); // Refresh every 10 seconds

    return () => clearInterval(interval);
  }, [autoRefresh, fetchJobs]);

  // ==================== FILTERING AND PAGINATION ====================
  
  /**
   * Filter jobs based on selected status
   */
  const filteredJobs = jobs.filter(job => {
    if (statusFilter === 'all') return true;
    return job.status?.toLowerCase() === statusFilter.toLowerCase();
  });

  /**
   * Calculate pagination
   */
  const indexOfLastJob = currentPage * jobsPerPage;
  const indexOfFirstJob = indexOfLastJob - jobsPerPage;
  const currentJobs = filteredJobs.slice(indexOfFirstJob, indexOfLastJob);
  const totalPages = Math.ceil(filteredJobs.length / jobsPerPage);

  /**
   * Handle page change
   */
  const handlePageChange = (pageNumber) => {
    setCurrentPage(pageNumber);
  };

  // ==================== RENDER COMPONENT ====================
  
  return (
    <div className="min-h-screen bg-gray-900 text-white font-sans">
      {/* Header Section */}
      <header className="bg-gray-800 border-b border-gray-700 px-6 py-4">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-3xl font-bold text-white">
            Autonomous Web Scraping Dashboard
          </h1>
          <p className="text-gray-400 mt-2">
            Submit URLs for scraping and monitor job progress in real-time
          </p>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-8">
        
        {/* Status Message Banner */}
        {message && (
          <div className={`mb-6 p-4 rounded-lg border ${
            messageType === 'success' 
              ? 'bg-green-900 border-green-700 text-green-200' 
              : messageType === 'error'
              ? 'bg-red-900 border-red-700 text-red-200'
              : 'bg-blue-900 border-blue-700 text-blue-200'
          }`}>
            <div className="flex justify-between items-center">
              <span>{message}</span>
              <button 
                onClick={() => setMessage('')}
                className="text-xl font-bold hover:opacity-70"
              >
                ×
              </button>
            </div>
          </div>
        )}

        {/* Job Submission Form */}
        <section className="bg-gray-800 rounded-lg border border-gray-700 p-6 mb-8">
          <h2 className="text-xl font-semibold mb-4">Submit New Scraping Job</h2>
          
          <form onSubmit={handleSubmitJob} className="space-y-4">
            <div>
              <label htmlFor="url" className="block text-sm font-medium text-gray-300 mb-2">
                Target URL
              </label>
              <input
                type="url"
                id="url"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="https://example.com"
                required
                disabled={isSubmitting}
              />
            </div>
            
            <button
              type="submit"
              disabled={isSubmitting || !urlInput.trim()}
              className="w-full sm:w-auto px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors duration-200"
            >
              {isSubmitting ? 'Submitting Job...' : 'Submit Scraping Job'}
            </button>
          </form>
        </section>

        {/* Controls Section */}
        <section className="bg-gray-800 rounded-lg border border-gray-700 p-6 mb-8">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            
            {/* Status Filter */}
            <div className="flex items-center gap-4">
              <label htmlFor="statusFilter" className="text-sm font-medium text-gray-300">
                Filter by Status:
              </label>
              <select
                id="statusFilter"
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setCurrentPage(1); // Reset to first page when filtering
                }}
                className="px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">All Status</option>
                <option value="pending">Pending</option>
                <option value="in progress">In Progress</option>
                <option value="completed">Completed</option>
                <option value="failed">Failed</option>
              </select>
            </div>

            {/* Controls */}
            <div className="flex items-center gap-4">
              {/* Auto-refresh Toggle */}
              <label className="flex items-center gap-2 text-sm text-gray-300">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  className="rounded"
                />
                Auto-refresh (10s)
              </label>

              {/* Manual Refresh Button */}
              <button
                onClick={() => fetchJobs()}
                disabled={jobsLoading}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-600 text-white rounded transition-colors duration-200"
              >
                {jobsLoading ? 'Refreshing...' : 'Refresh Jobs'}
              </button>
            </div>
          </div>
        </section>

        {/* Jobs List Section */}
        <section className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-700">
            <h2 className="text-xl font-semibold">
              Scraping Jobs 
              <span className="text-gray-400 text-base ml-2">
                ({filteredJobs.length} total)
              </span>
            </h2>
          </div>

          {/* Loading State */}
          {jobsLoading ? (
            <div className="p-8 text-center">
              <div className="text-gray-400">Loading jobs...</div>
            </div>
          ) : filteredJobs.length === 0 ? (
            /* Empty State */
            <div className="p-8 text-center">
              <div className="text-gray-400 mb-2">
                {statusFilter === 'all' 
                  ? 'No scraping jobs found' 
                  : `No jobs with status "${statusFilter}" found`
                }
              </div>
              <div className="text-sm text-gray-500">
                Submit a new job above to get started
              </div>
            </div>
          ) : (
            /* Jobs Table */
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-700">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                      Job ID
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                      URL
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                      Created
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                      Result
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {currentJobs.map((job) => (
                    <tr key={job._id} className="hover:bg-gray-750">
                      {/* Job ID */}
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-mono text-gray-300">
                          {job._id?.substring(0, 8)}...
                        </div>
                      </td>
                      
                      {/* URL */}
                      <td className="px-6 py-4">
                        <div className="text-sm text-blue-400 max-w-xs truncate">
                          <a 
                            href={job.url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="hover:underline"
                          >
                            {job.url}
                          </a>
                        </div>
                      </td>
                      
                      {/* Status */}
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={getStatusBadge(job.status)}>
                          {job.status || 'Unknown'}
                        </span>
                      </td>
                      
                      {/* Created Date */}
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-400">
                          {formatDate(job.createdAt)}
                        </div>
                      </td>
                      
                      {/* Result */}
                      <td className="px-6 py-4">
                        <div className="text-sm text-gray-300 max-w-xs">
                          {job.status === 'completed' && job.result ? (
                            <div>
                              <div className="font-medium">Title:</div>
                              <div className="text-gray-400 truncate">
                                {job.result.title || 'No title found'}
                              </div>
                            </div>
                          ) : job.status === 'failed' && job.error ? (
                            <div className="text-red-400 truncate">
                              Error: {job.error}
                            </div>
                          ) : (
                            <span className="text-gray-500">-</span>
                          )}
                        </div>
                      </td>
                      
                      {/* Actions */}
                      <td className="px-6 py-4 whitespace-nowrap">
                        <button
                          onClick={() => handleDeleteJob(job._id)}
                          className="text-red-400 hover:text-red-300 text-sm font-medium"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="px-6 py-4 border-t border-gray-700 flex justify-between items-center">
              <div className="text-sm text-gray-400">
                Showing {indexOfFirstJob + 1} to {Math.min(indexOfLastJob, filteredJobs.length)} of {filteredJobs.length} jobs
              </div>
              
              <div className="flex gap-2">
                <button
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={currentPage === 1}
                  className="px-3 py-1 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded text-sm"
                >
                  Previous
                </button>
                
                {[...Array(totalPages)].map((_, index) => (
                  <button
                    key={index + 1}
                    onClick={() => handlePageChange(index + 1)}
                    className={`px-3 py-1 rounded text-sm ${
                      currentPage === index + 1
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-700 hover:bg-gray-600 text-white'
                    }`}
                  >
                    {index + 1}
                  </button>
                ))}
                
                <button
                  onClick={() => handlePageChange(currentPage + 1)}
                  disabled={currentPage === totalPages}
                  className="px-3 py-1 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded text-sm"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </section>

        {/* Footer */}
        <footer className="mt-8 text-center text-gray-500 text-sm">
          <p>Autonomous Web Scraping System - Built with React, FastAPI, and MongoDB</p>
        </footer>
      </div>
    </div>
  );
};

export default App;
