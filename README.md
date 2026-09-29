# Chuka Black Market

A no-accounts local marketplace for Chuka. Anyone can browse. Anyone
can post something to sell. A listing comes down when its seller enters
the password they set when posting it — there's no login for anyone.

## How it works

- **Board (`/`)** — every listing, newest first. Search bar + category pills filter it.
- **Listing page (`/listing/<id>`)** — photos, specs, price, condition, and the seller's contact info (call or WhatsApp).
- **Sell (`/sell`)** — the upload form: name, category, quantity, price, condition, free-text details (size/dimensions/etc.), up to 5 photos, and contact info.
- **Removal** — when posting, the seller sets a password. Any time after that, opening the listing shows a "Remove product" link that asks for that password; entering it correctly deletes the listing and its photos. No account, no link to lose — just a password the seller picked themselves.
- **Admin (`/admin674`)** — a password-protected page listing every item on the board with a one-click Remove button, for when you need to take something down yourself. Not linked anywhere in the public site — only reachable if you know the URL and the password.
- **Contact (`/contact`)** — a public form, linked in the footer, for questions or problem reports. No personal contact info of yours is shown anywhere; messages are saved and only visible to you via `/admin674/messages` (same password as the rest of admin). The sender's phone/email is optional and only used if they want a reply.





Everything lives in one SQLite file (`chuka.db`), created automatically the first time the app runs.

## Run it locally

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python3 app.py
```

Visit `http://localhost:5000`.

## Project layout

```
app.py                 Routes and request handling
database.py             SQLite schema + all queries, categories & conditions list
templates/               Jinja2 HTML pages
static/css/style.css     All styling
static/js/main.js        Copy-link button, photo count hint
static/uploads/          Uploaded photos, one subfolder per listing
```

## Changing categories or conditions

Edit the `CATEGORIES` and `CONDITIONS` lists at the top of `database.py`. They
automatically populate the dropdowns and the filter pills — nothing else to change.

## Deploying (Render / PythonAnywhere free tier)

The app is a standard Flask app and runs under gunicorn:

```bash
gunicorn app:app
```

## Notes

- No authentication anywhere, by design — that was the brief. Anyone who knows
  a listing's removal password can delete it (that's the seller — nobody else
  is shown the password), and there's no way to edit a listing after posting
  (remove it and repost instead).
- Uploaded file size is capped at 12 MB per submission and 5 photos per listing.
