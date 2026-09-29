"""
Chuka Black Market
------------------------
A no-accounts local marketplace. Anyone can browse. Anyone can post.
A listing is removed with the password set during listing.
"""

import functools
import os
import shutil
import uuid
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect, url_for, abort, flash, Response
)
from PIL import Image, ImageOps
from werkzeug.security import generate_password_hash, check_password_hash

import database as db

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_PHOTOS = 5

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "guess")

FULL_MAX_DIM = 1600
THUMB_MAX_DIM = 480
FULL_QUALITY = 82
THUMB_QUALITY = 78

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "i-changed-it-in-prduction")
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024  # 12 MB per request

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def require_admin(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.password != ADMIN_PASSWORD:
            return Response(
                "Admin access required.", 401,
                {"WWW-Authenticate": 'Basic realm="Chuka Admin"'},
            )
        return view(*args, **kwargs)
    return wrapped


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_photo(file_storage, listing_dir: Path, index: int) -> str:
    img = Image.open(file_storage.stream)
    img = ImageOps.exif_transpose(img)  # bake in correct rotation before EXIF is dropped
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    filename = f"{index}_{uuid.uuid4().hex[:8]}.webp"

    listing_dir.mkdir(parents=True, exist_ok=True)
    full = img.copy()
    full.thumbnail((FULL_MAX_DIM, FULL_MAX_DIM))
    full.save(listing_dir / filename, "WEBP", quality=FULL_QUALITY)

    thumb_dir = listing_dir / "thumb"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb = img.copy()
    thumb.thumbnail((THUMB_MAX_DIM, THUMB_MAX_DIM))
    thumb.save(thumb_dir / filename, "WEBP", quality=THUMB_QUALITY)

    return f"{listing_dir.name}/{filename}"


def thumb_path(photo_path: str) -> str:
    folder, filename = photo_path.rsplit("/", 1)
    return f"{folder}/thumb/{filename}"


app.jinja_env.filters["thumb"] = thumb_path


def whatsapp_link(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if digits.startswith("254"):
        national = digits
    elif digits.startswith("0"):
        national = "254" + digits[1:]
    elif digits.startswith("7") or digits.startswith("1"):
        national = "254" + digits
    else:
        national = digits
    return f"https://wa.me/{national}"


app.jinja_env.filters["whatsapp_link"] = whatsapp_link


@app.route("/")
def index():
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    listings = db.search_listings(query=query, category=category)
    return render_template(
        "index.html",
        listings=listings,
        categories=db.CATEGORIES,
        query=query,
        active_category=category,
    )


SCHEMA_CONDITION = {
    "New": "https://schema.org/NewCondition",
    "Like New": "https://schema.org/UsedCondition",
    "Used - Good": "https://schema.org/UsedCondition",
    "Used - Fair": "https://schema.org/UsedCondition",
    "For Parts": "https://schema.org/DamagedCondition",
}


@app.route("/listing/<int:listing_id>")
def listing_detail(listing_id):
    listing = db.get_listing(listing_id)
    if listing is None:
        abort(404)
    photos = [p for p in (listing["photos"] or "").split(",") if p]

    product_schema = {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": listing["name"],
        "category": listing["category"],
        "url": request.url,
        "offers": {
            "@type": "Offer",
            "url": request.url,
            "priceCurrency": "KES",
            "price": listing["price"],
            "availability": "https://schema.org/InStock",
            "itemCondition": SCHEMA_CONDITION.get(listing["condition"], "https://schema.org/UsedCondition"),
        },
    }
    if listing["specs"]:
        product_schema["description"] = listing["specs"]
    if photos:
        product_schema["image"] = [
            url_for("static", filename=f"uploads/{p}", _external=True) for p in photos
        ]

    return render_template(
        "listing_detail.html", listing=listing, photos=photos, product_schema=product_schema
    )


@app.route("/sell", methods=["GET", "POST"])
def sell():
    if request.method == "GET":
        return render_template(
            "sell.html", categories=db.CATEGORIES, conditions=db.CONDITIONS
        )

    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    quantity = request.form.get("quantity", "1").strip()
    price = request.form.get("price", "").strip()
    condition = request.form.get("condition", "").strip()
    specs = request.form.get("specs", "").strip()
    contact_name = request.form.get("contact_name", "").strip()
    contact_phone = request.form.get("contact_phone", "").strip()
    password = request.form.get("password", "")
    password_confirm = request.form.get("password_confirm", "")

    errors = []
    if not name:
        errors.append("Give the item a name.")
    if category not in db.CATEGORIES:
        errors.append("Pick a category.")
    if condition not in db.CONDITIONS:
        errors.append("Pick a condition.")
    if not contact_phone:
        errors.append("A contact phone number is required so buyers can reach you.")
    if len(password) < 4:
        errors.append("Set a removal password (at least 4 characters).")
    elif password != password_confirm:
        errors.append("Passwords don't match.")

    try:
        quantity_val = max(1, int(quantity))
    except ValueError:
        quantity_val = 1

    try:
        price_val = float(price)
        if price_val < 0:
            raise ValueError
    except ValueError:
        errors.append("Enter a valid price.")
        price_val = 0

    files = [f for f in request.files.getlist("photos") if f and f.filename][:MAX_PHOTOS]
    for f in files:
        if not allowed_file(f.filename):
            errors.append(f"'{f.filename}' isn't a supported image type (use jpg, png or webp).")

    if errors:
        return render_template(
            "sell.html",
            categories=db.CATEGORIES,
            conditions=db.CONDITIONS,
            errors=errors,
            form=request.form,
        ), 400

    token = uuid.uuid4().hex  # kept only to satisfy the existing NOT NULL/UNIQUE column

    listing_id = db.create_listing({
        "name": name,
        "category": category,
        "quantity": quantity_val,
        "price": price_val,
        "condition": condition,
        "specs": specs,
        "contact_name": contact_name,
        "contact_phone": contact_phone,
        "token": token,
        "password_hash": generate_password_hash(password),
    })

    saved_paths = []
    if files:
        listing_dir = UPLOAD_DIR / str(listing_id)
        for i, f in enumerate(files):
            try:
                saved_paths.append(save_photo(f, listing_dir, i))
            except Exception:
                continue
        if saved_paths:
            db.set_listing_photos(listing_id, ",".join(saved_paths))

    return redirect(url_for("sell_success", listing_id=listing_id))


@app.route("/sell/success/<int:listing_id>")
def sell_success(listing_id):
    listing = db.get_listing(listing_id)
    if listing is None:
        abort(404)
    return render_template("success.html", listing=listing)


@app.route("/listing/<int:listing_id>/remove", methods=["GET", "POST"])
def remove_listing(listing_id):
    listing = db.get_listing(listing_id)
    if listing is None:
        abort(404)

    photos = [p for p in (listing["photos"] or "").split(",") if p]

    if not listing["password_hash"]:
        return render_template("remove_confirm.html", listing=listing, photos=photos, no_password=True)

    error = None
    if request.method == "POST":
        entered = request.form.get("password", "")
        if check_password_hash(listing["password_hash"], entered):
            db.delete_listing(listing_id)
            listing_dir = UPLOAD_DIR / str(listing_id)
            if listing_dir.exists():
                shutil.rmtree(listing_dir)
            return render_template("removed.html", listing=listing)
        error = "That password doesn't match. Try again."

    return render_template("remove_confirm.html", listing=listing, photos=photos, error=error)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "GET":
        return render_template("contact.html")

    message = request.form.get("message", "").strip()
    contact_info = request.form.get("contact_info", "").strip()

    if not message:
        return render_template("contact.html", error="Write a message before sending.", form=request.form), 400

    db.create_message(message, contact_info)
    return render_template("contact_sent.html")


@app.route("/admin674")
@require_admin
def admin_dashboard():
    listings = db.search_listings()
    message_count = len(db.get_all_messages())
    return render_template("admin.html", listings=listings, message_count=message_count)


@app.route("/admin674/remove/<int:listing_id>", methods=["POST"])
@require_admin
def admin_remove_listing(listing_id):
    listing = db.get_listing(listing_id)
    if listing is None:
        abort(404)
    db.delete_listing(listing_id)
    listing_dir = UPLOAD_DIR / str(listing_id)
    if listing_dir.exists():
        shutil.rmtree(listing_dir)
    return redirect(url_for("admin_dashboard"))


@app.route("/admin674/messages")
@require_admin
def admin_messages():
    messages = db.get_all_messages()
    return render_template("admin_messages.html", messages=messages)


@app.route("/admin674/messages/<int:message_id>/delete", methods=["POST"])
@require_admin
def admin_delete_message(message_id):
    db.delete_message(message_id)
    return redirect(url_for("admin_messages"))


@app.route("/robots.txt")
def robots_txt():
    body = f"User-agent: *\nAllow: /\n\nSitemap: {request.url_root}sitemap.xml\n"
    return Response(body, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    listings = db.search_listings()
    urls = [
        {"loc": url_for("index", _external=True), "changefreq": "hourly", "priority": "1.0"},
        {"loc": url_for("sell", _external=True), "changefreq": "monthly", "priority": "0.5"},
    ]
    for item in listings:
        urls.append({
            "loc": url_for("listing_detail", listing_id=item["id"], _external=True),
            "changefreq": "weekly",
            "priority": "0.8",
            "lastmod": str(item["created_at"])[:10],
        })

    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        xml.append("<url>")
        xml.append(f"<loc>{u['loc']}</loc>")
        if "lastmod" in u:
            xml.append(f"<lastmod>{u['lastmod']}</lastmod>")
        xml.append(f"<changefreq>{u['changefreq']}</changefreq>")
        xml.append(f"<priority>{u['priority']}</priority>")
        xml.append("</url>")
    xml.append("</urlset>")

    return Response("\n".join(xml), mimetype="application/xml")


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    db.init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
else:
    db.init_db()



