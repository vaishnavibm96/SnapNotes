from flask import Flask, request, jsonify
from flask_cors import CORS
from groq import Groq
from dotenv import load_dotenv
import base64
import os
import json
import sqlite3
from datetime import datetime

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

app = Flask(__name__)
CORS(app, origins=["http://127.0.0.1:5500", "http://localhost:5500"])

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Database setup
def init_db():
    conn = sqlite3.connect("notes.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            notes TEXT,
            tasks TEXT,
            reminders TEXT,
            points TEXT,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        if "image" not in request.files:
            return jsonify({"error": "No image uploaded"}), 400

        image_file = request.files["image"]
        filename = image_file.filename
        image_data = base64.b64encode(image_file.read()).decode("utf-8")
        mime_type = image_file.mimetype

        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_data}"
                            }
                        },
                        {
                            "type": "text",
                            "text": """Analyze this screenshot and extract the following in JSON format:
{
  "notes": ["key information or context from the screenshot"],
  "tasks": ["actionable items or things to do"],
  "reminders": ["time-sensitive items or deadlines"],
  "points": ["important highlights or takeaways"]
}
Only return valid JSON, nothing else."""
                        }
                    ]
                }
            ],
            max_tokens=1000
        )

        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        result = json.loads(raw)

        conn = sqlite3.connect("notes.db")
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO analyses (filename, notes, tasks, reminders, points, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            filename,
            json.dumps(result.get("notes", [])),
            json.dumps(result.get("tasks", [])),
            json.dumps(result.get("reminders", [])),
            json.dumps(result.get("points", [])),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        conn.close()

        return jsonify(result)

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"error": str(e)}), 500

@app.route("/history", methods=["GET"])
def history():
    try:
        conn = sqlite3.connect("notes.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM analyses ORDER BY created_at DESC LIMIT 10")
        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            results.append({
                "id": row[0],
                "filename": row[1],
                "notes": json.loads(row[2]),
                "tasks": json.loads(row[3]),
                "reminders": json.loads(row[4]),
                "points": json.loads(row[5]),
                "created_at": row[6]
            })

        return jsonify(results)

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"error": str(e)}), 500

@app.route("/delete/<int:id>", methods=["DELETE"])
def delete(id):
    try:
        conn = sqlite3.connect("notes.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM analyses WHERE id = ?", (id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)