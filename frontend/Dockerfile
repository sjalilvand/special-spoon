# Rosepsy Web — دو اپ: سایت عمومی (/) و پنل (/panel) — بند ۱۳ سند
FROM node:22.12.0-alpine AS build
WORKDIR /build

# --- پنل ---
COPY frontend/package.json frontend/package-lock.json* ./panel/
RUN cd panel && npm install --no-audit --no-fund
COPY frontend/ ./panel/
RUN cd panel && npm run build -- --base=/panel/

# --- سایت عمومی ---
COPY site/package.json ./site/
RUN cd site && npm install --no-audit --no-fund
COPY site/ ./site/
RUN cd site && npm run build

FROM nginx:1.27.3-alpine
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /build/site/dist /usr/share/nginx/html
COPY --from=build /build/panel/dist /usr/share/nginx/panel
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
