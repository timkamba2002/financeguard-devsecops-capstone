FROM nginx:alpine

# Copy the HTML as a template; the entrypoint substitutes ${BACKEND_API_URL}
# at container startup so each environment gets its own backend URL without
# rebuilding the image.
COPY index.html /usr/share/nginx/html/index.html.template
COPY nginx.conf /etc/nginx/nginx.conf

# Default — overridden by the Helm chart's env.BACKEND_API_URL per environment.
ENV BACKEND_API_URL="http://localhost:8000"

EXPOSE 80

# envsubst replaces ${BACKEND_API_URL} in the template before nginx starts.
# Listing the variable explicitly prevents envsubst from clobbering any other
# ${...} patterns that appear in the HTML (e.g. JS template literals).
CMD ["/bin/sh", "-c", \
     "envsubst '${BACKEND_API_URL}' \
       < /usr/share/nginx/html/index.html.template \
       > /usr/share/nginx/html/index.html \
     && nginx -g 'daemon off;'"]
