import hmac
import io
import json
import os
import re
import secrets
import sqlite3
import subprocess
import tempfile
import zipfile
from datetime import datetime, time, timedelta
from functools import wraps
from html import escape
from html.parser import HTMLParser
from ipaddress import ip_address

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename
from markupsafe import Markup
from werkzeug.security import check_password_hash
from werkzeug.exceptions import RequestEntityTooLarge
from extensions import db

try:
    import zstandard as zstd
except ImportError:  # The command-line fallback supports existing deployments during upgrade.
    zstd = None

app = Flask(__name__)
# Database configuration
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key-before-production")
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:////home/ec2-user/data/app.db"
#test
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # Allow multiple Anki packages in one upload.
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

ADMIN_PASSWORD_HASH = "scrypt:32768:8:1$AZoWWcB3tzxYAVCu$63fafb5009397187f33e0a33d85a7e1a21cb48f39e15d1f0382379035468963c89c0ea1cf31d68b496083fa6c51424b2ff0f13a81d91530b654cb3b49bf6453d"

db.init_app(app)

from models import Visitor, Post, LearningCategory, LearningEntry, LoginAttempt, BlockedIP, FlashcardDeck, Flashcard, JST


class LearningHtmlSanitizer(HTMLParser):
    """Keep common pasted document formatting while removing active content."""
    allowed_tags = {
        "a", "b", "blockquote", "br", "code", "div", "em", "h1", "h2", "h3",
        "h4", "h5", "h6", "hr", "i", "li", "ol", "p", "pre", "s", "span",
        "strong", "table", "tbody", "td", "th", "thead", "tr", "u", "ul", "img", "audio",
    }
    void_tags = {"br", "hr", "img"}
    blocked_tags = {"script", "style", "iframe", "object", "embed", "svg", "math"}

    def __init__(self):
        super().__init__()
        self.parts = []
        self.blocked_depth = 0

    @staticmethod
    def safe_style(value):
        """Allow only basic visual styles used by pasted ChatGPT content."""
        allowed = []
        for declaration in value.split(";"):
            if ":" not in declaration:
                continue
            property_name, property_value = (part.strip() for part in declaration.split(":", 1))
            if property_name == "color" and re.fullmatch(r"#[0-9a-fA-F]{3,8}|rgb\([0-9, ]+\)", property_value):
                allowed.append(f"color: {property_value}")
            elif property_name == "background-color" and re.fullmatch(r"#[0-9a-fA-F]{3,8}|rgb\([0-9, ]+\)", property_value):
                allowed.append(f"background-color: {property_value}")
            elif property_name == "text-align" and property_value in {"left", "center", "right"}:
                allowed.append(f"text-align: {property_value}")
        return "; ".join(allowed)

    def handle_starttag(self, tag, attrs):
        if tag in self.blocked_tags:
            self.blocked_depth += 1
            return
        if self.blocked_depth:
            return
        if tag not in self.allowed_tags:
            return
        attributes = dict(attrs)
        safe_attributes = []
        style = self.safe_style(attributes.get("style", ""))
        if style:
            safe_attributes.append(f'style="{escape(style, quote=True)}"')
        if tag == "a":
            href = attributes.get("href", "")
            if re.fullmatch(r"(https?://|mailto:|/|#)[^\s]*", href, re.IGNORECASE):
                safe_attributes.append(f'href="{escape(href, quote=True)}"')
                safe_attributes.append('rel="noopener noreferrer"')
                if href.startswith(("http://", "https://")):
                    safe_attributes.append('target="_blank"')
        elif tag in {"img", "audio"}:
            src = attributes.get("src", "")
            if src.startswith("/static/uploads/flashcards/"):
                safe_attributes.append(f'src="{escape(src, quote=True)}"')
                if tag == "img":
                    safe_attributes.append(f'alt="{escape(attributes.get("alt", "Anki card image"), quote=True)}"')
                else:
                    safe_attributes.append("controls")
        suffix = f" {' '.join(safe_attributes)}" if safe_attributes else ""
        self.parts.append(f"<{tag}{suffix}>")

    def handle_endtag(self, tag):
        if tag in self.blocked_tags:
            self.blocked_depth = max(0, self.blocked_depth - 1)
        elif not self.blocked_depth and tag in self.allowed_tags and tag not in self.void_tags:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.blocked_depth:
            self.parts.append(escape(data))

    def result(self):
        return "".join(self.parts)


def sanitize_learning_html(value):
    sanitizer = LearningHtmlSanitizer()
    sanitizer.feed(value or "")
    return sanitizer.result()


