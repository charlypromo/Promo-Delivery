from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import os
import base64
import mimetypes, json, hmac, csv, io
from functools import wraps

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "CHANGE-ME-PROMO-DELIVERY-2026")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("COOKIE_SECURE", "1") == "1"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=12)

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "PromoAdmin2026!")
DRIVER_PASSWORDS = {
    "Jeff": os.getenv("DRIVER_JEFF_PASSWORD", ""),
    "Duckens": os.getenv("DRIVER_DUCKENS_PASSWORD", ""),
    "Jn Fritz": os.getenv("DRIVER_JN_FRITZ_PASSWORD", ""),
}


@app.after_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.path.startswith(("/admin", "/driver", "/profile", "/api/")):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            if request.path.startswith("/api/"):
                return jsonify({"error": "unauthorized"}), 401
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapped


def driver_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if session.get("role") != "driver" or not session.get("driver"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "unauthorized"}), 401
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapped


def customer_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if session.get("role") != "customer" or not session.get("customer_id"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "member_login_required"}), 401
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapped


database_url = os.getenv("DATABASE_URL", "").strip()
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
if not database_url:
    database_url = "sqlite:///promo_delivery.db"

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True, "pool_recycle": 300}
db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(140), nullable=False)
    phone = db.Column(db.String(60), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def public_dict(self):
        return {"id": self.id, "full_name": self.full_name, "phone": self.phone, "username": self.username}


class DriverAccount(db.Model):
    __tablename__ = "driver_accounts"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def as_dict(self):
        return {"id": self.id, "name": self.name, "active": bool(self.active),
                "created_at": self.created_at.isoformat(timespec="seconds") if self.created_at else ""}


class PasswordResetRequest(db.Model):
    __tablename__ = "password_reset_requests"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    username = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(60), nullable=False)
    status = db.Column(db.String(30), default="En attente", nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)

    def as_dict(self):
        return {"id": self.id, "user_id": self.user_id, "username": self.username,
                "phone": self.phone, "status": self.status,
                "created_at": self.created_at.isoformat(timespec="seconds") if self.created_at else "",
                "resolved_at": self.resolved_at.isoformat(timespec="seconds") if self.resolved_at else ""}


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255), default="")
    price = db.Column(db.Float, default=0)
    icon = db.Column(db.String(20), default="📦")
    active = db.Column(db.Boolean, default=True)

    def as_dict(self):
        return {"id": self.id, "name": self.name, "category": self.category,
                "description": self.description or "", "price": self.price or 0,
                "icon": self.icon or "📦", "active": bool(self.active)}


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, nullable=True, index=True)
    customer = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(60), nullable=False)
    address = db.Column(db.Text, nullable=False)
    landmark = db.Column(db.String(255), default="")
    zone = db.Column(db.String(255), default="")
    payment = db.Column(db.String(50), default="Cash")
    transaction_id = db.Column(db.String(120), default="")
    paid_amount = db.Column(db.Float, default=0)
    payment_status = db.Column(db.String(50), default="Cash")
    order_type = db.Column(db.String(50), default="Livraison")
    note = db.Column(db.Text, default="")
    items_json = db.Column(db.Text, nullable=False)
    subtotal = db.Column(db.Float, default=0)
    delivery_fee = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    status = db.Column(db.String(50), default="Nouveau", index=True)
    driver = db.Column(db.String(120), default="", index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def as_dict(self):
        return {
            "id": self.id, "code": self.code, "customer_id": self.customer_id,
            "customer": self.customer, "phone": self.phone,
            "address": self.address, "landmark": self.landmark or "", "zone": self.zone or "",
            "payment": self.payment or "Cash", "transaction_id": self.transaction_id or "",
            "paid_amount": float(self.paid_amount or 0),
            "payment_status": self.payment_status or ("Cash" if (self.payment or "Cash") == "Cash" else "Ap tann verifikasyon"),
            "order_type": self.order_type or "Livraison", "note": self.note or "",
            "items": json.loads(self.items_json or "[]"), "subtotal": self.subtotal or 0,
            "delivery_fee": self.delivery_fee or 0, "total": self.total or 0,
            "status": self.status or "Nouveau", "driver": self.driver or "",
            "created_at": self.created_at.isoformat(timespec="seconds") if self.created_at else ""
        }

    cash_received = db.Column(db.Float, nullable=False, default=0)
    accepted_at = db.Column(db.DateTime, nullable=True)
    en_route_at = db.Column(db.DateTime, nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)

class Ad(db.Model):
    __tablename__ = "ads"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, default="")
    image_url = db.Column(db.String(500), default="")
    target_url = db.Column(db.String(500), default="")
    active = db.Column(db.Boolean, default=True)
    starts_at = db.Column(db.Date, nullable=True)
    ends_at = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    image_data = db.Column(db.Text, nullable=True)

    def as_dict(self):
        return {
            "id": self.id, "title": self.title, "description": self.description or "",
            "image_url": self.image_url or "", "target_url": self.target_url or "",
            "active": bool(self.active),
            "starts_at": self.starts_at.isoformat() if self.starts_at else "",
            "ends_at": self.ends_at.isoformat() if self.ends_at else ""
        }


