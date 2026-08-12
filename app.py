import hmac
import os
import re
import secrets
from functools import wraps
from html import escape
from html.parser import HTMLParser
from ipaddress import ip_address

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from markupsafe import Markup
from werkzeug.security import check_password_hash
from extensions import db

app = Flask(__name__)
# Database configuration
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key-before-production")
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:////home/ec2-user/data/app.db"
#test
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

ADMIN_PASSWORD_HASH = "scrypt:32768:8:1$AZoWWcB3tzxYAVCu$63fafb5009397187f33e0a33d85a7e1a21cb48f39e15d1f0382379035468963c89c0ea1cf31d68b496083fa6c51424b2ff0f13a81d91530b654cb3b49bf6453d"

db.init_app(app)

from models import Visitor, Post, LearningCategory, LearningEntry


class LearningHtmlSanitizer(HTMLParser):
    """Keep only the small set of formatting tags supported by the editor."""
    allowed_tags = {"b", "strong", "i", "em", "u", "span", "br", "p", "div", "ul", "ol", "li"}

    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.allowed_tags:
            return
        if tag == "span":
            color = dict(attrs).get("style", "")
            if re.fullmatch(r"color:\s*(#[0-9a-fA-F]{3,8}|rgb\([0-9, ]+\))\s*;?", color):
                self.parts.append(f'<span style="{escape(color, quote=True)}">')
                return
        self.parts.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if tag in self.allowed_tags and tag != "br":
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        self.parts.append(escape(data))

    def result(self):
        return "".join(self.parts)


def sanitize_learning_html(value):
    sanitizer = LearningHtmlSanitizer()
    sanitizer.feed(value or "")
    return sanitizer.result()


@app.template_filter("learning_html")
def learning_html(value):
    return Markup(sanitize_learning_html(value))


def is_admin():
    return session.get("is_admin", False)


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def validate_csrf():
    submitted_token = request.form.get("csrf_token", "")
    if not hmac.compare_digest(submitted_token, session.get("csrf_token", "")):
        abort(400, "Invalid CSRF token")


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not is_admin():
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped_view


@app.context_processor
def inject_template_values():
    return {"is_admin": is_admin(), "csrf_token": csrf_token}


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if check_password_hash(ADMIN_PASSWORD_HASH, request.form.get("password", "")):
            session.clear()
            session["is_admin"] = True
            csrf_token()
            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("home"))
        flash("Invalid password.")

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@admin_required
def logout():
    validate_csrf()
    session.clear()
    return redirect(url_for("home"))


def mask_ip(value):
    """Show enough of an address for a visit log without exposing the full IP."""
    try:
        address = ip_address(value)
    except ValueError:
        return "UNKNOWN"

    if address.version != 4:
        return "UNKNOWN"

    return f"{str(address).rsplit('.', 1)[0]}.***"


@app.route("/")
def home():

    visitor_ip = request.headers.get(
        "X-Forwarded-For",
        request.remote_addr
    ).split(",")[0].strip()

    visitor = Visitor(
        ip=visitor_ip,
        page=request.path,
        user_agent=request.headers.get("User-Agent")
    )



    db.session.add(visitor)
    db.session.commit()

    posts = Post.query.order_by(Post.created_at.desc()).all()
    learning_categories = LearningCategory.query.order_by(LearningCategory.name).all()
    recent_visitors = (
        Visitor.query
        .filter(Visitor.ip.notlike("%:%"))
        .order_by(Visitor.visited_at.desc())
        .limit(50)
        .all()
    )

    total_visitors = Visitor.query.count()
    today = datetime.now().date()
    today_visitors = Visitor.query.filter(
    db.func.date(Visitor.visited_at) == today
    ).count()

    return render_template(
        "index.html",
        posts=posts,
        learning_categories=learning_categories,
        today_visitors=today_visitors,
        total_visitors=total_visitors
    )


@app.route("/learning/categories", methods=["POST"])
@admin_required
def create_learning_category():
    validate_csrf()
    name = request.form.get("name", "").strip()
    if not name:
        flash("Category name is required.")
    elif len(name) > 80:
        flash("Category name must be 80 characters or fewer.")
    elif LearningCategory.query.filter_by(name=name).first():
        flash("That category already exists.")
    else:
        db.session.add(LearningCategory(name=name))
        db.session.commit()
    return redirect(url_for("home") + "#learning")


@app.route("/learning/category/<int:category_id>", methods=["GET", "POST"])
def learning_category(category_id):
    category = LearningCategory.query.get_or_404(category_id)

    if request.method == "POST":
        if not is_admin():
            return redirect(url_for("login", next=request.path))
        validate_csrf()
        title = request.form.get("title", "").strip()
        content = sanitize_learning_html(request.form.get("content", ""))
        if not title or not content:
            flash("Title and content are required.")
        else:
            db.session.add(LearningEntry(category=category, title=title, content=content))
            db.session.commit()
            return redirect(url_for("learning_category", category_id=category.id))

    entries = LearningEntry.query.filter_by(category_id=category.id).order_by(
        LearningEntry.created_at.desc()
    ).all()
    return render_template("learning_category.html", category=category, entries=entries)


@app.route("/learning/entry/<int:entry_id>/edit", methods=["POST"])
@admin_required
def edit_learning_entry(entry_id):
    validate_csrf()
    entry = LearningEntry.query.get_or_404(entry_id)
    title = request.form.get("title", "").strip()
    content = sanitize_learning_html(request.form.get("content", ""))
    if title and content:
        entry.title = title
        entry.content = content
        db.session.commit()
    else:
        flash("Title and content are required.")
    return redirect(url_for("learning_category", category_id=entry.category_id))


