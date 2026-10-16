"""آزمایش اتصال MySQL با کد خطا، بدون فرستادن متن حساس درایور."""

import pymysql
from rasam.databases import connectivity
from rasam.databases.mysql import connection


def test_connection(uri, database):
    if not database:
        return connectivity.report("invalid")
    try:
        connection.parse_uri(uri, database)
        failure = connectivity.preflight(uri, 3306)
        if failure:
            return failure
        with connection.connect(uri, database, timeout_s=3, read_timeout=3, write_timeout=3):
            pass
        return connectivity.report("connected")
    except pymysql.MySQLError as error:
        code = error.args[0] if error.args else None
        category = {1045: "credentials", 1044: "database", 1049: "database",
                    2003: "port", 2013: "timeout"}.get(code, "connection")
        return connectivity.report(category)
    except ValueError:
        return connectivity.report("invalid")
    except Exception:
        return connectivity.report("connection")