def seed_products():
    if Product.query.count():
        return
    items = [
        ("Pain", "pain", "Pain fre", 75, "🥖"), ("Sucre", "sucre", "Sachet / kantite", 150, "🍚"),
        ("Dlo", "eau", "Bouteille oswa gallon", 100, "💧"), ("Plat du jour", "food", "Manje pare", 500, "🍛"),
        ("Gaz propane", "gas", "Pri baz — selon kantite", 750, "🔥"), ("Taxi", "taxi", "Pri sou demann selon trajè", 0, "🚕"),
        ("Ti komisyon", "other", "Ekri sa w bezwen", 0, "🛍️"), ("Livraison dokiman", "other", "Dokiman oswa ti pakè", 250, "📄"),
        ("Fè mache", "other", "Nou fè ti acha pou ou", 0, "🧺")
    ]
    for n, c, d, p, i in items:
        db.session.add(Product(name=n, category=c, description=d, price=p, icon=i))
    db.session.commit()



def seed_driver_accounts():
    if DriverAccount.query.count():
        return
    for name, password in DRIVER_PASSWORDS.items():
        if password:
            db.session.add(DriverAccount(
                name=name,
                password_hash=generate_password_hash(password),
                active=True
            ))
    db.session.commit()

def seed_ads():
    if Ad.query.count():
        return
    db.session.add(Ad(
        title="📣 Espas Piblisite Promo Delivery",
        description="Admin ka mete Paryaj Lakay, La Grâce Solutions, gwo bal, spektak ak lòt anons isit la.",
        image_url="", target_url="", image_data="", active=True
    ))
    db.session.commit()


def current_customer():
    cid = session.get("customer_id")
    return db.session.get(User, cid) if cid else None


