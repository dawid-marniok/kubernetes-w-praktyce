import os
import socket
import time

from flask import Flask, jsonify, request
from sqlalchemy import Boolean, Column, Float, Integer, String, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker

app = Flask(__name__)

# Konfiguracja tylko ze zmiennej środowiskowej (ustawiana w compose.yaml)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://shop:changeme-postgres@db:5432/shoppingdb")
HOSTNAME = socket.gethostname()  # w kontenerze = ID kontenera

Base = declarative_base()


class ShoppingItem(Base):
    __tablename__ = "shopping_items"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    quantity = Column(Float, default=1.0)
    unit = Column(String(20), default="szt.")
    bought = Column(Boolean, default=False)
    price = Column(Float, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "quantity": self.quantity,
            "unit": self.unit,
            "bought": self.bought,
            "price": self.price,
        }


def init_db(max_retries=10, retry_interval=3):
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    for attempt in range(1, max_retries + 1):
        try:
            Base.metadata.create_all(engine)  # tworzy tabelę, jeśli jej nie ma
            return engine
        except OperationalError:
            if attempt == max_retries:
                raise
            print(f"Baza niedostępna, próba {attempt}/{max_retries}, czekam {retry_interval} s...", flush=True)
            time.sleep(retry_interval)


engine = init_db()
Session = sessionmaker(bind=engine)


@app.after_request
def add_served_by(resp):
    # Nagłówek z nazwą kontenera, który obsłużył żądanie
    resp.headers["X-Served-By"] = HOSTNAME
    return resp


@app.get("/whoami")
def whoami():
    # Do demo skalowania: który kontener (replika) odpowiedział
    return f"{HOSTNAME}\n", 200, {"Content-Type": "text/plain"}


@app.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return jsonify(status="ok", host=HOSTNAME)
    except OperationalError:
        return jsonify(status="db-unavailable", host=HOSTNAME), 503


@app.get("/items")
def get_items():
    with Session() as session:
        return jsonify([i.to_dict() for i in session.query(ShoppingItem).order_by(ShoppingItem.id)])


@app.post("/items")
def create_item():
    data = request.get_json()
    with Session() as session:
        item = ShoppingItem(
            name=data["name"],
            quantity=data.get("quantity", 1.0),
            unit=data.get("unit", "szt."),
            price=data.get("price"),
        )
        session.add(item)
        session.commit()
        return jsonify(item.to_dict()), 201


@app.put("/items/<int:item_id>")
def update_item(item_id):
    data = request.get_json()
    with Session() as session:
        item = session.get(ShoppingItem, item_id)
        if not item:
            return jsonify(error="Item not found"), 404
        for field in ("name", "quantity", "unit", "bought", "price"):
            if field in data:
                setattr(item, field, data[field])
        session.commit()
        return jsonify(item.to_dict())


@app.delete("/items/<int:item_id>")
def delete_item(item_id):
    with Session() as session:
        item = session.get(ShoppingItem, item_id)
        if not item:
            return jsonify(error="Item not found"), 404
        session.delete(item)
        session.commit()
        return "", 204


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
