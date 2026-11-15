# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    npm ci --strict-ssl=true --no-audit --no-fund

# Local development (Docker Compose): source is mounted and reloads on change.
FROM deps AS dev
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]

# Production build. next.config.ts is read at build time, so the backend URL used by
# the /api/v1 rewrite must be known now: --build-arg BACKEND_URL=https://...
FROM deps AS build
ARG BACKEND_URL
ENV BACKEND_URL=$BACKEND_URL \
    NEXT_TELEMETRY_DISABLED=1
COPY . .
RUN if [ -z "$BACKEND_URL" ]; then echo "Set --build-arg BACKEND_URL" >&2; exit 1; fi; \
    npm run build

# Production runtime: the standalone server only, no dev dependencies, non-root.
FROM node:22-bookworm-slim AS prod
WORKDIR /app
ENV NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000 \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
