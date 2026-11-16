"""Create databases + the low-privilege app user on MySQL and MSSQL. Idempotent."""
import time

import pymssql
import pymysql

from .common import *  # noqa


def wait(fn, tries=90):
    for i in range(tries):
        try:
            return fn()
        except Exception:  # noqa
            if i == tries - 1:
                raise
            time.sleep(2)


def mysql():
    c = wait(lambda: pymysql.connect(host=MYSQL_HOST, port=MYSQL_PORT, user="root",
                                     password=MYSQL_ROOT_PW, autocommit=True))
    cur = c.cursor()
    cur.execute(f"CREATE USER IF NOT EXISTS '{APP_USER}'@'%' IDENTIFIED WITH mysql_native_password BY '{APP_PW}'")
    for db in MYSQL_DBS:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db}` CHARACTER SET utf8mb4")
        cur.execute(f"GRANT SELECT,INSERT,UPDATE,DELETE ON `{db}`.* TO '{APP_USER}'@'%'")
    cur.execute("FLUSH PRIVILEGES")
    c.close()
    print("mysql ready")


def mssql():
    c = wait(lambda: pymssql.connect(server=MSSQL_HOST, port=MSSQL_PORT, user="sa",
                                     password=MSSQL_SA_PW, database="master",
                                     autocommit=True, login_timeout=5))
    cur = c.cursor()
    cur.execute(f"IF SUSER_ID('{APP_USER}') IS NULL CREATE LOGIN {APP_USER} WITH PASSWORD='{APP_PW}', CHECK_POLICY=OFF")
    for db in MSSQL_DBS:
        cur.execute(f"IF DB_ID('{db}') IS NULL CREATE DATABASE [{db}]")
    c.close()
    for db in MSSQL_DBS:
        c = pymssql.connect(server=MSSQL_HOST, port=MSSQL_PORT, user="sa", password=MSSQL_SA_PW,
                            database=db, autocommit=True, login_timeout=10)
        cur = c.cursor()
        cur.execute(f"IF USER_ID('{APP_USER}') IS NULL CREATE USER {APP_USER} FOR LOGIN {APP_USER}")
        cur.execute(f"ALTER ROLE db_datareader ADD MEMBER {APP_USER}")
        cur.execute(f"ALTER ROLE db_datawriter ADD MEMBER {APP_USER}")
        c.close()
    print("mssql ready")


if __name__ == "__main__":
    mysql()
    mssql()
