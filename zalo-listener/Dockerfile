# ---- Build stage ----
FROM node:20-alpine AS builder

WORKDIR /app

# Copy only package files first (leverages Docker layer cache).
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev

# ---- Runtime stage ----
FROM node:20-alpine

# Security: run as non-root user.
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

# Copy node_modules from builder and application source.
COPY --from=builder /app/node_modules ./node_modules
COPY package.json ./
COPY src/ ./src/

# Switch to non-root user.
USER appuser

# Node runs in the container; no shell needed.
CMD ["node", "src/index.js"]
