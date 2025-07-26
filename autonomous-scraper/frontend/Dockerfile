# Multi-stage Docker build for React frontend
# Stage 1: Build the React application
FROM node:18-alpine AS build

# Set working directory inside container
WORKDIR /app

# Copy package.json first for better Docker layer caching
# This allows npm install to be cached if dependencies haven't changed
COPY package.json ./

# Install all dependencies
# --no-cache reduces image size by not storing npm cache
RUN npm install

# Copy all source code to container
COPY . .

# Install Tailwind CSS globally for building styles
RUN npm install -g tailwindcss

# Build Tailwind CSS from source to output
# This creates the compiled CSS file with all utility classes
RUN tailwindcss build -i ./src/index.css -o ./public/tailwind.css

# Build the React application for production
# This creates optimized, minified files in the build/ directory
RUN npm run build

# Stage 2: Serve the built application
FROM node:18-alpine

# Set working directory for serving
WORKDIR /app

# Copy the built application from the previous stage
# This includes all static files, HTML, CSS, and JavaScript
COPY --from=build /app/build /app/build

# Install 'serve' package globally to serve static files
# This is a lightweight static file server perfect for React apps
RUN npm install -g serve

# Expose port 3000 for the web server
EXPOSE 3000

# Start the static file server
# -s flag serves Single Page Application (handles client-side routing)
# -l flag specifies the port to listen on
CMD ["serve", "-s", "build", "-l", "3000"]
