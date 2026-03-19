### 🌌 **Space Dogs Telemetry API Documentation**

**Your friendly guide to monitoring a spacecraft from the comfort of your code.** 🚀

---

### 1. Why This API Exists

The **Space Dogs Telemetry API** was built to make space telemetry fun, accessible, and safe to experiment with.

Using simple **Python + Flask**, it simulates real satellite and spacecraft telemetry data without needing expensive hardware or actual satellites.  

In real space missions, telemetry systems constantly monitor vital signs — temperature, power, communication links — and send that information back to Earth for analysis.  

This API recreates that exact experience in a controlled environment. Every time you call it, you get fresh, realistic values for:

- **Temperature** (how hot the systems are running)  
- **Battery Level** (remaining power)  
- **Signal Strength** (how well it’s talking to ground control)  
- **Timestamp**  
- **Subsystem Status**

It’s the perfect sandbox for developers, students, and hackers who want to build monitoring tools, dashboards, or data pipelines without any risk.

Whether you’re learning, prototyping, or competing in a hackathon, this API gives you a realistic telemetry stream to play with.

---

### 2. Main Endpoint: `/telemetry`

**Method:** `GET`  
**Path:** `/telemetry`

This is the heart of the API.  

Every time you visit this endpoint, it instantly generates and returns a brand-new set of simulated telemetry data in clean **JSON** format.

#### What you’ll receive:

- **temperature**: Current temperature in °C (float)  
- **battery_level**: Battery percentage (0–100, integer)  
- **signal_strength**: Signal quality percentage (integer)  
- **timestamp**: Exact UTC time when the data was generated  
- **subsystem_status**: Current state — currently always `"nominal"`

The values are randomized within realistic ranges, so each request feels alive and dynamic.

---

### 3. Example Response

Here’s what a typical call looks like:

```json
{
  "temperature": 26.74,
  "battery_level": 88,
  "signal_strength": 92,
  "timestamp": "2026-03-14T22:18:34.245631",
  "subsystem_status": "nominal"
}

