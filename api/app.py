from flask import Flask, jsonify
import random
import datetime

# Create the Flask application
app = Flask(__name__)

# Root route to confirm the API is running
@app.route("/")
def home():
    return "Space Dogs Telemetry API is running"

# Telemetry endpoint
@app.route("/telemetry")
def telemetry():

    data = {
        "temperature": round(random.uniform(15, 40), 2),
        "battery_level": random.randint(60, 100),
        "signal_strength": random.randint(70, 100),
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "subsystem_status": "nominal"
    }

    return jsonify(data)

# Run the Flask development server
if __name__ == "__main__":
    app.run(debug=True)
