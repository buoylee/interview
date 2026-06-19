"""Reset the schema and load a reproducible dataset.

20 authors x 5 books = 100 books, plus accounts(id=1, balance=100).
Run after `docker compose up -d`, and again to reset state between demos.
"""
from sqlalchemy.orm import Session

from db import make_engine
from models import Account, Author, Base, Book


def main():
    engine = make_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        for a in range(1, 21):
            author = Author(name=f"Author {a}")
            s.add(author)
            s.flush()  # assign author.id before inserting its books
            for b in range(1, 6):
                s.add(Book(author_id=author.id, title=f"Book {a}-{b}",
                           published_year=2000 + b))
        s.add(Account(id=1, balance=100))
        s.commit()
    print("seeded: 20 authors, 100 books, 1 account")


if __name__ == "__main__":
    main()
