# syntax=docker/dockerfile:1
# React frontend: built with Node, served by nginx (which also proxies the API).
# Build context: the repository root (see docker-compose.yml); only the files allowed by
# docker/frontend.Dockerfile.dockerignore are sent to the build.

# ---- Build stage ----
FROM node:24-alpine AS build
WORKDIR /build

# Install exactly what the lockfile says (cached until package*.json change).
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/index.html frontend/vite.config.js ./
COPY frontend/public ./public
COPY frontend/src ./src
RUN npm run build

# ---- Runtime stage: only the static build, no Node and no node_modules ----
# The official unprivileged nginx image runs as a non-root user and listens on 8080.
FROM nginxinc/nginx-unprivileged:1.29-alpine

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /build/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/nginx-health"]
