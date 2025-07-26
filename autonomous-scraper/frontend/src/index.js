/**
 * React Application Entry Point
 * 
 * This file is the main entry point for the React application.
 * It renders the App component into the DOM and sets up the React environment.
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css'; // Import Tailwind CSS and custom styles
import App from './App';

/**
 * Create the root React element and render the application
 * This uses React 18's new createRoot API for better performance
 */
const root = ReactDOM.createRoot(document.getElementById('root'));

root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

/**
 * Performance monitoring (optional)
 * Uncomment the lines below to enable web vitals reporting
 * This helps monitor the performance of your application
 */

// import reportWebVitals from './reportWebVitals';
// reportWebVitals(console.log);
