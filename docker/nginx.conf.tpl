user nginx;

events {
  worker_connections   1000;
}

http {
  server {
    server_name localhost;
    listen ${API_PROXY_PORT};
    # static files
    include /etc/nginx/mime.types;
    location /static/ {
        alias /static/;
    }
    location /${FLOWER_URL_PREFIX} {
      proxy_pass http://${FLOWER_HOST}:${FLOWER_PORT};
      proxy_request_buffering off;
      client_max_body_size 1024m;
      # Use the Docker embedded DNS server:
      resolver 127.0.0.11;
    }
    location / {
      proxy_pass http://${API_SERVER_HOST}:${API_SERVER_PORT}/;
      # Set `proxy_set_header Host` so that the OIDC callback will look like 
      # http://localhost:${API_PROXY_PORT} in the case of local development
      proxy_set_header Host ${DOLLAR}host:${API_PROXY_PORT} ; 
      proxy_request_buffering off;
      client_max_body_size 4096m;
    }
  }
}
