FROM node:20-alpine AS dependencies
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM dependencies AS builder
ARG BACKEND_BASE_URL=http://backend:8000
ENV BACKEND_BASE_URL=$BACKEND_BASE_URL
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    BACKEND_BASE_URL=http://backend:8000 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
RUN addgroup -S app && adduser -S app -G app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
USER app
HEALTHCHECK --interval=10s --timeout=5s --retries=5 CMD node -e "fetch('http://127.0.0.1:3000/health').then((response) => { if (!response.ok) { process.exit(1); } }).catch(() => process.exit(1));"
EXPOSE 3000
CMD ["node", "server.js"]
