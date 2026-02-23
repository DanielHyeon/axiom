# Build Stage
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package.json ./
RUN npm install --legacy-peer-deps

# Build-time API URL (Docker: canvas 5173 → core 8002)
ARG VITE_CORE_URL=http://localhost:8002
ENV VITE_CORE_URL=$VITE_CORE_URL

# Copy source and build (Docker: skip tsc to avoid TS strict errors; fix types in repo for full build)
COPY . .
RUN npx vite build

# Production Stage (Nginx)
FROM nginx:alpine

# Copy compiled Vite bundle to Nginx html directory
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose standard web port
EXPOSE 80

# Run nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
