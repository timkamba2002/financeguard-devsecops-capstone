FROM nginx:alpine

# Copy static files
COPY index.html /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/nginx.conf

# Optional: copy any other assets (css, images, etc.) if you add them later
# COPY assets/ /usr/share/nginx/html/assets/

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]