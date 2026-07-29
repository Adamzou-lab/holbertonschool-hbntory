FROM nginx:alpine

# Pur HTML/CSS/JS, pas de build ni de serveur applicatif nécessaire — nginx
# sert les fichiers tels quels, image minimale (~40 Mo).
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html
COPY static /usr/share/nginx/html/static

EXPOSE 80
