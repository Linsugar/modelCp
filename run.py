import logging

import uvicorn

from app.config import get_settings


if __name__ == "__main__":
    settings = get_settings()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        access_log=False,
        log_config=None,
    )
