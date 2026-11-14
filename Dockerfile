# Imagen de la app SOS (Express + Svelte) para el pipeline DevSecOps de PAI-4.
FROM node:20-slim

WORKDIR /app

# Dependencias del backend (se copian primero para aprovechar la cache de capas)
COPY package.json package-lock.json ./
RUN npm ci

# Codigo de la app
COPY . .

# Build del frontend Svelte (npm run build entra en src/front/svelte-app,
# hace npm install y vite build; el resultado queda en src/front/svelte-app/build)
RUN npm run build

# Carpeta de las bases NeDB
RUN mkdir -p data

EXPOSE 8080

CMD ["npm", "start"]
