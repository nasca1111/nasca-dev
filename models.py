from extensions import db
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))


class Visitor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(50))
    page = db.Column(db.String(100))
    user_agent = db.Column(db.String(200))
    visited_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(JST)
    )

    def __repr__(self):
        return f"<Visitor {self.ip}>"


class FlashcardDeck(db.Model):
    __tablename__ = "flashcard_decks"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    source_filename = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(JST), nullable=False)
    cards = db.relationship("Flashcard", backref="deck", cascade="all, delete-orphan", lazy=True)


class Flashcard(db.Model):
    __tablename__ = "flashcards"

    id = db.Column(db.Integer, primary_key=True)
    deck_id = db.Column(db.Integer, db.ForeignKey("flashcard_decks.id"), nullable=False, index=True)
    front = db.Column(db.Text, nullable=False)
    back = db.Column(db.Text, nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(JST)
    )

    def __repr__(self):
        return f"<Post {self.title}>"


class LearningCategory(db.Model):
    __tablename__ = "learning_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(JST)
    )
    entries = db.relationship(
        "LearningEntry",
        backref="category",
        cascade="all, delete-orphan",
        lazy=True
    )


class LearningEntry(db.Model):
    __tablename__ = "learning_entries"

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(
        db.Integer,
        db.ForeignKey("learning_categories.id"),
        nullable=False
    )
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(JST)
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(JST),
        onupdate=lambda: datetime.now(JST)
    )


class LoginAttempt(db.Model):
    __tablename__ = "login_attempts"

    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(50), nullable=False, index=True)
    user_agent = db.Column(db.String(300))
    success = db.Column(db.Boolean, nullable=False, default=False)
    attempted_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(JST),
        nullable=False,
        index=True
    )


class BlockedIP(db.Model):
    __tablename__ = "blocked_ips"

    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(50), nullable=False, unique=True, index=True)
    reason = db.Column(db.String(200), nullable=False)
    blocked_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(JST),
        nullable=False
    )