@app.route("/")
def client():
    user = current_customer() if session.get("role") == "customer" else None
    return render_template("index.html", page="client", member=user)


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("role") == "customer":
        return redirect("/")
    error = ""
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not full_name or not phone or not username or not password:
            error = "Ranpli tout chan yo."
        elif len(username) < 3:
            error = "Username lan dwe gen omwen 3 karaktè."
        elif len(password) < 6:
            error = "Modpas la dwe gen omwen 6 karaktè."
        elif password != confirm:
            error = "De modpas yo pa menm."
        elif User.query.filter(db.func.lower(User.username) == username).first():
            error = "Username sa deja itilize."
        else:
            user = User(full_name=full_name, phone=phone, username=username,
                        password_hash=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            session.clear()
            session["role"] = "customer"
            session["customer_id"] = user.id
            session["name"] = user.full_name
            session.permanent = True
            return redirect("/")
    return render_template("index.html", page="register", error=error)


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    message = ""
    error = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        user = User.query.filter(db.func.lower(User.username) == username).first()
        if not user or user.phone.strip() != phone:
            error = "Nou pa jwenn yon manm ak username ak telefòn sa yo."
        else:
            existing = PasswordResetRequest.query.filter_by(user_id=user.id, status="En attente").first()
            if not existing:
                db.session.add(PasswordResetRequest(
                    user_id=user.id, username=user.username, phone=user.phone, status="En attente"
                ))
                db.session.commit()
            message = "Demann reset modpas la voye bay Admin. Promo Delivery ap kontakte ou."
    return render_template("index.html", page="forgot", error=error, success=message)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        role = request.form.get("role", "customer")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if role == "customer":
            user = User.query.filter(db.func.lower(User.username) == username.lower()).first()
            if user and check_password_hash(user.password_hash, password):
                session.clear(); session["role"] = "customer"; session["customer_id"] = user.id; session["name"] = user.full_name; session.permanent = True
                return redirect("/")
        elif role == "admin" and hmac.compare_digest(username, ADMIN_USER) and hmac.compare_digest(password, ADMIN_PASSWORD):
            session.clear(); session["role"] = "admin"; session["name"] = "Admin"; session.permanent = True
            return redirect("/admin")
        elif role == "driver":
            driver_account = DriverAccount.query.filter(
                db.func.lower(DriverAccount.name) == username.lower(),
                DriverAccount.active.is_(True)
            ).first()
            if driver_account and check_password_hash(driver_account.password_hash, password):
                session.clear(); session["role"] = "driver"; session["driver"] = driver_account.name; session["name"] = driver_account.name; session.permanent = True
                return redirect("/driver")
        error = "Non itilizatè oswa modpas pa kòrèk."
    return render_template("index.html", page="login", error=error)


@app.route("/profile", methods=["GET", "POST"])
@customer_required
def profile():
    user = current_customer()
    error = ""
    success = ""
    if request.method == "POST":
        action = request.form.get("action", "profile")
        if action == "profile":
            full_name = request.form.get("full_name", "").strip()
            phone = request.form.get("phone", "").strip()
            if not full_name or not phone:
                error = "Non ak telefòn obligatwa."
            else:
                user.full_name = full_name
                user.phone = phone
                db.session.commit()
                session["name"] = user.full_name
                success = "Profil ou mete ajou."
        elif action == "password":
            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            confirm_password = request.form.get("confirm_password", "")
            if not check_password_hash(user.password_hash, current_password):
                error = "Modpas aktyèl la pa kòrèk."
            elif len(new_password) < 8:
                error = "Nouvo modpas la dwe gen omwen 8 karaktè."
            elif new_password != confirm_password:
                error = "De nouvo modpas yo pa menm."
            else:
                user.password_hash = generate_password_hash(new_password)
                db.session.commit()
                success = "Modpas ou chanje avèk siksè."
    return render_template("index.html", page="profile", member=user, error=error, success=success)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/admin")
@admin_required
def admin():
    return render_template("index.html", page="admin", auth_name=session.get("name"))


@app.route("/driver")
@driver_required
def driver():
    return render_template("index.html", page="driver", auth_name=session.get("driver"))


@app.route("/health")
def health():
    return {"ok": True, "service": "Promo Delivery V15"}


@app.get("/api/me")
def me():
    data = {"role": session.get("role"), "name": session.get("name"), "driver": session.get("driver")}
    if session.get("role") == "customer":
        u = current_customer()
        data["customer"] = u.public_dict() if u else None
    return jsonify(data)


@app.get("/api/products")
def products():
    return jsonify([p.as_dict() for p in Product.query.filter_by(active=True).order_by(Product.id).all()])


@app.post("/api/products")
@admin_required
def add_product():
    d = request.get_json(silent=True) or {}
    name = str(d.get("name", "")).strip()
    if not name:
        return jsonify({"error": "name_required"}), 400
    p = Product(name=name, category=str(d.get("category", "other")),
                description=str(d.get("description", "Ajoute pa Admin")),
                price=float(d.get("price", 0) or 0), icon=str(d.get("icon", "📦")) or "📦")
    db.session.add(p); db.session.commit()
    return jsonify({"ok": True, "id": p.id})


@app.put("/api/products/<int:pid>")
@admin_required
def edit_product(pid):
    p = db.session.get(Product, pid)
    if not p:
        return jsonify({"error": "not_found"}), 404
    d = request.get_json(silent=True) or {}
    if "name" in d:
        name = str(d.get("name", "")).strip()
        if name: p.name = name
    if "category" in d: p.category = str(d.get("category", "other"))
    if "description" in d: p.description = str(d.get("description", ""))
    if "price" in d: p.price = float(d.get("price", 0) or 0)
    if "icon" in d: p.icon = str(d.get("icon", "📦")) or "📦"
    if "active" in d: p.active = bool(d.get("active"))
    db.session.commit()
    return jsonify({"ok": True, "product": p.as_dict()})


@app.delete("/api/products/<int:pid>")
@admin_required
def remove_product(pid):
    p = db.session.get(Product, pid)
    if not p:
        return jsonify({"error": "not_found"}), 404
    p.active = False; db.session.commit()
    return jsonify({"ok": True})


@app.get("/api/ads")
def public_ads():
    today = date.today()
    rows = Ad.query.filter_by(active=True).order_by(Ad.id.desc()).all()
    rows = [a for a in rows if (not a.starts_at or a.starts_at <= today) and (not a.ends_at or a.ends_at >= today)]
    return jsonify([a.as_dict() for a in rows])



@app.post("/api/admin/ad-image")
@admin_required
def admin_upload_ad_image():
    if "image" not in request.files:
        return jsonify({"error": "missing_image"}), 400
    f = request.files["image"]
    if not f or not f.filename:
        return jsonify({"error": "missing_image"}), 400
    ext = os.path.splitext(f.filename.lower())[1]
    allowed = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
    if ext not in allowed:
        return jsonify({"error": "invalid_type", "message": "PNG, JPG oswa JPEG sèlman."}), 400
    raw = f.read()
    if len(raw) > 3 * 1024 * 1024:
        return jsonify({"error": "too_large", "message": "Foto a dwe pi piti pase 3 MB."}), 400
    encoded = base64.b64encode(raw).decode("ascii")
    data_uri = f"data:{allowed[ext]};base64,{encoded}"
    return jsonify({"ok": True, "image_data": data_uri, "filename": f.filename})


@app.get("/api/admin/ads")
@admin_required
def admin_ads():
    return jsonify([a.as_dict() for a in Ad.query.order_by(Ad.id.desc()).all()])


@app.post("/api/admin/ads")
@admin_required
def add_ad():
    d = request.get_json(silent=True) or {}
    title = str(d.get("title", "")).strip()
    if not title:
        return jsonify({"error": "title_required"}), 400
    def parse_date(v):
        try: return datetime.strptime(v, "%Y-%m-%d").date() if v else None
        except ValueError: return None
    ad = Ad(title=title, description=str(d.get("description", "")).strip(),
            image_url=str(d.get("image_url", "")).strip(),
        image_data=str(d.get("image_data", "")).strip(), target_url=str(d.get("target_url", "")).strip(),
            active=bool(d.get("active", True)), starts_at=parse_date(str(d.get("starts_at", ""))),
            ends_at=parse_date(str(d.get("ends_at", ""))))
    db.session.add(ad); db.session.commit()
    return jsonify({"ok": True, "id": ad.id})


@app.patch("/api/admin/ads/<int:aid>")
@admin_required
def edit_ad(aid):
    ad = db.session.get(Ad, aid)
    if not ad:
        return jsonify({"error": "not_found"}), 404
    d = request.get_json(silent=True) or {}
    if "active" in d: ad.active = bool(d.get("active"))
    if "title" in d and str(d.get("title", "")).strip(): ad.title = str(d.get("title")).strip()
    if "description" in d: ad.description = str(d.get("description", "")).strip()
    if "image_url" in d: ad.image_url = str(d.get("image_url", "")).strip()
    if "target_url" in d: ad.target_url = str(d.get("target_url", "")).strip()
    db.session.commit()
    return jsonify({"ok": True})


@app.delete("/api/admin/ads/<int:aid>")
@admin_required
def delete_ad(aid):
    ad = db.session.get(Ad, aid)
    if not ad:
        return jsonify({"error": "not_found"}), 404
    db.session.delete(ad); db.session.commit()
    return jsonify({"ok": True})


@app.get("/api/orders")
@admin_required
def orders():
    return jsonify([o.as_dict() for o in Order.query.order_by(Order.id.desc()).all()])


@app.get("/api/orders/<code>")
@customer_required
def order_by_code(code):
    o = Order.query.filter(db.func.upper(Order.code) == code.upper(), Order.customer_id == session.get("customer_id")).first()
    return jsonify(o.as_dict()) if o else (jsonify({"error": "not_found"}), 404)


@app.get("/api/my-orders")
@customer_required
def my_orders():
    rows = Order.query.filter_by(customer_id=session.get("customer_id")).order_by(Order.id.desc()).all()
    return jsonify([o.as_dict() for o in rows])


@app.post("/api/orders")
@customer_required
def create_order():
    d = request.get_json(silent=True) or {}
    items = d.get("items", [])
    address = str(d.get("address", "")).strip()
    user = current_customer()
    if not user:
        return jsonify({"error": "member_login_required"}), 401
    if not items or not address:
        return jsonify({"error": "missing_fields"}), 400
    subtotal = sum(float(i.get("price", 0) or 0) * int(i.get("qty", 1) or 1) for i in items)
    fee = float(d.get("delivery_fee", 0) or 0)
    now = datetime.utcnow()
    code = "PD-" + now.strftime("%y%m%d%H%M%S%f")[-12:]
    payment = str(d.get("payment", "Cash")).strip() or "Cash"
    transaction_id = str(d.get("transaction_id", "")).strip()
    try:
        paid_amount = float(d.get("paid_amount", 0) or 0)
    except (TypeError, ValueError):
        paid_amount = 0
    if payment in ("MonCash", "NatCash") and not transaction_id:
        return jsonify({"error": "transaction_required"}), 400
    if payment in ("MonCash", "NatCash") and paid_amount <= 0:
        return jsonify({"error": "paid_amount_required"}), 400
    if payment == "Cash":
        paid_amount = 0
    payment_status = "Cash" if payment == "Cash" else "Ap tann verifikasyon"
    o = Order(code=code, customer_id=user.id, customer=user.full_name, phone=user.phone, address=address,
              landmark=str(d.get("landmark", "")).strip(), zone=str(d.get("zone", "")), payment=payment,
              transaction_id=transaction_id, paid_amount=paid_amount, payment_status=payment_status,
              order_type=str(d.get("order_type", "Livraison")), note=str(d.get("note", "")).strip(),
              items_json=json.dumps(items, ensure_ascii=False), subtotal=subtotal, delivery_fee=fee,
              total=subtotal + fee, status="Nouveau", driver="", created_at=now)
    db.session.add(o); db.session.commit()
    return jsonify({"ok": True, "code": code, "total": o.total})


@app.patch("/api/orders/<int:oid>")
def patch_order(oid):
    o = db.session.get(Order, oid)
    if not o:
        return jsonify({"error": "not_found"}), 404
    role = session.get("role")
    d = request.get_json(silent=True) or {}
    if role == "admin":
        if "status" in d: o.status = str(d["status"])
        if o.status == "Préparation" and not o.accepted_at:
            o.accepted_at = datetime.utcnow()
        elif o.status == "En route" and not o.en_route_at:
            o.en_route_at = datetime.utcnow()
        elif o.status == "Livré" and not o.delivered_at:
            o.delivered_at = datetime.utcnow()
        if "driver" in d: o.driver = str(d["driver"])
        if "payment_status" in d and o.payment in ("MonCash", "NatCash"):
            value = str(d["payment_status"])
            if value not in ("Ap tann verifikasyon", "Konfime", "Refize"):
                return jsonify({"error": "invalid_payment_status"}), 400
            o.payment_status = value
    elif role == "driver" and o.driver == session.get("driver"):
        if "status" not in d or str(d["status"]) not in ("Préparation", "En route", "Livré"):
            return jsonify({"error": "forbidden"}), 403
        o.status = str(d["status"])
        if o.status == "Préparation" and not o.accepted_at:
            o.accepted_at = datetime.utcnow()
        elif o.status == "En route" and not o.en_route_at:
            o.en_route_at = datetime.utcnow()
        elif o.status == "Livré" and not o.delivered_at:
            o.delivered_at = datetime.utcnow()
    else:
        return jsonify({"error": "unauthorized"}), 401
    db.session.commit()
    return jsonify({"ok": True})


@app.get("/api/admin/drivers")
@admin_required
def admin_drivers():
    return jsonify([d.as_dict() for d in DriverAccount.query.order_by(DriverAccount.name.asc()).all()])


@app.post("/api/admin/drivers")
@admin_required
def admin_add_driver():
    d = request.get_json(silent=True) or {}
    name = str(d.get("name", "")).strip()
    password = str(d.get("password", ""))
    if not name or len(password) < 6:
        return jsonify({"error": "name_and_password_required"}), 400
    if DriverAccount.query.filter(db.func.lower(DriverAccount.name) == name.lower()).first():
        return jsonify({"error": "driver_exists"}), 400
    row = DriverAccount(name=name, password_hash=generate_password_hash(password), active=True)
    db.session.add(row); db.session.commit()
    return jsonify({"ok": True, "driver": row.as_dict()})


@app.patch("/api/admin/drivers/<int:driver_id>")
@admin_required
def admin_edit_driver(driver_id):
    row = db.session.get(DriverAccount, driver_id)
    if not row:
        return jsonify({"error": "not_found"}), 404
    d = request.get_json(silent=True) or {}
    if "active" in d:
        row.active = bool(d.get("active"))
    if "password" in d and str(d.get("password", "")):
        password = str(d.get("password"))
        if len(password) < 6:
            return jsonify({"error": "password_too_short"}), 400
        row.password_hash = generate_password_hash(password)
    db.session.commit()
    return jsonify({"ok": True, "driver": row.as_dict()})


@app.get("/api/admin/password-resets")
@admin_required
def admin_password_resets():
    return jsonify([r.as_dict() for r in PasswordResetRequest.query.order_by(PasswordResetRequest.id.desc()).all()])


@app.post("/api/admin/password-resets/<int:request_id>/resolve")
@admin_required
def admin_resolve_password_reset(request_id):
    req = db.session.get(PasswordResetRequest, request_id)
    if not req:
        return jsonify({"error": "not_found"}), 404
    d = request.get_json(silent=True) or {}
    password = str(d.get("password", ""))
    if len(password) < 8:
        return jsonify({"error": "password_too_short"}), 400
    user = db.session.get(User, req.user_id)
    if not user:
        return jsonify({"error": "member_not_found"}), 404
    user.password_hash = generate_password_hash(password)
    req.status = "Résolu"
    req.resolved_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True})


