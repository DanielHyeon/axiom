# Build Stage
FROM node:20-alpine AS builder

RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

# Install dependencies (lock file ensures reproducible builds)
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Build-time API URLs (Docker: browser → host ports)
ARG VITE_CORE_URL=http://localhost:19002
ARG VITE_SYNAPSE_URL=http://localhost:19003
ARG VITE_VISION_URL=http://localhost:19100
ARG VITE_WEAVER_URL=http://localhost:19001
ARG VITE_ORACLE_URL=http://localhost:19004
ARG VITE_OLAP_STUDIO_URL=http://localhost:19005
ENV VITE_CORE_URL=$VITE_CORE_URL
ENV VITE_SYNAPSE_URL=$VITE_SYNAPSE_URL
ENV VITE_VISION_URL=$VITE_VISION_URL
ENV VITE_WEAVER_URL=$VITE_WEAVER_URL
ENV VITE_ORACLE_URL=$VITE_ORACLE_URL
ENV VITE_OLAP_STUDIO_URL=$VITE_OLAP_STUDIO_URL

# Copy source and build
COPY . .
RUN npx vite build

# Production Stage (Nginx)
FROM nginx:alpine

# Copy compiled Vite bundle to Nginx html directory
COPY --from=builder /app/dist /usr/share/nginx/html

# SPA fallback: serve index.html for all client-side routes
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose standard web port
EXPOSE 80

# 컨테이너가 정상인지 30초마다 확인한다 (Nginx가 응답하는지 체크)
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:80/ || exit 1

# Run nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
