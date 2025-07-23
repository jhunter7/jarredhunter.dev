# BEFORE: FROM nginx:alpine
FROM nginxinc/nginx-unprivileged:stable-alpine

# Static files
COPY *.html /usr/share/nginx/html/
COPY *.webp /usr/share/nginx/html/

# Port 8080 is already used in this image
EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
