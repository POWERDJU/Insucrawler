from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.migrations import create_views
from app.db.seed_master_data import seed_all


@pytest.fixture()
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", future=True, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    create_views(engine)
    Session = sessionmaker(bind=engine, future=True)
    with Session() as db:
        seed_all(db)
        yield db
    Base.metadata.drop_all(engine)
