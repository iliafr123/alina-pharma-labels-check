FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# VITE_API_URL must be present at build time (Vite inlines it into the bundle)
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
# nginx:alpine entrypoint runs envsubst on templates → substitutes ${PORT} at boot
COPY nginx.railway.conf.template /etc/nginx/templates/default.conf.template
ENV PORT=8080
EXPOSE 8080
