"""آزمایش کوتاه اتصال مونگو، بدون نمایش خطای خام یا تغییر داده."""

from pymongo import MongoClient
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError, ConfigurationError
from rasam.databases import connectivity


def test_connection(uri, database):
    if not uri.startswith(("mongodb://", "mongodb+srv://")) or not database:
        return connectivity.report("invalid")
    # SRV را خود درایور با DNS مخصوص آن حل می‌کند.
    failure = None if uri.startswith("mongodb+srv://") else connectivity.preflight(uri, 27017)
    if failure:
        return failure
    try:
        with MongoClient(uri, serverSelectionTimeoutMS=3000, connectTimeoutMS=3000) as client:
            client.admin.command("ping")
            names = client.list_database_names()
            if database not in names:
                return connectivity.report("database")
            client[database].list_collection_names()
        return connectivity.report("connected")
    except OperationFailure as error:
        return connectivity.report("credentials" if error.code in (18, 8000) else "database")
    except ServerSelectionTimeoutError:
        return connectivity.report("timeout")
    except (ConfigurationError, ValueError):
        return connectivity.report("invalid")
    except Exception:
        return connectivity.report("connection")
