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