def cleanup_expired_visitors():
    """Keep access logs for the last rolling 72 hours only."""
    cutoff = datetime.now(JST).replace(tzinfo=None) - timedelta(days=3)
    return Visitor.query.filter(Visitor.visited_at < cutoff).delete(synchronize_session=False)


def render_anki_template(template, fields, front_side=""):
    """Apply the common Anki field and cloze replacements without executing package code."""
    field_values = {field.get("name", ""): value for field, value in zip(template.get("fields", []), fields)}

    def cloze_value(value, answer):
        target = str(template.get("ordinal", 0) + 1)

        def replace(match):
            number, text, hint = match.groups()
            if answer or number != target:
                return text
            return f"[{hint or '...'}]"

        return re.sub(r"\{\{c(\d+)::(.*?)(?:::(.*?))?\}\}", replace, value, flags=re.DOTALL)

    content = template.get("format", "")
    content = content.replace("{{FrontSide}}", front_side)

    def replace_field(match):
        raw_name = match.group(1).strip()
        filters, _, field_name = raw_name.rpartition(":")
        value = field_values.get(field_name if filters else raw_name, "")
        if "cloze" in filters:
            return cloze_value(value, "answer" in template)
        return value

    content = re.sub(r"\{\{\{?([^{}]+?)\}?\}\}", replace_field, content)
    return content


def save_anki_media(media_files):
    """Save package media under a unique static folder and return source URL mappings."""
    if not media_files:
        return {}
    folder = secrets.token_urlsafe(12)
    target_directory = os.path.join(BASE_DIR, "static", "uploads", "flashcards", folder)
    os.makedirs(target_directory, exist_ok=True)
    urls = {}
    allowed_extensions = {".avif", ".gif", ".jpeg", ".jpg", ".mp3", ".ogg", ".png", ".wav", ".webp"}
    for index, (original_name, data) in enumerate(media_files.items()):
        safe_name = secure_filename(original_name)
        if not safe_name or os.path.splitext(safe_name)[1].lower() not in allowed_extensions:
            continue
        saved_name = f"{index}-{safe_name}"
        with open(os.path.join(target_directory, saved_name), "wb") as media_file:
            media_file.write(data)
        urls[original_name] = f"/static/uploads/flashcards/{folder}/{saved_name}"
    return urls


def replace_anki_media(content, media_urls):
    """Turn Anki image/audio references into URLs that can safely be shown on this site."""
    def replace_src(match):
        prefix, source = match.groups()
        return f"{prefix}{media_urls.get(source, source)}" if source in media_urls else match.group(0)

    content = re.sub(r"((?:src|href)=[\"'])([^\"']+)", replace_src, content, flags=re.IGNORECASE)
    return re.sub(
        r"\[sound:([^\]]+)\]",
        lambda match: f'<audio controls src="{media_urls[match.group(1)]}"></audio>' if match.group(1) in media_urls else "",
        content,
    )


def decode_anki_text(value):
    """Read older Anki exports that contain non-UTF-8 media names or fields."""
    if isinstance(value, str):
        return value
    for encoding in ("utf-8-sig", "utf-8", "cp949", "shift_jis", "cp1252"):
        try:
            return value.decode(encoding)
        except UnicodeDecodeError:
            continue
    return value.decode("utf-8", errors="replace")


def decompress_anki21b(data):
    """Decode the Zstandard-compressed SQLite collection in modern Anki exports."""
    try:
        if zstd:
            unpacked = zstd.ZstdDecompressor().decompress(data, max_output_size=100 * 1024 * 1024)
        else:
            result = subprocess.run(
                ["zstd", "-d", "-q", "-c"], input=data, capture_output=True, check=True, timeout=20
            )
            unpacked = result.stdout
    except (OSError, subprocess.SubprocessError, Exception) as exc:
        raise ValueError("This modern Anki package could not be decompressed.") from exc
    if len(unpacked) > 100 * 1024 * 1024:
        raise ValueError("The Anki collection data must be 100 MB or smaller.")
    return unpacked


