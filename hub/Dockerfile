# ID8 Cloud Intelligence — static Docusaurus on Cloud Run
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM node:20-alpine AS serve
WORKDIR /app
RUN npm install -g serve@14
COPY --from=build /app/build ./build
ENV PORT=8080
EXPOSE 8080
# Cloud Run injects $PORT; serve the static build on it.
CMD ["sh", "-c", "serve -s build -l ${PORT}"]