@app.get("/api/driver/orders")
@driver_required
def driver_orders():
    name = session.get("driver")
    rows = Order.query.filter_by(driver=name).order_by(Order.id.desc()).all()
    return jsonify([o.as_dict() for o in rows if o.status not in ("Livré", "Annulé")])


@app.delete("/api/orders/<int:oid>")
@admin_required
def remove_order(oid):
    o = db.session.get(Order, oid)
    if not o:
        return jsonify({"error": "not_found"}), 404
    db.session.delete(o); db.session.commit()
    return jsonify({"ok": True})


@app.get("/api/members")
@admin_required
def members():
    users = User.query.order_by(User.id.desc()).all()
    result = []
    for user in users:
        user_orders = Order.query.filter_by(customer_id=user.id).all()
        delivered = [o for o in user_orders if o.status == "Livré"]
        result.append({
            "id": user.id,
            "full_name": user.full_name,
            "username": user.username,
            "phone": user.phone,
            "created_at": user.created_at.isoformat(timespec="seconds") if user.created_at else "",
            "orders_count": len(user_orders),
            "delivered_count": len(delivered),
            "orders_total": float(sum(float(o.total or 0) for o in user_orders)),
        })
    return jsonify(result)


@app.get("/api/admin/finance")
@admin_required
def admin_finance():
    period = request.args.get("period", "today")
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    if period == "week":
        start = today_start.fromordinal(today_start.toordinal() - today_start.weekday())
    elif period == "month":
        start = datetime(now.year, now.month, 1)
    else:
        period = "today"
        start = today_start

    rows = Order.query.filter(Order.created_at >= start).all()

    def total_for(method):
        method_rows = [o for o in rows if o.payment == method and o.status != "Annulé"]
        if method == "Cash":
            amount = sum(float(o.cash_received or 0) for o in method_rows)
        else:
            method_rows = [o for o in method_rows if o.payment_status == "Konfime"]
            amount = sum(float(o.paid_amount or 0) for o in method_rows)
        return {"count": len(method_rows), "amount": float(amount)}

    delivered = [o for o in rows if o.status == "Livré"]
    return jsonify({
        "period": period,
        "cash": total_for("Cash"),
        "moncash": total_for("MonCash"),
        "natcash": total_for("NatCash"),
        "orders_count": len([o for o in rows if o.status != "Annulé"]),
        "delivered_count": len(delivered),
        "sales_total": float(sum(float(o.total or 0) for o in delivered))
    })


