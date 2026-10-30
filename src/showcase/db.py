from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def create_pool(database_url: str) -> ConnectionPool:
    return ConnectionPool(
        database_url,
        min_size=0,
        max_size=8,
        max_waiting=32,
        timeout=3,
        open=False,
        kwargs={
            "row_factory": dict_row,
            "connect_timeout": 3,
            "options": "-c statement_timeout=5000 -c lock_timeout=5000",
        },
    )
