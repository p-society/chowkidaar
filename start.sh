docker-compose -f prometheus-container.yml up -d 
docker run -d -p 3000:3000 --name=grafana grafana/grafana-oss -d 
docker run -d --name=loki -p 3100:3100 grafana/loki
