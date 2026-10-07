from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import DateTime, Integer, String, Text, create_engine, select, func, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase): pass


class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(200), default="guest", index=True)
    dilemma: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(40))
    response_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    feedback: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback_comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(200), default="guest", index=True)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class UserSettings(Base):
    __tablename__ = "user_settings"
    user_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    country: Mapped[str] = mapped_column(String(2), default="")
    city: Mapped[str] = mapped_column(String(120), default="")
    emergency_contact: Mapped[str] = mapped_column(String(80), default="")
    location_enabled: Mapped[int] = mapped_column(Integer, default=0)
    theme: Mapped[str] = mapped_column(String(20), default="System")


def make_db(path: str | Path = "council.db"):
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    # create_all does not add columns to an existing SQLite table; keep local
    # upgrades safe when a user already has a pre-user-scoping database.
    with engine.begin() as connection:
        for table in ("decisions", "journal_entries"):
            columns = {column["name"] for column in inspect(connection).get_columns(table)}
            if "user_id" not in columns:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN user_id VARCHAR(200) NOT NULL DEFAULT 'guest'"))
                connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table}_user_id ON {table} (user_id)"))
        decision_columns = {column["name"] for column in inspect(connection).get_columns("decisions")}
        if "feedback_comment" not in decision_columns:
            connection.execute(text("ALTER TABLE decisions ADD COLUMN feedback_comment TEXT"))
        settings_columns = {column["name"] for column in inspect(connection).get_columns("user_settings")}
        if "name" not in settings_columns:
            connection.execute(text("ALTER TABLE user_settings ADD COLUMN name VARCHAR(120) NOT NULL DEFAULT ''"))
    return engine


def save_decision(engine, dilemma: str, category: str, response_json: str, user_id: str = "guest") -> int:
    with Session(engine) as session:
        item = Decision(user_id=user_id, dilemma=dilemma, category=category, response_json=response_json)
        session.add(item); session.commit(); session.refresh(item)
        return item.id


def list_decisions(engine, limit: int = 50, user_id: str = "guest"):
    with Session(engine) as session:
        return list(session.scalars(select(Decision).where(Decision.user_id == user_id).order_by(Decision.created_at.desc()).limit(limit)))


def delete_all(engine, user_id: str = "guest") -> None:
    with Session(engine) as session:
        session.query(Decision).filter(Decision.user_id == user_id).delete(); session.query(JournalEntry).filter(JournalEntry.user_id == user_id).delete(); session.commit()


def add_journal_entry(engine, text: str, user_id: str = "guest") -> int:
    with Session(engine) as session:
        item = JournalEntry(user_id=user_id, text=text); session.add(item); session.commit(); session.refresh(item)
        return item.id


def list_journal_entries(engine, limit: int = 30, user_id: str = "guest"):
    with Session(engine) as session:
        return list(session.scalars(select(JournalEntry).where(JournalEntry.user_id == user_id).order_by(JournalEntry.created_at.desc()).limit(limit)))


def set_feedback(engine, decision_id: int, rating: int, comment: str = "") -> None:
    if rating not in (0, 1): raise ValueError("rating must be 0 or 1")
    with Session(engine) as session:
        item = session.get(Decision, decision_id)
        if item: item.feedback = rating; item.feedback_comment = comment[:2000] or None; session.commit()


def requests_today(engine, user_id: str = "guest") -> int:
    """Return today's request count; the app can use this as a cost-control cap."""
    from datetime import datetime, timezone
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    with Session(engine) as session:
        return int(session.scalar(select(func.count(Decision.id)).where(Decision.user_id == user_id, Decision.created_at >= start)) or 0)


def decision_metrics(engine, user_id: str = "guest") -> dict[str, int | float]:
    with Session(engine) as session:
        items = list(session.scalars(select(Decision).where(Decision.user_id == user_id)))
    ratings = [i.feedback for i in items if i.feedback is not None]
    return {"decisions": len(items), "helpful": sum(ratings), "rated": len(ratings)}


def get_settings(engine, user_id: str = "guest") -> UserSettings:
    with Session(engine) as session:
        item = session.get(UserSettings, user_id)
        return item or UserSettings(user_id=user_id)


def save_settings(engine, user_id: str, **values) -> None:
    allowed = {"name", "country", "city", "emergency_contact", "location_enabled", "theme"}
    with Session(engine) as session:
        item = session.get(UserSettings, user_id) or UserSettings(user_id=user_id)
        for key, value in values.items():
            if key in allowed: setattr(item, key, value)
        session.add(item); session.commit()
