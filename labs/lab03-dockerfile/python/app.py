import os

from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/")
def hello():
    name = os.getenv("APP_NAME", "Docker App")
    version = os.getenv("APP_VERSION", "nieznana")
    return f"Hello z {name}, wersja {version}!\n"


@app.route("/whoami")
def whoami():
    # USER w Dockerfile nie ustawia zmiennej $USER, dlatego patrzymy na uid/gid procesu
    return jsonify(uid=os.getuid(), gid=os.getgid(), env_USER=os.getenv("USER", "(brak)"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
