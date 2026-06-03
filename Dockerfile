# Build blog HTML from Markdown
FROM python:3.12-alpine AS blog-builder
WORKDIR /build
COPY scripts/requirements.txt scripts/build_blog.py ./
COPY blog/posts ./blog/posts/
COPY blog/media ./blog/media/
COPY src ./src
RUN pip install --no-cache-dir -r requirements.txt \
    && python build_blog.py

# Serve static site with Nginx
FROM nginx:alpine
RUN rm -rf /usr/share/nginx/html/*
COPY --from=blog-builder /build/src/ /usr/share/nginx/html/
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
