from flask import Flask, jsonify
from battery_monitor import calculer_batterie

app = Flask(__name__)

@app.route("/battery", methods=["GET"])
def battery():
    data = calculer_batterie()
    return jsonify(data)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "battery_api"})

if __name__ == "__main__":
    # 0.0.0.0 pour autoriser aussi l'accès depuis le navigateur du Raspberry
    app.run(host="0.0.0.0", port=5000, debug=False)