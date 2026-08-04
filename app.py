import hmac
import os
import secrets
from functools import wraps
from ipaddress import ip_address

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash
from extensions import db

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key-before-production")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

ADMIN_PASSWORD_HASH = "scrypt:32768:8:1$AZoWWcB3tzxYAVCu$63fafb5009397187f33e0a33d85a7e1a21cb48f39e15d1f0382379035468963c89c0ea1cf31d68b496083fa6c51424b2ff0f13a81d91530b654cb3b49bf6453d"

db.init_app(app)

from models import Visitor, Post


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

    visitor = Visitor(
        ip = request.remote_addr,
        page = request.path,
        user_agent = request.headers.get("User-Agent")
    )

    db.session.add(visitor)
    db.session.commit()

    posts = Post.query.order_by(Post.created_at.desc()).all()
    recent_visitors = (
        Visitor.query
        .filter(Visitor.ip.notlike("%:%"))
        .order_by(Visitor.visited_at.desc())
        .limit(50)
        .all()
    )

    return render_template(
        "index.html",
        posts=posts,
        recent_visitors=recent_visitors,
        mask_ip=mask_ip,
    )

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

from datetime import datetime


@app.route("/admin/visitors")
@admin_required
def visitor_logs():

    visitors = Visitor.query.order_by(
        Visitor.visited_at.desc()
    ).all()

    total_visitors = Visitor.query.count()

    today = datetime.now().date()

    today_visitors = Visitor.query.filter(
        db.func.date(Visitor.visited_at) == today
    ).count()


    return render_template(
        "visitors.html",
        visitors=visitors,
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

    app.run(debug=True)
