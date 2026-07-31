FROM nginx:1.27-alpine

RUN apk add --no-cache openssl

RUN mkdir -p /etc/nginx/certs && \
    openssl req -x509 -nodes -newkey rsa:2048 -days 3650 \
      -subj "/CN=localhost" \
      -keyout /etc/nginx/certs/tls.key \
      -out /etc/nginx/certs/tls.crt

COPY default.conf /etc/nginx/conf.d/default.conf

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
