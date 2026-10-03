FROM node:22-alpine AS builder

WORKDIR /frontend

COPY package*.json ./
RUN npm ci --ignore-scripts --registry=https://registry.npmjs.org/

COPY . .

ARG VITE_API_BASE_URL=http://localhost:8000/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /frontend/dist /usr/share/nginx/html

EXPOSE 5174

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --spider --quiet http://127.0.0.1:5174/ || exit 1