@app.route("/learning/entry/<int:entry_id>/delete", methods=["POST"])
@admin_required
def delete_learning_entry(entry_id):
    validate_csrf()
    entry = LearningEntry.query.get_or_404(entry_id)
    category_id = entry.category_id
    db.session.delete(entry)
    db.session.commit()
    return redirect(url_for("learning_category", category_id=category_id))


@app.route("/learning/category/<int:category_id>/delete", methods=["POST"])
@admin_required
def delete_learning_category(category_id):
    validate_csrf()
    category = LearningCategory.query.get_or_404(category_id)
    db.session.delete(category)
    db.session.commit()
    return redirect(url_for("home") + "#learning")

@app.route("/test-db")
@admin_required
def test_db():

    visitors = Visitor.query.all()

    result = ""

    for v in visitors:
        result += f"""
        ID: {v.id}<br>
        IP: {v.ip}<br>
        PAGE: {v.page}<br>
        USER_AGENT: {v.user_agent}<br>
        TIME: {v.visited_at}<br>
        <hr>
        """

    return result

from datetime import datetime, time, timedelta


def describe_user_agent(user_agent):
    """Turn a browser's long User-Agent string into an admin-friendly summary."""
    agent = (user_agent or "").lower()
    bot_markers = {
        "googlebot": "Googlebot",
        "bingbot": "Bingbot",
        "yandexbot": "YandexBot",
        "baiduspider": "Baidu Spider",
        "facebookexternalhit": "Facebook Crawler",
        "twitterbot": "Twitterbot",
        "slackbot": "Slackbot",
        "discordbot": "Discordbot",
        "crawler": "Web Crawler",
        "spider": "Web Spider",
        "bot": "Automated Bot",
    }
    bot_name = next((name for marker, name in bot_markers.items() if marker in agent), None)

    if "edg/" in agent:
        browser = "Microsoft Edge"
    elif "opr/" in agent or "opera" in agent:
        browser = "Opera"
    elif "firefox/" in agent:
        browser = "Firefox"
    elif "chrome/" in agent or "crios/" in agent:
        browser = "Chrome"
    elif "safari/" in agent:
        browser = "Safari"
    elif bot_name:
        browser = bot_name
    else:
        browser = "Unknown client"

    if "iphone" in agent:
        device = "iPhone"
    elif "ipad" in agent:
        device = "iPad"
    elif "android" in agent and "mobile" in agent:
        device = "Android phone"
    elif "android" in agent:
        device = "Android tablet"
    elif "windows" in agent:
        device = "Windows"
    elif "mac os" in agent or "macintosh" in agent:
        device = "macOS"
    elif "linux" in agent:
        device = "Linux"
    else:
        device = "Unknown device"

    return {
        "type": "Bot" if bot_name else "Person",
        "name": bot_name or "Likely human visitor",
        "browser": browser,
        "device": device,
        "raw": user_agent or "No User-Agent provided",
    }


@app.route("/admin/visitors")
@admin_required
def visitor_logs():
    selected_date = request.args.get("date", "").strip()
    try:
        selected_day = datetime.strptime(selected_date, "%Y-%m-%d").date() if selected_date else datetime.now().date()
    except ValueError:
        selected_day = datetime.now().date()

    start = datetime.combine(selected_day, time.min)
    end = start + timedelta(days=1)
    visitors = (Visitor.query
        .filter(Visitor.visited_at >= start, Visitor.visited_at < end)
        .order_by(Visitor.visited_at.desc())
        .all())
    visitor_logs = [
        {"visitor": visitor, "client": describe_user_agent(visitor.user_agent)}
        for visitor in visitors
    ]
    available_dates = [
        row[0] for row in db.session.query(db.func.date(Visitor.visited_at))
        .distinct()
        .order_by(db.func.date(Visitor.visited_at).desc())
        .all()
        if row[0]
    ]
    total_visitors = Visitor.query.count()
    today = datetime.now().date()
    today_visitors = Visitor.query.filter(
        Visitor.visited_at >= datetime.combine(today, time.min),
        Visitor.visited_at < datetime.combine(today + timedelta(days=1), time.min)
    ).count()
    bot_visitors = sum(log["client"]["type"] == "Bot" for log in visitor_logs)

    return render_template(
        "visitors.html",
        visitor_logs=visitor_logs,
        selected_date=selected_day.isoformat(),
        available_dates=available_dates,
        selected_total=len(visitor_logs),
        selected_bots=bot_visitors,
        total_visitors=total_visitors,
        today_visitors=today_visitors
    )

@app.route("/write", methods=["GET", "POST"])
@admin_required
def write():

    if request.method == "POST":
        validate_csrf()

        post = Post(
            title=request.form["title"],
            content=request.form["content"]
        )

        db.session.add(post)
        db.session.commit()

        return redirect("/")

    return render_template("write.html")

@app.route("/posts")
def posts():

    posts = Post.query.order_by(
        Post.created_at.desc()
    ).all()

    return render_template(
        "posts.html",
        posts=posts
    )

@app.route("/post/<int:id>")
def post_detail(id):

    post = Post.query.get_or_404(id)

    return render_template(
        "detail.html",
        post=post
    )

@app.route("/post/<int:id>/edit", methods=["GET", "POST"])
@admin_required
def edit_post(id):

    post = Post.query.get_or_404(id)

    if request.method == "POST":
        validate_csrf()

        post.title = request.form["title"]
        post.content = request.form["content"]

        db.session.commit()

        return redirect("/")


    return render_template(
        "edit.html",
        post=post
    )

@app.route("/post/<int:id>/delete", methods=["POST"])
@admin_required
def delete_post(id):

    validate_csrf()

    post = Post.query.get_or_404(id)

    db.session.delete(post)
    db.session.commit()

    return redirect("/")



if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(
            host="0.0.0.0",
            port=5000,
            debug=False
    )