def read_anki_package(upload):
    """Read front/back fields from an .apkg without extracting its contents."""
    if not upload or not upload.filename:
        raise ValueError("An Anki .apkg file is required.")
    if not upload.filename.lower().endswith(".apkg"):
        raise ValueError("Only .apkg Anki package files can be uploaded.")

    package_bytes = upload.read()
    if len(package_bytes) > 50 * 1024 * 1024:
        raise ValueError("Each Anki package must be 50 MB or smaller.")
    try:
        with zipfile.ZipFile(io.BytesIO(package_bytes)) as archive:
            database_name = next(
                name for name in archive.namelist()
                if name in {"collection.anki21b", "collection.anki21", "collection.anki2"}
            )
            database_bytes = archive.read(database_name)
            if database_name == "collection.anki21b":
                database_bytes = decompress_anki21b(database_bytes)
            media_files = {}
            try:
                raw_media_index = archive.read("media")
                if raw_media_index.startswith(b"\x28\xb5\x2f\xfd"):
                    raw_media_index = decompress_anki21b(raw_media_index)
                media_index = json.loads(decode_anki_text(raw_media_index)) if raw_media_index else {}
                total_media_size = 0
                for archive_name, original_name in media_index.items():
                    data = archive.read(str(archive_name))
                    total_media_size += len(data)
                    if total_media_size > 80 * 1024 * 1024:
                        raise ValueError("The package media must be 80 MB or smaller.")
                    media_files[decode_anki_text(original_name)] = data
            except KeyError:
                pass
    except (StopIteration, zipfile.BadZipFile, KeyError):
        raise ValueError("This does not appear to be a valid Anki package.")

    with tempfile.NamedTemporaryFile(suffix=".anki", delete=False) as temp_file:
        temp_file.write(database_bytes)
        database_path = temp_file.name
    try:
        connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
        try:
            connection.text_factory = bytes
            deck_names, models = {}, {}
            table_names = {decode_anki_text(row[0]) for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "decks" in table_names:
                deck_names = {
                    deck_id: decode_anki_text(name)
                    for deck_id, name in connection.execute("SELECT id, name FROM decks")
                }
            else:
                row = connection.execute("SELECT decks, models FROM col LIMIT 1").fetchone()
                if row:
                    deck_names = {
                        int(deck_id): decode_anki_text(data.get("name", "Untitled deck"))
                        for deck_id, data in json.loads(decode_anki_text(row[0])).items()
                    }
                    models = json.loads(decode_anki_text(row[1]))
            rows = connection.execute(
                "SELECT c.did, n.flds, n.mid, c.ord, c.due FROM cards c JOIN notes n ON n.id = c.nid ORDER BY c.due, c.id"
            ).fetchall()
        finally:
            connection.close()
    except (sqlite3.Error, json.JSONDecodeError) as exc:
        raise ValueError("The Anki package could not be read.") from exc
    finally:
        os.unlink(database_path)

    cards_by_deck = {}
    for deck_id, fields, model_id, ordinal, due in rows:
        values = decode_anki_text(fields).split("\x1f")
        model = models.get(str(model_id), {})
        templates = model.get("tmpls", [])
        if ordinal < len(templates):
            field_definitions = model.get("flds", [])
            question_template = {"format": templates[ordinal].get("qfmt", ""), "fields": field_definitions, "ordinal": ordinal}
            answer_template = {"format": templates[ordinal].get("afmt", ""), "fields": field_definitions, "ordinal": ordinal, "answer": True}
            front = render_anki_template(question_template, values)
            back = render_anki_template(answer_template, values, front)
        else:
            front, *remaining = values
            back = next((value for value in remaining if value.strip()), front)
        if front.strip() and back.strip():
            cards_by_deck.setdefault(deck_names.get(deck_id, "Untitled deck"), []).append((front, back, due))
    if not cards_by_deck:
        raise ValueError("No cards with both front and back fields were found.")
    if sum(len(cards) for cards in cards_by_deck.values()) > 10000:
        raise ValueError("An Anki package can contain up to 10,000 cards.")
    return cards_by_deck, media_files


@app.errorhandler(RequestEntityTooLarge)
def handle_large_upload(error):
    if request.path == "/flashcards/upload":
        flash("Uploads can be up to 100 MB in total, with each .apkg up to 50 MB.")
        return redirect(url_for("flashcards"))
    return error, 413


@app.template_filter("learning_html")
def learning_html(value):
    return Markup(sanitize_learning_html(value))


def is_admin():
    return session.get("is_admin", False)


def flashcard_deck_name(deck):
    """Use the package filename when an Anki export only supplies its Default deck name."""
    if deck.name in {"Default", "Untitled deck"}:
        return os.path.splitext(deck.source_filename)[0]
    return deck.name


def request_ip():
    """Return the client address supplied by the reverse proxy or direct request."""
    return request.headers.get("X-Forwarded-For", request.remote_addr).split(",")[0].strip()


@app.before_request
def reject_blocked_ip():
    """Block all site requests from an address blocked after failed sign-ins."""
    if request.endpoint == "static":
        return None
    if BlockedIP.query.filter_by(ip=request_ip()).first():
        return render_template("blocked.html"), 403
    if cleanup_expired_visitors():
        db.session.commit()
    return None


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
    return {
        "is_admin": is_admin(),
        "csrf_token": csrf_token,
        "describe_user_agent": describe_user_agent,
        "flashcard_deck_name": flashcard_deck_name,
    }


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        client_ip = request_ip()
        if check_password_hash(ADMIN_PASSWORD_HASH, request.form.get("password", "")):
            db.session.add(LoginAttempt(
                ip=client_ip,
                user_agent=request.headers.get("User-Agent"),
                success=True
            ))
            db.session.commit()
            session.clear()
            session["is_admin"] = True
            csrf_token()
            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("home"))
        db.session.add(LoginAttempt(
            ip=client_ip,
            user_agent=request.headers.get("User-Agent"),
            success=False
        ))
        failed_attempts = LoginAttempt.query.filter_by(ip=client_ip, success=False).count()
        if failed_attempts >= 5:
            db.session.add(BlockedIP(
                ip=client_ip,
                reason="Five failed login attempts"
            ))
        db.session.commit()
        if failed_attempts >= 5:
            return render_template("blocked.html"), 403
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
    visitor_ip = request_ip()
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


