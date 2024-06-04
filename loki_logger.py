from logging import getLogger
from logging_loki import LokiHandler


HANDLER = LokiHandler(
    url="http://127.0.0.1:3100/loki/api/v1/push", 
    tags={"application": "chowkidaar"},
    version="1",
)

logger = getLogger("my-logger")
logger.addHandler(HANDLER)
# docker run -d --name=loki -p 3100:3100 grafana/loki
