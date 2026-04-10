FROM nginx:alpine
COPY index.html /usr/share/nginx/html/index.html
COPY manifest.json /usr/share/nginx/html/manifest.json
COPY data/ /usr/share/nginx/html/data/
EXPOSE 80
