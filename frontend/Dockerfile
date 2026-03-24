FROM node:20-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY package*.json .
RUN npm install

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]
