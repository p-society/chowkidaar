from logging import getLogger
from logging_loki import LokiHandler


HANDLER = LokiHandler(
    url="https://my-loki-instance/loki/api/v1/push", 
    tags={"application": "my-app"},
    auth=("username", "password"),
    version="1",
)

logger = getLogger("my-logger")
logger.addHandler(HANDLER)
logger.error(
    "Something happened", 
    extra={"tags": {"service": "my-service"}},
)

