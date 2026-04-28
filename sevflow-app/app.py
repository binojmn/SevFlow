from flask import Flask, jsonify
import os

app = Flask(__name__)


@app.get("/")
def home():
    return jsonify(
        {
            "name": "sevflow-app",
            "status": "ok",
            "message": "Welcome to the SevFlow microservice -14",
            "version": os.getenv("APP_VERSION", "1.0.0"),
            "environment": os.getenv("APP_ENV", "dev"),
        }
    )


@app.get("/health")
def health():
    return jsonify({"status": "healthy"}), 200


@app.get("/api/severity")
def severity():
    return jsonify(
        {
            "service": "sevflow-app",
            "severityLevels": ["critical", "high", "medium", "low"],
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
