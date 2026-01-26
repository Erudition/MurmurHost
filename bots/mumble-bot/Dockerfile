FROM node:10-stretch

WORKDIR /mumble-bot

# Install all dependencies used for puppeteer and for running the bot.
# Added GPG bypass for archived repositories.
RUN sed -i 's/deb.debian.org/archive.debian.org/g' /etc/apt/sources.list && \
  sed -i 's|security.debian.org/debian-security|archive.debian.org/debian-security|g' /etc/apt/sources.list && \
  sed -i '/stretch-updates/d' /etc/apt/sources.list && \
  apt-get -o Acquire::Check-Valid-Until=false -qq update && \
  apt-get -qq install -y --allow-unauthenticated \
  gconf-service libasound2 libgconf-2-4 libgtk-3-0 libnspr4 libx11-xcb1 \
  libxss1 libxtst6 fonts-ipafont-gothic fonts-wqy-zenhei fonts-thai-tlwg fonts-kacst ttf-freefont \
  fonts-liberation libappindicator1 libnss3 lsb-release xdg-utils libpango1.0-dev libgif-dev \
  build-essential ffmpeg sox postgresql-client

COPY . .

# Delete lockfile to force dependency update (fix for bit-rotted native modules)
RUN rm yarn.lock

# Force TypeScript resolution to local version and fix broken types
RUN sed -i 's/"resolutions": {/"resolutions": {\n        "typescript": "4.0.3",\n        "@types\/express-serve-static-core": "4.17.13",\n        "@types\/bluebird": "3.5.36",\n        "@types\/babel__traverse": "7.14.2",\n        "@types\/minimatch": "3.0.5",/g' package.json

# Build the sources
RUN yarn install --ignore-engines --ignore-scripts && \
  yarn add typescript@4.0.3 --dev --ignore-engines --ignore-scripts && \
  yarn build:server && \
  yarn build:web && \
  yarn install --production --ignore-engines

# Generate certificate and key if they don't exist
RUN [ -f bot.key ] || (openssl genrsa -out bot.key 2048 2> /dev/null && \
  openssl req -new -sha256 -key bot.key -out bot.csr -subj "/" && \
  openssl x509 -req -in bot.csr -signkey bot.key -out bot.cert 2> /dev/null)

# Use a wait loop for the database in the entrypoint
CMD ["/bin/sh", "-c", "sleep 5 && node server migrate --config-file config.yml && node server serve --config-file config.yml"]