@app.get("/api/admin/summary")
@admin_required
def admin_summary():
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    today_orders = Order.query.filter(Order.created_at >= today_start).all()
    active = [o for o in today_orders if o.status not in ("Livré", "Annulé")]
    delivered = [o for o in today_orders if o.status == "Livré"]
    def electronic(method):
        rows = [o for o in today_orders if o.payment == method and o.payment_status == "Konfime"]
        return {"count": len(rows), "amount": float(sum(float(o.paid_amount or 0) for o in rows))}
    return jsonify({
        "orders_today": len(today_orders),
        "active_today": len(active),
        "delivered_today": len(delivered),
        "delivered_revenue_today": float(sum(float(o.total or 0) for o in delivered)),
        "moncash": electronic("MonCash"),
        "natcash": electronic("NatCash"),
        "members_total": User.query.count(),
        "generated_at": now.isoformat(timespec="seconds")
    })


@app.get("/admin/export/orders.csv")
@admin_required
def export_orders_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["code","date","client","telephone","adresse","total","frais","paiement","montant_paye","transaction","statut_paiement","statut","livreur"])
    for o in Order.query.order_by(Order.id.desc()).all():
        writer.writerow([o.code, o.created_at.isoformat(timespec="seconds") if o.created_at else "", o.customer, o.phone, o.address, o.total, o.delivery_fee, o.payment, o.paid_amount, o.transaction_id, o.payment_status, o.status, o.driver])
    data = output.getvalue().encode("utf-8-sig")
    return Response(data, mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=promo_delivery_orders.csv"})


@app.get("/admin/export/members.csv")
@admin_required
def export_members_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id","nom","username","telephone","date_inscription","nombre_commandes","livrees","valeur_commandes"])
    for user in User.query.order_by(User.id.desc()).all():
        rows = Order.query.filter_by(customer_id=user.id).all()
        delivered = sum(1 for o in rows if o.status == "Livré")
        writer.writerow([user.id, user.full_name, user.username, user.phone, user.created_at.isoformat(timespec="seconds") if user.created_at else "", len(rows), delivered, sum(float(o.total or 0) for o in rows)])
    data = output.getvalue().encode("utf-8-sig")
    return Response(data, mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=promo_delivery_members.csv"})


@app.get("/admin/backup.json")
@admin_required
def admin_backup():
    payload = {
        "version": "Promo Delivery V15",
        "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
        "members": [{
            "id": u.id, "full_name": u.full_name, "phone": u.phone, "username": u.username,
            "created_at": u.created_at.isoformat(timespec="seconds") if u.created_at else ""
        } for u in User.query.order_by(User.id).all()],
        "products": [p.as_dict() for p in Product.query.order_by(Product.id).all()],
        "ads": [a.as_dict() for a in Ad.query.order_by(Ad.id).all()],
        "orders": [o.as_dict() for o in Order.query.order_by(Order.id).all()]
    }
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    return Response(data, mimetype="application/json", headers={"Content-Disposition": "attachment; filename=promo_delivery_backup_v15.json"})


@app.get("/api/stats")
@admin_required
def stats():
    result = {}
    rows = db.session.query(Order.status, db.func.count(Order.id), db.func.coalesce(db.func.sum(Order.total), 0)).group_by(Order.status).all()
    for status, count, total in rows:
        result[status] = {"count": count, "total": float(total or 0)}
    delivered = db.session.query(db.func.coalesce(db.func.sum(Order.total), 0)).filter(Order.status == "Livré").scalar()
    result["revenue_delivered"] = float(delivered or 0)
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    week_start = today_start.fromordinal(today_start.toordinal() - today_start.weekday())
    month_start = datetime(now.year, now.month, 1)
    result["members"] = User.query.count()
    result["members_today"] = User.query.filter(User.created_at >= today_start).count()
    result["members_week"] = User.query.filter(User.created_at >= week_start).count()
    result["members_month"] = User.query.filter(User.created_at >= month_start).count()
    return jsonify(result)


@app.post("/api/driver/orders/<int:order_id>/cash")
@driver_required
def driver_cash_received(order_id):
    o = db.session.get(Order, order_id)
    if not o or o.driver != session.get("driver"):
        return jsonify({"error": "forbidden"}), 403
    if o.payment != "Cash":
        return jsonify({"error": "cash_only"}), 400
    d = request.get_json(silent=True) or {}
    try:
        amount = float(d.get("amount", 0))
    except Exception:
        amount = 0
    if amount < 0:
        return jsonify({"error": "invalid_amount"}), 400
    o.cash_received = amount
    db.session.commit()
    return jsonify({"ok": True, "cash_received": amount})


@app.get("/api/driver/me-stats")
@driver_required
def driver_me_stats():
    name = session.get("driver")
    active = Order.query.filter(Order.driver == name, Order.status.notin_(("Livré", "Annulé"))).count()
    delivered = Order.query.filter_by(driver=name, status="Livré").count()
    delivered_total = db.session.query(db.func.coalesce(db.func.sum(Order.total), 0)).filter(
        Order.driver == name, Order.status == "Livré"
    ).scalar()
    cash_collected = db.session.query(db.func.coalesce(db.func.sum(Order.cash_received), 0)).filter(
        Order.driver == name, Order.payment == "Cash"
    ).scalar()
    return jsonify({
        "driver": name,
        "active": active,
        "delivered": delivered,
        "delivered_total": float(delivered_total or 0),
        "cash_collected": float(cash_collected or 0)
    })


@app.get("/api/driver-stats")
@admin_required
def driver_stats():
    result = []
    for driver in [d.name for d in DriverAccount.query.filter_by(active=True).order_by(DriverAccount.name.asc()).all()]:
        rows = Order.query.filter_by(driver=driver, status="Livré").all()
        result.append({"driver": driver, "count": len(rows), "total": sum(float(o.total or 0) for o in rows)})
    return jsonify(result)



def ensure_ad_columns():
    inspector = inspect(db.engine)
    if not inspector.has_table("ads"):
        return
    cols = {c["name"] for c in inspector.get_columns("ads")}
    if "image_data" not in cols:
        db.session.execute(text("ALTER TABLE ads ADD COLUMN image_data TEXT"))
        db.session.commit()


def ensure_order_columns():
    inspector = inspect(db.engine)
    if not inspector.has_table("orders"):
        return
    cols = {c["name"] for c in inspector.get_columns("orders")}
    wanted = {
        "customer_id":"INTEGER","transaction_id":"VARCHAR(120) DEFAULT ''",
        "paid_amount":"FLOAT DEFAULT 0","payment_status":"VARCHAR(50) DEFAULT 'Cash'",
        "cash_received":"FLOAT DEFAULT 0","accepted_at":"TIMESTAMP",
        "en_route_at":"TIMESTAMP","delivered_at":"TIMESTAMP"
    }
    changed=False
    for name, sql_type in wanted.items():
        if name not in cols:
            db.session.execute(text(f"ALTER TABLE orders ADD COLUMN {name} {sql_type}"))
            changed=True
    if changed:
        db.session.commit()


with app.app_context():
    db.create_all()
    ensure_order_columns()
    ensure_ad_columns()
    seed_products()
    seed_ads()
    seed_driver_accounts()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
