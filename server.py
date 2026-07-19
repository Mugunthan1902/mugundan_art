"""
Mugundan Art Studio — Backend Server
Flask + SQLite | No external dependencies beyond Flask
Run: python3 server.py
"""

from flask import Flask, request, jsonify, send_from_directory, send_file, g
import sqlite3, os, uuid, hashlib, json, re
from datetime import datetime
from werkzeug.utils import secure_filename

# ── CONFIG ──────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
# On Railway, use /tmp for writable storage; locally use project folder
IS_RAILWAY    = os.environ.get('RAILWAY_ENVIRONMENT') is not None
DATA_DIR      = '/tmp/mugundan' if IS_RAILWAY else BASE_DIR
DB_PATH       = os.path.join(DATA_DIR, 'db', 'studio.db')
UPLOADS_DIR   = os.path.join(DATA_DIR, 'uploads')
FRONTEND_DIR  = os.path.join(BASE_DIR, 'public')
ADMIN_SECRET  = 'mugundan2024'          # Change this in production!
ALLOWED_EXT   = {'png','jpg','jpeg','gif','webp'}
MAX_MB        = 20
REACTIONS     = ['❤️','🔥','😍','👏','✨']

os.makedirs(os.path.join(DATA_DIR,'db'), exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(FRONTEND_DIR, exist_ok=True)

app = Flask(__name__, static_folder=FRONTEND_DIR)
app.config['MAX_CONTENT_LENGTH'] = MAX_MB * 1024 * 1024

# ── DATABASE ─────────────────────────────────────────────────────────────────
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db: db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS commissions (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            contact     TEXT NOT NULL,
            art_type    TEXT NOT NULL,
            package     TEXT NOT NULL,
            description TEXT NOT NULL,
            special     TEXT,
            ref_file    TEXT,
            status      TEXT DEFAULT 'new',
            notes       TEXT DEFAULT '',
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS artworks (
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            art_type    TEXT NOT NULL,
            medium      TEXT DEFAULT '',
            year        TEXT DEFAULT '',
            size        TEXT DEFAULT '',
            description TEXT DEFAULT '',
            filename    TEXT NOT NULL,
            order_idx   INTEGER DEFAULT 0,
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reactions (
            id          TEXT PRIMARY KEY,
            artwork_id  TEXT NOT NULL,
            emoji       TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            UNIQUE(artwork_id, emoji, fingerprint)
        );

        CREATE TABLE IF NOT EXISTS admin_sessions (
            token       TEXT PRIMARY KEY,
            created_at  TEXT NOT NULL
        );
    """)
    db.commit()
    db.close()

init_db()

# ── HELPERS ──────────────────────────────────────────────────────────────────
def now():
    return datetime.utcnow().isoformat()

def allowed(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXT

def fingerprint():
    ip  = request.headers.get('X-Forwarded-For', request.remote_addr or '0')
    ua  = request.headers.get('User-Agent','')
    return hashlib.sha256(f"{ip}|{ua}".encode()).hexdigest()[:32]

def require_admin():
    token = request.headers.get('X-Admin-Token','')
    db = get_db()
    row = db.execute("SELECT token FROM admin_sessions WHERE token=?", (token,)).fetchone()
    return row is not None

def cors(resp):
    resp.headers['Access-Control-Allow-Origin']  = '*'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Admin-Token'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    return resp

@app.after_request
def add_cors(resp):
    return cors(resp)

@app.route('/', defaults={'path':''})
@app.route('/<path:path>')
def catch_all(path):
    # Serve static frontend files
    full = os.path.join(FRONTEND_DIR, path)
    if path and os.path.isfile(full):
        return send_file(full)
    index = os.path.join(FRONTEND_DIR, 'index.html')
    if os.path.isfile(index):
        return send_file(index)
    return jsonify({"status":"Mugundan Art Studio API running"}), 200

# ── ADMIN AUTH ───────────────────────────────────────────────────────────────
@app.route('/api/admin/login', methods=['POST','OPTIONS'])
def admin_login():
    if request.method == 'OPTIONS': return jsonify({}), 200
    data = request.get_json(silent=True) or {}
    if data.get('password') == ADMIN_SECRET:
        token = str(uuid.uuid4())
        get_db().execute("INSERT INTO admin_sessions VALUES (?,?)", (token, now()))
        get_db().commit()
        return jsonify({"ok": True, "token": token})
    return jsonify({"ok": False, "error": "Wrong password"}), 401

@app.route('/api/admin/logout', methods=['POST','OPTIONS'])
def admin_logout():
    if request.method == 'OPTIONS': return jsonify({}), 200
    token = request.headers.get('X-Admin-Token','')
    get_db().execute("DELETE FROM admin_sessions WHERE token=?", (token,))
    get_db().commit()
    return jsonify({"ok": True})

# ── COMMISSIONS ───────────────────────────────────────────────────────────────
@app.route('/api/commissions', methods=['POST','OPTIONS'])
def submit_commission():
    if request.method == 'OPTIONS': return jsonify({}), 200
    ref_file = None
    if 'ref_file' in request.files:
        f = request.files['ref_file']
        if f and allowed(f.filename):
            ext = f.filename.rsplit('.',1)[1].lower()
            ref_file = f"ref_{uuid.uuid4().hex[:8]}.{ext}"
            f.save(os.path.join(UPLOADS_DIR, ref_file))

    d = request.form
    required = ['name','contact','art_type','package','description']
    for field in required:
        if not d.get(field,'').strip():
            return jsonify({"ok":False,"error":f"Missing {field}"}), 400

    cid = str(uuid.uuid4())
    get_db().execute(
        "INSERT INTO commissions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (cid, d['name'].strip(), d['contact'].strip(), d['art_type'],
         d['package'], d['description'].strip(), d.get('special','').strip(),
         ref_file, 'new', '', now())
    )
    get_db().commit()
    return jsonify({"ok": True, "id": cid})

@app.route('/api/admin/commissions', methods=['GET','OPTIONS'])
def get_commissions():
    if request.method == 'OPTIONS': return jsonify({}), 200
    if not require_admin(): return jsonify({"error":"Unauthorized"}), 401
    status = request.args.get('status','all')
    db = get_db()
    if status == 'all':
        rows = db.execute("SELECT * FROM commissions ORDER BY created_at DESC").fetchall()
    else:
        rows = db.execute("SELECT * FROM commissions WHERE status=? ORDER BY created_at DESC",(status,)).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/admin/commissions/<cid>', methods=['PUT','OPTIONS'])
def update_commission(cid):
    if request.method == 'OPTIONS': return jsonify({}), 200
    if not require_admin(): return jsonify({"error":"Unauthorized"}), 401
    d = request.get_json(silent=True) or {}
    get_db().execute(
        "UPDATE commissions SET status=?, notes=? WHERE id=?",
        (d.get('status','new'), d.get('notes',''), cid)
    )
    get_db().commit()
    return jsonify({"ok": True})

@app.route('/api/admin/commissions/<cid>', methods=['DELETE','OPTIONS'])
def delete_commission(cid):
    if request.method == 'OPTIONS': return jsonify({}), 200
    if not require_admin(): return jsonify({"error":"Unauthorized"}), 401
    get_db().execute("DELETE FROM commissions WHERE id=?", (cid,))
    get_db().commit()
    return jsonify({"ok": True})

# ── ARTWORKS ─────────────────────────────────────────────────────────────────
@app.route('/api/artworks', methods=['GET','OPTIONS'])
def get_artworks():
    if request.method == 'OPTIONS': return jsonify({}), 200
    art_type = request.args.get('type','all')
    db = get_db()
    if art_type == 'all':
        rows = db.execute("SELECT * FROM artworks ORDER BY order_idx, created_at DESC").fetchall()
    else:
        rows = db.execute("SELECT * FROM artworks WHERE art_type=? ORDER BY order_idx, created_at DESC",(art_type,)).fetchall()
    artworks = []
    fp = fingerprint()
    for r in rows:
        a = dict(r)
        # Get reaction counts + whether user reacted
        for emoji in REACTIONS:
            count = db.execute(
                "SELECT COUNT(*) as c FROM reactions WHERE artwork_id=? AND emoji=?",
                (r['id'], emoji)
            ).fetchone()['c']
            reacted = db.execute(
                "SELECT id FROM reactions WHERE artwork_id=? AND emoji=? AND fingerprint=?",
                (r['id'], emoji, fp)
            ).fetchone()
            a[f'react_{emoji}'] = count
            a[f'reacted_{emoji}'] = reacted is not None
        artworks.append(a)
    return jsonify(artworks)

@app.route('/api/artworks/<aid>/react', methods=['POST','OPTIONS'])
def react_artwork(aid):
    if request.method == 'OPTIONS': return jsonify({}), 200
    d = request.get_json(silent=True) or {}
    emoji = d.get('emoji','')
    if emoji not in REACTIONS:
        return jsonify({"ok":False,"error":"Invalid emoji"}), 400
    fp = fingerprint()
    db = get_db()
    existing = db.execute(
        "SELECT id FROM reactions WHERE artwork_id=? AND emoji=? AND fingerprint=?",
        (aid, emoji, fp)
    ).fetchone()
    if existing:
        db.execute("DELETE FROM reactions WHERE artwork_id=? AND emoji=? AND fingerprint=?", (aid, emoji, fp))
        db.commit()
        return jsonify({"ok":True, "action":"removed"})
    else:
        db.execute("INSERT INTO reactions VALUES (?,?,?,?,?)", (str(uuid.uuid4()), aid, emoji, fp, now()))
        db.commit()
        return jsonify({"ok":True, "action":"added"})

@app.route('/api/admin/artworks', methods=['POST','OPTIONS'])
def upload_artwork():
    if request.method == 'OPTIONS': return jsonify({}), 200
    if not require_admin(): return jsonify({"error":"Unauthorized"}), 401
    if 'image' not in request.files:
        return jsonify({"ok":False,"error":"No image"}), 400
    f = request.files['image']
    if not allowed(f.filename):
        return jsonify({"ok":False,"error":"Invalid file type"}), 400
    ext = f.filename.rsplit('.',1)[1].lower()
    filename = f"art_{uuid.uuid4().hex}.{ext}"
    f.save(os.path.join(UPLOADS_DIR, filename))
    d = request.form
    aid = str(uuid.uuid4())
    get_db().execute(
        "INSERT INTO artworks VALUES (?,?,?,?,?,?,?,?,?,?)",
        (aid, d.get('title','Untitled'), d.get('art_type','other'),
         d.get('medium',''), d.get('year',''), d.get('size',''),
         d.get('description',''), filename, int(d.get('order_idx',0)), now())
    )
    get_db().commit()
    return jsonify({"ok":True,"id":aid,"filename":filename})

@app.route('/api/admin/artworks', methods=['GET','OPTIONS'])
def admin_get_artworks():
    if request.method == 'OPTIONS': return jsonify({}), 200
    if not require_admin(): return jsonify({"error":"Unauthorized"}), 401
    rows = get_db().execute("SELECT * FROM artworks ORDER BY order_idx, created_at DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/admin/artworks/<aid>', methods=['PUT','OPTIONS'])
def update_artwork(aid):
    if request.method == 'OPTIONS': return jsonify({}), 200
    if not require_admin(): return jsonify({"error":"Unauthorized"}), 401
    d = request.get_json(silent=True) or {}
    get_db().execute(
        "UPDATE artworks SET title=?,art_type=?,medium=?,year=?,size=?,description=?,order_idx=? WHERE id=?",
        (d.get('title',''), d.get('art_type',''), d.get('medium',''),
         d.get('year',''), d.get('size',''), d.get('description',''),
         d.get('order_idx',0), aid)
    )
    get_db().commit()
    return jsonify({"ok":True})

@app.route('/api/admin/artworks/<aid>', methods=['DELETE','OPTIONS'])
def delete_artwork(aid):
    if request.method == 'OPTIONS': return jsonify({}), 200
    if not require_admin(): return jsonify({"error":"Unauthorized"}), 401
    db = get_db()
    row = db.execute("SELECT filename FROM artworks WHERE id=?", (aid,)).fetchone()
    if row:
        fpath = os.path.join(UPLOADS_DIR, row['filename'])
        if os.path.exists(fpath): os.remove(fpath)
    db.execute("DELETE FROM artworks WHERE id=?", (aid,))
    db.execute("DELETE FROM reactions WHERE artwork_id=?", (aid,))
    db.commit()
    return jsonify({"ok":True})

@app.route('/api/admin/stats', methods=['GET','OPTIONS'])
def get_stats():
    if request.method == 'OPTIONS': return jsonify({}), 200
    if not require_admin(): return jsonify({"error":"Unauthorized"}), 401
    db = get_db()
    total_c    = db.execute("SELECT COUNT(*) as c FROM commissions").fetchone()['c']
    new_c      = db.execute("SELECT COUNT(*) as c FROM commissions WHERE status='new'").fetchone()['c']
    inprog_c   = db.execute("SELECT COUNT(*) as c FROM commissions WHERE status='in_progress'").fetchone()['c']
    done_c     = db.execute("SELECT COUNT(*) as c FROM commissions WHERE status='done'").fetchone()['c']
    total_art  = db.execute("SELECT COUNT(*) as c FROM artworks").fetchone()['c']
    total_reac = db.execute("SELECT COUNT(*) as c FROM reactions").fetchone()['c']
    return jsonify({
        "commissions": {"total":total_c,"new":new_c,"in_progress":inprog_c,"done":done_c},
        "artworks": total_art,
        "reactions": total_reac
    })

# ── SERVE UPLOADED IMAGES ─────────────────────────────────────────────────────
@app.route('/uploads/<filename>')
def serve_upload(filename):
    return send_from_directory(UPLOADS_DIR, filename)

if __name__ == '__main__':
    print("\n🎨 Mugundan Art Studio — Server starting...")
    print("   API:   http://localhost:5000/api")
    print("   Admin: http://localhost:5000/admin.html")
    print(f"   Admin password: {ADMIN_SECRET}")
    print("   Change ADMIN_SECRET in server.py before going live!\n")
    app.run(debug=True, port=5000, host='0.0.0.0')
