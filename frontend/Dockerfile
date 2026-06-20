# ============================================================
# TaskingAI Frontend Dockerfile
# Build context: project root (docker build -f frontend/Dockerfile .)
# ============================================================

# Stage 1: Build the application
FROM node:18.18 as build-stage

WORKDIR /app

# ============================================================
# Step 1: Copy shared contracts package first (cached layer)
# ============================================================
COPY contracts/npm /app/contracts/npm

# ============================================================
# Step 2: Copy frontend dependencies (cached layer)
# ============================================================
COPY frontend/package.json /app/package.json
COPY frontend/package-lock.json /app/package-lock.json
COPY frontend/yarn.lock /app/yarn.lock

# Install dependencies
RUN npm install

# ============================================================
# Step 3: Copy frontend source code and build
# ============================================================
COPY frontend /app

# Build the application for production
RUN npm run build

# ============================================================
# Stage 2: Serve with Nginx
# ============================================================
FROM nginx:alpine

# Copy the build artifacts from the previous stage to the Nginx server directory
COPY --from=build-stage /app/dist /usr/share/nginx/html

# Create a custom Nginx configuration file to handle React Router
RUN echo $'server {\n\
    listen       80;\n\
    server_name  localhost;\n\
    location / {\n\
        root   /usr/share/nginx/html;\n\
        index  index.html index.htm;\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
    error_page   500 502 503 504  /50x.html;\n\
    location = /50x.html {\n\
        root   /usr/share/nginx/html;\n\
    }\n\
}' > /etc/nginx/conf.d/default.conf

# Expose port 80 to the Docker host
EXPOSE 80

# Start Nginx when the container is launched and keep it running
CMD ["nginx", "-g", "daemon off;"]
