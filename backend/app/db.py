import os
import pymysql
from pymysql.cursors import DictCursor
from queue import Queue, Empty
from contextlib import contextmanager

# Database configuration
DB_HOST = os.environ.get('MYSQL_HOST', 'localhost')
DB_PORT = int(os.environ.get('MYSQL_PORT', 3306))
DB_USER = os.environ.get('MYSQL_USER', 'root')
DB_PASSWORD = os.environ.get('MYSQL_PASSWORD', os.environ.get('MYSQL_ROOT_PASSWORD', 'X@rV#mTk'))
DB_NAME = os.environ.get('MYSQL_DATABASE', 'daily_drop_db')

class ConnectionPool:
    def __init__(self, max_connections=15):
        self.max_connections = max_connections
        self._pool = Queue(maxsize=max_connections)
        self._created_count = 0

    def _create_connection(self):
        return pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset='utf8mb4',
            cursorclass=DictCursor,
            autocommit=False
        )

    def get_connection(self):
        try:
            conn = self._pool.get_nowait()
            # Verify connection is alive
            conn.ping(reconnect=True)
            return conn
        except Empty:
            return self._create_connection()

    def release_connection(self, conn):
        try:
            if self._pool.qsize() < self.max_connections:
                self._pool.put_nowait(conn)
            else:
                conn.close()
        except Exception:
            try:
                conn.close()
            except Exception:
                pass

pool = ConnectionPool(max_connections=15)

@contextmanager
def get_db():
    conn = pool.get_connection()
    try:
        # Reset any stale REPEATABLE READ snapshot so read queries always see latest commits
        conn.commit()
        yield conn
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.commit()
        except Exception:
            pass
        pool.release_connection(conn)

