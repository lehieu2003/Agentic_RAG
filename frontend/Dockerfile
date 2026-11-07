# Build stage: compile the SPA. Node 24 matches the CI/development line
# (jsdom 30's undici 8 does not load under older Node).
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Serve stage: static files with SPA fallback and /api reverse proxy.
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
