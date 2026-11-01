import logging

from redis import Redis
from rq import Queue, Worker

from app.config import get_settings
from app.db import init_db
from app.jobs import QUEUE_NAME

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    connection = Redis.from_url(settings.redis_url)
    Worker([Queue(QUEUE_NAME, connection=connection)], connection=connection).work(with_scheduler=False)


if __name__ == "__main__":
    main()
