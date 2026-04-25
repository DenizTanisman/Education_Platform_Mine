# IAU app — production image (Next.js 15 standalone)
#
# Build context: repository root. Compose passes `context: .` and
# `dockerfile: app/Dockerfile`, so paths below are relative to repo root.

ARG NODE_VERSION=20-slim

FROM node:${NODE_VERSION} AS deps
WORKDIR /build
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends openssl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY app/package.json app/package-lock.json ./
RUN npm ci

FROM node:${NODE_VERSION} AS builder
WORKDIR /build
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends openssl \
 && rm -rf /var/lib/apt/lists/*
COPY --from=deps /build/node_modules ./node_modules
COPY app/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npx prisma generate
# Page-data collection during `next build` instantiates lib/auth, which
# needs JWT_SECRET >= 32 chars. Stub values; real secrets come from .env
# at run time.
RUN JWT_SECRET=$(printf 'x%.0s' $(seq 1 64)) \
    DATABASE_URL=postgresql://stub:stub@localhost:5432/stub \
    npm run build

FROM node:${NODE_VERSION} AS runner
WORKDIR /app
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends openssl \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 1001 nodejs \
 && useradd  --system --uid 1001 --gid nodejs --shell /usr/sbin/nologin nextjs
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
COPY --from=builder --chown=nextjs:nodejs /build/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /build/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /build/public ./public
COPY --from=builder --chown=nextjs:nodejs /build/prisma ./prisma
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
