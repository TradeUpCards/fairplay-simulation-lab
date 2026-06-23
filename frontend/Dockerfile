# syntax=docker/dockerfile:1

FROM node:22-alpine AS build

WORKDIR /app
ARG VITE_API_BASE=http://localhost:8000
ENV VITE_API_BASE=$VITE_API_BASE

# Install frontend dependencies first for better Docker layer caching.
COPY frontend/package*.json ./frontend/
RUN npm ci --prefix frontend

# The Vite config imports frozen Contract-2 JSON from the repo-level data/ dir.
COPY data ./data
COPY frontend ./frontend

WORKDIR /app/frontend
RUN npm run build

FROM nginx:1.27-alpine AS runtime

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