@app.route("/flashcards")
def flashcards():
    decks = FlashcardDeck.query.order_by(FlashcardDeck.created_at.desc()).all()
    return render_template("flashcards.html", decks=decks)


@app.route("/flashcards/upload", methods=["POST"])
@admin_required
def upload_flashcards():
    validate_csrf()
    try:
        uploads = [upload for upload in request.files.getlist("anki_files") if upload.filename]
        if not uploads:
            raise ValueError("At least one Anki .apkg file is required.")
        imported_count = 0
        for upload in uploads:
            cards_by_deck, media_files = read_anki_package(upload)
            source_filename = secure_filename(upload.filename) or "anki-deck.apkg"
            media_urls = save_anki_media(media_files)
            for name, cards in cards_by_deck.items():
                deck_name = os.path.splitext(source_filename)[0] if name in {"Default", "Untitled deck"} else name
                deck = FlashcardDeck(name=deck_name[:200], source_filename=source_filename)
                db.session.add(deck)
                db.session.flush()
                for position, (front, back, _) in enumerate(cards, start=1):
                    db.session.add(Flashcard(
                        deck=deck,
                        front=sanitize_learning_html(replace_anki_media(front, media_urls)),
                        back=sanitize_learning_html(replace_anki_media(back, media_urls)),
                        position=position,
                    ))
                imported_count += len(cards)
        db.session.commit()
        flash(f"Imported {imported_count} flashcards from {len(uploads)} package(s).")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc))
    return redirect(url_for("flashcards"))


@app.route("/flashcards/<int:deck_id>")
def study_flashcards(deck_id):
    deck = FlashcardDeck.query.get_or_404(deck_id)
    cards = Flashcard.query.filter_by(deck_id=deck.id).order_by(Flashcard.position).all()
    return render_template("flashcard_study.html", deck=deck, cards=cards)


@app.route("/flashcards/<int:deck_id>/delete", methods=["POST"])
@admin_required
def delete_flashcard_deck(deck_id):
    validate_csrf()
    deck = FlashcardDeck.query.get_or_404(deck_id)
    db.session.delete(deck)
    db.session.commit()
    flash("Flashcard deck deleted.")
    return redirect(url_for("flashcards"))


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


@app.route("/admin/login-attempts")
@admin_required
def login_attempt_logs():
    attempts = LoginAttempt.query.order_by(LoginAttempt.attempted_at.desc()).limit(200).all()
    blocked_ips = BlockedIP.query.order_by(BlockedIP.blocked_at.desc()).all()
    return render_template(
        "login_attempts.html",
        attempts=attempts,
        blocked_ips=blocked_ips,
        failed_attempts=LoginAttempt.query.filter_by(success=False).count(),
    )


@app.route("/admin/blocked-ips/<int:blocked_ip_id>/unblock", methods=["POST"])
@admin_required
def unblock_ip(blocked_ip_id):
    validate_csrf()
    blocked_ip = BlockedIP.query.get_or_404(blocked_ip_id)
    db.session.delete(blocked_ip)
    db.session.commit()
    flash("IP address unblocked.")
    return redirect(url_for("login_attempt_logs"))

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
