# Vite 빌드, Docker, CDN 배포

<!-- affects: operations, frontend -->
<!-- requires-update: - -->

## 이 문서가 답하는 질문

- Canvas의 빌드 프로세스는 어떻게 되는가?
- Docker 이미지는 어떻게 구성하는가?
- 스테이징/프로덕션 배포 파이프라인은?
- 환경별 설정 관리 방법은?

> 포트/엔드포인트 기준: [`docs/service-endpoints-ssot.md`](../../../../docs/service-endpoints-ssot.md)

---

## 1. 빌드 프로세스

### 1.1 Vite 빌드 설정

```typescript
// vite.config.ts

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    target: 'es2020',
    outDir: 'dist',
    sourcemap: true,            // 프로덕션 소스맵 (에러 추적)
    rollupOptions: {
      output: {
        manualChunks: {
          // 벤더 청크 분리
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-query': ['@tanstack/react-query'],
          'vendor-ui': ['@radix-ui/react-dialog', '@radix-ui/react-dropdown-menu'],
          'vendor-charts': ['recharts'],
          'vendor-table': ['@tanstack/react-table'],
          'vendor-dnd': ['@dnd-kit/core', '@dnd-kit/sortable'],
          'vendor-graph': ['react-force-graph-2d'],
        },
      },
    },
    chunkSizeWarningLimit: 500,  // 500KB 경고
  },
  server: {
    port: 3000,
    proxy: {
      // 개발 시 API 프록시
      '/api/core':    { target: 'http://localhost:8000', rewrite: (p) => p.replace('/api/core', '/api/v1') }, // Core 별도 실행 시
      '/api/vision':  { target: 'http://localhost:8000', rewrite: (p) => p.replace('/api/vision', '/api/v1') },
      '/api/oracle':  { target: 'http://localhost:8002', rewrite: (p) => p.replace('/api/oracle', '/api/v1') }, // Oracle 별도 실행 시
      '/api/synapse': { target: 'http://localhost:8003', rewrite: (p) => p.replace('/api/synapse', '/api/v1') }, // Synapse 별도 실행 시
      '/api/weaver':  { target: 'http://localhost:8001', rewrite: (p) => p.replace('/api/weaver', '/api/v1') },
    },
  },
});
```

### 1.2 빌드 명령어

```bash
# 개발 서버
npm run dev               # Vite dev server (HMR, port 3000)

# 타입 체크
npm run type-check        # tsc --noEmit

# 린트
npm run lint              # eslint src/ --ext .ts,.tsx

# 테스트
npm run test              # vitest run
npm run test:watch        # vitest (watch mode)

# 빌드
npm run build             # vite build (production)
npm run build:staging     # vite build --mode staging

# 프리뷰
npm run preview           # vite preview (빌드 결과 로컬 확인)
```

### 1.3 빌드 산출물 구조

```
dist/
├── index.html
├── assets/
│   ├── index-[hash].js          # 메인 엔트리 (~50KB gzip)
│   ├── vendor-react-[hash].js   # React 코어 (~45KB gzip)
│   ├── vendor-query-[hash].js   # TanStack Query (~15KB gzip)
│   ├── vendor-ui-[hash].js      # Radix UI (~20KB gzip)
│   ├── vendor-charts-[hash].js  # Recharts (~40KB gzip)
│   ├── vendor-table-[hash].js   # TanStack Table (~10KB gzip)
│   ├── vendor-dnd-[hash].js     # DnD Kit (~12KB gzip)
│   ├── vendor-graph-[hash].js   # Force Graph (~25KB gzip)
│   ├── CaseDashboard-[hash].js  # 라우트 청크
│   ├── DocumentEditor-[hash].js
│   ├── OlapPivot-[hash].js
│   ├── ... (라우트별 청크)
│   ├── index-[hash].css         # Tailwind CSS (~30KB gzip)
│   └── fonts/
│       └── Pretendard-*.woff2   # 한글 폰트
└── robots.txt

목표 번들 크기: 초기 로드 < 200KB (gzip), 전체 < 1MB (gzip)
```

---

## 2. Docker 구성

### 2.1 Dockerfile

```dockerfile
# === 1단계: 빌드 ===
FROM node:20-alpine AS builder

WORKDIR /app

# 의존성 설치 (캐시 최적화)
COPY package.json package-lock.json ./
RUN npm ci --frozen-lockfile

# 소스 복사 및 빌드
COPY . .
ARG VITE_CORE_URL
ARG VITE_VISION_URL
ARG VITE_ORACLE_URL
ARG VITE_SYNAPSE_URL
ARG VITE_WEAVER_URL
ARG VITE_WS_URL
ARG VITE_AUTH_FALLBACK_MOCK
RUN npm run build

# === 2단계: 서빙 ===
FROM nginx:1.25-alpine

# Nginx 설정
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 빌드 산출물 복사
COPY --from=builder /app/dist /usr/share/nginx/html

# 헬스체크
HEALTHCHECK --interval=30s --timeout=3s \
  CMD wget -qO- http://localhost/health || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

운영 원칙:
- 스테이징/프로덕션 빌드에서는 `VITE_AUTH_FALLBACK_MOCK=false`를 강제한다.

### 2.2 Nginx 설정

```nginx
# nginx.conf

