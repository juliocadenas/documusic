# Usar imagen de Node
FROM node:18-alpine

WORKDIR /app

# Copiar archivos de dependencia
COPY package*.json ./

# Instalar dependencias
RUN npm install

# Copiar el resto del código
COPY . .

# Exponer el puerto de Vite
EXPOSE 5173

# Ejecutar en modo desarrollo con host expuesto para Docker
CMD ["npm", "run", "dev", "--", "--host"]
