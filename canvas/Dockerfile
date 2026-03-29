# Build Stage
FROM node:20-alpine AS builder

RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

# Install dependencies (lock file ensures reproducible builds)
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Copy source and Docker-specific env (Nginx 리버스 프록시용 상대 경로)
COPY . .
COPY .env.docker .env.production.local

# Vite 빌드 시 .env.production.local이 최우선 적용되어
# VITE_*_URL이 /proxy/core 등 상대 경로로 번들에 포함된다.
# 이렇게 하면 브라우저가 Nginx를 거쳐 백엔드에 접근하므로
# CORS 문제와 경로 불일치 문제가 모두 해결된다.
RUN npx vite build

# Production Stage (Nginx)
FROM nginx:alpine

# Copy compiled Vite bundle to Nginx html directory
COPY --from=builder /app/dist /usr/share/nginx/html

# SPA fallback + API 리버스 프록시 설정
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose standard web port
EXPOSE 80

# 컨테이너가 정상인지 30초마다 확인한다 (Nginx가 응답하는지 체크)
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:80/ || exit 1

# Run nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
