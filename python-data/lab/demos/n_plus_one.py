"""Demo: the N+1 query problem and its fix.

Lazy loading (default) fires 1 query for authors + 1 per author's books
=> 1 + 20 = 21 queries. selectinload collapses it to 2. A before_cursor_execute
listener counts the actual SQL statements so you see it, not guess it.

Run: uv run python demos/n_plus_one.py
"""
import pathlib
import sys
import time

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))

from sqlalchemy import event, select  # noqa: E402
from sqlalchemy.orm import Session, selectinload  # noqa: E402

from db import make_engine  # noqa: E402
from models import Author  # noqa: E402

engine = make_engine()
counter = {"n": 0}


@event.listens_for(engine, "before_cursor_execute")
def _count(conn, cursor, statement, params, context, executemany):
    counter["n"] += 1


def run(label, use_eager):
    counter["n"] = 0
    t0 = time.perf_counter()
    with Session(engine) as s:
        stmt = select(Author)
        if use_eager:
            stmt = stmt.options(selectinload(Author.books))
        authors = s.scalars(stmt).all()
        total = sum(len(a.books) for a in authors)  # triggers lazy loads
    dt = (time.perf_counter() - t0) * 1000
    print(f"{label}: {counter['n']} queries, {total} books, {dt:.1f} ms")


run("N+1 (lazy)", use_eager=False)
run("fixed (selectinload)", use_eager=True)
