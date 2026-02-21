# Build Stage
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package.json ./
RUN npm install --legacy-peer-deps

# Copy source and build (inject production constants dynamically)
COPY . .
RUN npm run build

# Production Stage (Nginx)
FROM nginx:alpine

# Copy compiled Vite bundle to Nginx html directory
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose standard web port
EXPOSE 80

# Run nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
