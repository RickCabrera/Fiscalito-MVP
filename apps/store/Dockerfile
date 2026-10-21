# Front de Fiscalito (P6-03). Se construye desde la RAÍZ del repo (el lock de npm es el del
# workspace):  docker build -f apps/store/Dockerfile --build-arg VITE_FISCAL_AGENT_URL=... .
# Las VITE_* se hornean en el bundle: cambiar una exige reconstruir. Guía: docs/despliegue.md.

FROM node:20-alpine AS build
WORKDIR /repo
COPY package.json package-lock.json ./
COPY apps/store/package.json apps/store/
RUN npm ci --workspace apps/store --include-workspace-root=false
COPY apps/store/ apps/store/

ARG VITE_FISCAL_AGENT_URL=http://localhost:8000
ARG VITE_FIREBASE_API_KEY=""
ARG VITE_FIREBASE_AUTH_DOMAIN=""
ARG VITE_FIREBASE_PROJECT_ID=""
ARG VITE_FIREBASE_STORAGE_BUCKET=""
ARG VITE_FIREBASE_MESSAGING_SENDER_ID=""
ARG VITE_FIREBASE_APP_ID=""
ARG VITE_MOSTRAR_DEMO=""
ARG VITE_CUENTAS_DEMO=""
ARG VITE_RESPONSABLE_NOMBRE=""
ARG VITE_RESPONSABLE_DOMICILIO=""
ARG VITE_RESPONSABLE_CORREO=""
ARG VITE_RESPONSABLE_FECHA_AVISO=""
ENV VITE_FISCAL_AGENT_URL=$VITE_FISCAL_AGENT_URL \
    VITE_FIREBASE_API_KEY=$VITE_FIREBASE_API_KEY \
    VITE_FIREBASE_AUTH_DOMAIN=$VITE_FIREBASE_AUTH_DOMAIN \
    VITE_FIREBASE_PROJECT_ID=$VITE_FIREBASE_PROJECT_ID \
    VITE_FIREBASE_STORAGE_BUCKET=$VITE_FIREBASE_STORAGE_BUCKET \
    VITE_FIREBASE_MESSAGING_SENDER_ID=$VITE_FIREBASE_MESSAGING_SENDER_ID \
    VITE_FIREBASE_APP_ID=$VITE_FIREBASE_APP_ID \
    VITE_MOSTRAR_DEMO=$VITE_MOSTRAR_DEMO \
    VITE_CUENTAS_DEMO=$VITE_CUENTAS_DEMO \
    VITE_RESPONSABLE_NOMBRE=$VITE_RESPONSABLE_NOMBRE \
    VITE_RESPONSABLE_DOMICILIO=$VITE_RESPONSABLE_DOMICILIO \
    VITE_RESPONSABLE_CORREO=$VITE_RESPONSABLE_CORREO \
    VITE_RESPONSABLE_FECHA_AVISO=$VITE_RESPONSABLE_FECHA_AVISO
RUN npm run build --workspace apps/store

FROM nginx:1.27-alpine
# La imagen de nginx sustituye ${PORT} en las plantillas al arrancar (Railway inyecta PORT).
ENV PORT=8080
COPY apps/store/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /repo/apps/store/dist /usr/share/nginx/html
EXPOSE 8080
