from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os, json

app = Flask(__name__)

database_url = os.getenv("DATABASE_URL", "").strip()
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
if not database_url:
    database_url = "sqlite:///promo_delivery.db"

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True, "pool_recycle": 300}
db = SQLAlchemy(app)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255), default="")
    price = db.Column(db.Float, default=0)
    icon = db.Column(db.String(20), default="📦")
    active = db.Column(db.Boolean, default=True)

    def as_dict(self):
        return {"id":self.id,"name":self.name,"category":self.category,
                "description":self.description or "","price":self.price or 0,
                "icon":self.icon or "📦","active":bool(self.active)}

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False, index=True)
    customer = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(60), nullable=False)
    address = db.Column(db.Text, nullable=False)
    landmark = db.Column(db.String(255), default="")
    zone = db.Column(db.String(255), default="")
    payment = db.Column(db.String(50), default="Cash")
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
            "id":self.id,"code":self.code,"customer":self.customer,"phone":self.phone,
            "address":self.address,"landmark":self.landmark or "","zone":self.zone or "",
            "payment":self.payment or "Cash","order_type":self.order_type or "Livraison",
            "note":self.note or "","items":json.loads(self.items_json or "[]"),
            "subtotal":self.subtotal or 0,"delivery_fee":self.delivery_fee or 0,
            "total":self.total or 0,"status":self.status or "Nouveau",
            "driver":self.driver or "",
            "created_at":self.created_at.isoformat(timespec="seconds") if self.created_at else ""
        }

def seed_products():
    if Product.query.count():
        return
    items = [
        ("Pain","pain","Pain fre",75,"🥖"),("Sucre","sucre","Sachet / kantite",150,"🍚"),
        ("Dlo","eau","Bouteille oswa gallon",100,"💧"),("Plat du jour","food","Manje pare",500,"🍛"),
        ("Gaz propane","gas","Pri baz — selon kantite",750,"🔥"),("Taxi","taxi","Pri sou demann selon trajè",0,"🚕"),
        ("Ti komisyon","other","Ekri sa w bezwen",0,"🛍️"),("Livraison dokiman","other","Dokiman oswa ti pakè",250,"📄"),
        ("Fè mache","other","Nou fè ti acha pou ou",0,"🧺")
    ]
    for n,c,d,p,i in items:
        db.session.add(Product(name=n,category=c,description=d,price=p,icon=i))
    db.session.commit()

@app.route("/")
def client(): return render_template("index.html", page="client")

@app.route("/admin")
def admin(): return render_template("index.html", page="admin")

@app.route("/driver")
def driver(): return render_template("index.html", page="driver")

@app.route("/health")
def health(): return {"ok":True,"service":"Promo Delivery"}

@app.get("/api/products")
def products():
    return jsonify([p.as_dict() for p in Product.query.filter_by(active=True).order_by(Product.id).all()])

@app.post("/api/products")
def add_product():
    d=request.get_json(silent=True) or {}
    name=str(d.get("name","")).strip()
    if not name: return jsonify({"error":"name_required"}),400
    p=Product(name=name,category=str(d.get("category","other")),
              description=str(d.get("description","Ajoute pa Admin")),
              price=float(d.get("price",0) or 0),icon=str(d.get("icon","📦")) or "📦")
    db.session.add(p); db.session.commit()
    return jsonify({"ok":True,"id":p.id})

@app.delete("/api/products/<int:pid>")
def remove_product(pid):
    p=db.session.get(Product,pid)
    if not p: return jsonify({"error":"not_found"}),404
    p.active=False; db.session.commit()
    return jsonify({"ok":True})

@app.get("/api/orders")
def orders():
    return jsonify([o.as_dict() for o in Order.query.order_by(Order.id.desc()).all()])

@app.get("/api/orders/<code>")
def order_by_code(code):
    o=Order.query.filter(db.func.upper(Order.code)==code.upper()).first()
    return jsonify(o.as_dict()) if o else (jsonify({"error":"not_found"}),404)

@app.post("/api/orders")
def create_order():
    d=request.get_json(silent=True) or {}
    items=d.get("items",[])
    customer=str(d.get("customer","")).strip()
    phone=str(d.get("phone","")).strip()
    address=str(d.get("address","")).strip()
    if not items or not customer or not phone or not address:
        return jsonify({"error":"missing_fields"}),400
    subtotal=sum(float(i.get("price",0) or 0)*int(i.get("qty",1) or 1) for i in items)
    fee=float(d.get("delivery_fee",0) or 0)
    now=datetime.utcnow()
    code="PD-"+now.strftime("%y%m%d%H%M%S%f")[-12:]
    o=Order(code=code,customer=customer,phone=phone,address=address,
            landmark=str(d.get("landmark","")).strip(),zone=str(d.get("zone","")),
            payment=str(d.get("payment","Cash")),order_type=str(d.get("order_type","Livraison")),
            note=str(d.get("note","")).strip(),items_json=json.dumps(items,ensure_ascii=False),
            subtotal=subtotal,delivery_fee=fee,total=subtotal+fee,status="Nouveau",driver="",created_at=now)
    db.session.add(o); db.session.commit()
    return jsonify({"ok":True,"code":code,"total":o.total})

@app.patch("/api/orders/<int:oid>")
def patch_order(oid):
    o=db.session.get(Order,oid)
    if not o: return jsonify({"error":"not_found"}),404
    d=request.get_json(silent=True) or {}
    if "status" in d: o.status=str(d["status"])
    if "driver" in d: o.driver=str(d["driver"])
    db.session.commit()
    return jsonify({"ok":True})

@app.delete("/api/orders/<int:oid>")
def remove_order(oid):
    o=db.session.get(Order,oid)
    if not o: return jsonify({"error":"not_found"}),404
    db.session.delete(o); db.session.commit()
    return jsonify({"ok":True})

@app.get("/api/stats")
def stats():
    result={}
    rows=db.session.query(Order.status,db.func.count(Order.id),db.func.coalesce(db.func.sum(Order.total),0)).group_by(Order.status).all()
    for status,count,total in rows:
        result[status]={"count":count,"total":float(total or 0)}
    delivered=db.session.query(db.func.coalesce(db.func.sum(Order.total),0)).filter(Order.status=="Livré").scalar()
    result["revenue_delivered"]=float(delivered or 0)
    return jsonify(result)

with app.app_context():
    db.create_all()
    seed_products()

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT","5000")),debug=False)
