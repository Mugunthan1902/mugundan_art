# 🎨 Mugundan Art Studio — Full Stack Setup

## What's included

```
mugundan-backend/
├── server.py          ← Flask backend (API + file serving)
├── db/
│   └── studio.db      ← SQLite database (auto-created on first run)
├── uploads/           ← All uploaded artwork images stored here
└── public/
    ├── index.html     ← Your portfolio website (copy from outputs)
    └── admin.html     ← Your private admin panel
```

---

## Step 1 — Install Python & Flask

Make sure Python 3 is installed:
```bash
python3 --version
```

Install Flask:
```bash
pip3 install flask
```

---

## Step 2 — Put your portfolio in the right place

Copy `mugundan-art-portfolio.html` → rename it to `index.html` → put it in the `public/` folder.

---

## Step 3 — Set your admin password

Open `server.py` and change line:
```python
ADMIN_SECRET = 'mugundan2024'   # ← change this!
```

---

## Step 4 — Run the server

```bash
cd mugundan-backend
python3 server.py
```

You'll see:
```
🎨 Mugundan Art Studio — Server starting...
   API:   http://localhost:5000/api
   Admin: http://localhost:5000/admin.html
```

- **Your website:** http://localhost:5000
- **Admin panel:** http://localhost:5000/admin.html

---

## What you can do in the Admin Panel

### 📬 Commissions Tab
- See every commission request customers send
- New badge shows unread count
- Change status: New → In Progress → Done
- Add private notes (e.g. "Called client on WhatsApp")
- Delete spam/cancelled requests

### 🖼 Artworks Tab
- Upload 1 or 50+ drawings at once (drag & drop or click)
- Add title, medium, year, size, description
- Set display order
- See reaction counts (❤️🔥😍👏✨) per drawing
- Delete artworks

### 📊 Dashboard
- Total commissions, new requests, in-progress, done
- Total artworks and reactions at a glance

---

## Deploying to the internet (so clients can access it)

### Option A — PythonAnywhere (free, easy)
1. Go to pythonanywhere.com → create free account
2. Upload this entire folder
3. Set up a Web App → Flask → point to `server.py`
4. Done — you get a public URL like `yourusername.pythonanywhere.com`

### Option B — Railway (free tier)
1. Push to GitHub
2. Connect Railway → deploy from repo
3. Set environment variable `PORT=5000`

### Option C — VPS (DigitalOcean/Hetzner, ~₹400/month)
```bash
# On the server:
pip3 install flask gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 server:app
```

---

## API Endpoints (for reference)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/commissions` | Submit a commission (public) |
| GET | `/api/artworks` | Get all artworks + reactions (public) |
| POST | `/api/artworks/:id/react` | Toggle reaction (public) |
| POST | `/api/admin/login` | Admin login |
| GET | `/api/admin/commissions` | Get all commissions (admin) |
| PUT | `/api/admin/commissions/:id` | Update status/notes (admin) |
| DELETE | `/api/admin/commissions/:id` | Delete commission (admin) |
| POST | `/api/admin/artworks` | Upload artwork (admin) |
| DELETE | `/api/admin/artworks/:id` | Delete artwork (admin) |
| GET | `/api/admin/stats` | Dashboard stats (admin) |

---

## Need help?
If anything breaks, check the terminal where `python3 server.py` is running — all errors print there.