server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # 헬스체크
    location /health {
        return 200 'ok';
        add_header Content-Type text/plain;
    }

    # 정적 파일 (해시 포함 -> 장기 캐시)
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # 폰트 (장기 캐시)
    location ~* \.(woff2?|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # SPA fallback (모든 경로 -> index.html)
    location / {
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache";
    }

    # gzip 압축
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml;
    gzip_min_length 1000;

    # 보안 헤더
    add_header X-Frame-Options "SAMEORIGIN";
    add_header X-Content-Type-Options "nosniff";
    add_header X-XSS-Protection "1; mode=block";
    add_header Referrer-Policy "strict-origin-when-cross-origin";
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' wss: https:;";
}
```

---

## 3. 배포 파이프라인

### 3.1 환경 구성

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Development  │────→│   Staging    │────→│  Production  │
│              │     │              │     │              │
│ localhost:3000│     │ staging.axiom│     │ app.axiom.kr │
│ Vite dev     │     │ Docker + K8s │     │ Docker + K8s │
│ 개발자 로컬   │     │ 테스트 검증  │     │ 실서비스     │
└──────────────┘     └──────────────┘     └──────────────┘
```

### 3.2 CI/CD 파이프라인

```
[Git Push / PR]
      │
      ▼
[CI: 타입 체크 + 린트]
      │
      ├── 실패 → PR 차단
      │
      ▼
[CI: 단위 테스트]
      │
      ├── 실패 → PR 차단
      │
      ▼
[CI: 빌드 (staging)]
      │
      ├── 실패 → PR 차단
      │
      ▼
[PR Merge → main]
      │
      ▼
[CD: Docker 이미지 빌드]
      │
      ▼
[CD: Staging 배포]
      │
      ▼
[수동 승인 + E2E 테스트]
      │
      ▼
[CD: Production 배포]
      │
      ▼
[모니터링 + 롤백 대기 (30분)]
```

---

## 4. 환경별 설정

### 4.1 환경 변수 관리

| 변수 | Development | Staging | Production |
|------|-------------|---------|------------|
| `VITE_CORE_URL` | `http://localhost:8000` | `https://api-stg.axiom.kr/core` | `https://api.axiom.kr/core` |
| `VITE_VISION_URL` | `http://localhost:8000` | `https://api-stg.axiom.kr/vision` | `https://api.axiom.kr/vision` |
| `VITE_ORACLE_URL` | `http://localhost:8002` | `https://api-stg.axiom.kr/oracle` | `https://api.axiom.kr/oracle` |
| `VITE_SYNAPSE_URL` | `http://localhost:8003` | `https://api-stg.axiom.kr/synapse` | `https://api.axiom.kr/synapse` |
| `VITE_WEAVER_URL` | `http://localhost:8001` | `https://api-stg.axiom.kr/weaver` | `https://api.axiom.kr/weaver` |
| `VITE_WS_URL` | `ws://localhost:8000/ws` | `wss://api-stg.axiom.kr/ws` | `wss://api.axiom.kr/ws` |

### 4.2 Docker Build Args

```bash
# 스테이징 빌드
docker build \
  --build-arg VITE_CORE_URL=https://api-stg.axiom.kr/core \
  --build-arg VITE_VISION_URL=https://api-stg.axiom.kr/vision \
  --build-arg VITE_ORACLE_URL=https://api-stg.axiom.kr/oracle \
  --build-arg VITE_SYNAPSE_URL=https://api-stg.axiom.kr/synapse \
  --build-arg VITE_WEAVER_URL=https://api-stg.axiom.kr/weaver \
  --build-arg VITE_WS_URL=wss://api-stg.axiom.kr/ws \
  -t axiom-canvas:staging .
```

---

## 5. 모니터링

### 5.1 프론트엔드 모니터링 항목

| 항목 | 도구 | 임계값 |
|------|------|--------|
| 에러율 | Sentry | 1% 이상 경고 |
| LCP (Largest Contentful Paint) | Web Vitals | 2.5초 이상 경고 |
| FID (First Input Delay) | Web Vitals | 100ms 이상 경고 |
| CLS (Cumulative Layout Shift) | Web Vitals | 0.1 이상 경고 |
| 번들 크기 | CI 빌드 시 측정 | 초기 200KB(gzip) 초과 시 경고 |

---

## 결정 사항 (Decisions)

- Nginx 정적 서빙 (Node.js SSR 아님)
  - 근거: Canvas는 SPA, 서버 사이드 렌더링 불필요
  - CDN 캐싱 최적화 가능

- Docker 멀티스테이지 빌드
  - 근거: 최종 이미지에 node_modules 불포함, 이미지 크기 최소화 (~25MB)

---

## 관련 문서

- Core 성능·모니터링 종합 (`services/core/docs/08_operations/performance-monitoring.md`): Canvas Web Vitals SLO, Sentry 프론트엔드 설정, 번들 크기 모니터링, Grafana Canvas Frontend 대시보드

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-19 | 1.0 | Axiom Team | 초기 작성 |
