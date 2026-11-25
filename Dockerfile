# Imagen de la app SOS (Express + Svelte) para el pipeline DevSecOps de PAI-4.
# Fijada por digest (no por la etiqueta, que se puede mover). Etiqueta: node:20-slim
# (Node 20.20.2). Para actualizarla: docker buildx imagetools inspect node:20-slim
FROM node:20-slim@sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0

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
