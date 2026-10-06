import duckdb
import os
from pathlib import Path


DB_PATH = (
    Path(__file__)
    .resolve()
    .parent
    .parent
    .parent
    / "database"
    / "dblp.duckdb"
)


def get_connection():

    return duckdb.connect(
        os.environ.get('DBLP_DB_PATH', str(DB_PATH)),
        read_only=True
    )
