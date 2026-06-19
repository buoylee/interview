"""Demo: SERIALIZABLE serialization failure (lost-update prevention).

Two transactions both read balance=100, then both try to write 90. Under
SERIALIZABLE, Postgres detects the read-write dependency and aborts the
second commit with SQLSTATE 40001 (could_not_serialize_access). The fix in
real code is a retry loop.

Run: uv run python seed.py && uv run python demos/isolation.py
"""
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import DBAPIError  # noqa: E402

from db import make_engine  # noqa: E402

engine = make_engine(isolation_level="SERIALIZABLE")
c1, c2 = engine.connect(), engine.connect()
t1, t2 = c1.begin(), c2.begin()

b1 = c1.execute(text("SELECT balance FROM accounts WHERE id=1")).scalar()
b2 = c2.execute(text("SELECT balance FROM accounts WHERE id=1")).scalar()
print(f"both read balance={b1}")

c1.execute(text("UPDATE accounts SET balance=:b WHERE id=1"), {"b": b1 - 10})
t1.commit()
print("tx1 committed -> balance=90")

try:
    c2.execute(text("UPDATE accounts SET balance=:b WHERE id=1"), {"b": b2 - 10})
    t2.commit()
    print("tx2 committed (unexpected)")
except DBAPIError as e:
    t2.rollback()
    code = getattr(e.orig, "sqlstate", getattr(e.orig, "pgcode", "?"))
    print(f"tx2 serialization failure: {type(e.orig).__name__} / sqlstate={code}")
finally:
    c1.close()
    c2.close()
