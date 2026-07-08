# ID8 Cloud Intelligence — static Docusaurus behind a Google sign-in gate, on Cloud Run
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM node:20-alpine AS serve
WORKDIR /app
COPY server/package.json ./
RUN npm install --omit=dev
COPY server/ .
COPY --from=build /app/build ./build
COPY --from=build /app/.docusaurus/routesChunkNames.json ./routesChunkNames.json
ENV PORT=8080
EXPOSE 8080
# Cloud Run injects $PORT; server/index.js gates everything except /investors.
CMD ["node", "index.js"]
