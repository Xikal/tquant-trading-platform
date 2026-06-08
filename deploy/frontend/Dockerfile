FROM node:22-alpine AS legacy-build
WORKDIR /workspace/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM node:22-alpine AS next-build
WORKDIR /workspace/frontend-next
COPY frontend-next/package*.json ./
RUN npm ci
COPY frontend-next/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY deploy/frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=legacy-build /workspace/frontend/dist/ /usr/share/nginx/html-root/
COPY --from=next-build /workspace/frontend-next/dist/ /usr/share/nginx/html-next/
