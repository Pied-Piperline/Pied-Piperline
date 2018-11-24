import os

import rethinkdb as r

RDB_CONFIG = {
    'host': os.environ['RDB_HOST'],
    'port': int(os.environ['RDB_PORT']),
    'db': os.environ['RDB_DB'],
}

def db_connection() -> r.Connection:
    return r.connect(host=RDB_CONFIG['host'], port=RDB_CONFIG['port'], db=RDB_CONFIG['db'])