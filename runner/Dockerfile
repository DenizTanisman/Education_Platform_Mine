# IAU runner — production image
#
# Build context: repository root. Compose passes `context: .` and
# `dockerfile: runner/Dockerfile`. We need ../app/prisma/schema.prisma at
# build time to generate the prisma client.

FROM node:22-slim AS builder
WORKDIR /runner
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends openssl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY runner/package.json runner/package-lock.json ./
RUN npm ci
COPY runner/ ./
# Stage the schema *inside* the runner workspace so prisma generate finds
# its CLI (in /runner/node_modules) and the generator's relative output
# `../../runner/node_modules/.prisma/client` resolves correctly:
# /runner/staging/prisma/ -> ../../runner/node_modules = /runner/node_modules.
COPY app/prisma ./staging/prisma
RUN npx prisma generate --schema ./staging/prisma/schema.prisma \
 && rm -rf ./staging

FROM node:22-slim AS runtime
WORKDIR /runner
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends openssl ca-certificates docker.io \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 1001 nodejs \
 && useradd  --system --uid 1001 --gid nodejs --shell /usr/sbin/nologin runner
COPY --from=builder --chown=nodejs:nodejs /runner /runner
ENV NODE_ENV=production
USER runner
EXPOSE 4000
CMD ["node", "--experimental-strip-types", "--no-warnings=ExperimentalWarning", "src/server.ts"]
