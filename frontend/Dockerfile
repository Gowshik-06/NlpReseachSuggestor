# Stage 1: Build static assets
FROM node:20-slim AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci || npm install

COPY . .

# Build production bundle with relative API routes
ENV VITE_API_BASE_URL=""
RUN npm run build

# Stage 2: Production Nginx web server
FROM nginx:alpine

# Copy built static assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy Nginx template for dynamic DNS resolution
COPY nginx.conf /etc/nginx/templates/default.conf.template

ENV NGINX_ENTRYPOINT_LOCAL_RESOLVERS=true

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
