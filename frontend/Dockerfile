FROM node:22-alpine AS build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json /app/
RUN npm ci

COPY frontend/ /app/

ARG VITE_API_BASE_URL
ARG VITE_APP_BASE_PATH=

ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_APP_BASE_PATH=${VITE_APP_BASE_PATH}

RUN if [ -z "$VITE_API_BASE_URL" ]; then echo "VITE_API_BASE_URL is required"; exit 1; fi
RUN npm run build

FROM nginx:1.28.2-alpine

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
