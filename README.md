*Repository for the Space Dogs Cloud Telemetry API* — developed during *Global Hack Week: Cloud*.

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)
![GitHub Copilot](https://img.shields.io/badge/Powered%20by%20Copilot-000000?style=for-the-badge&logo=githubcopilot)
![MLH](https://img.shields.io/badge/MLH-Participation-FF6B6B?style=for-the-badge)
![Visual Studio Code](https://img.shields.io/badge/Visual%20Studio%20Code-007ACC?style=for-the-badge&logo=visualstudiocode&logoColor=white)
![Google Chrome](https://img.shields.io/badge/Google%20Chrome-4285F4?style=for-the-badge&logo=googlechrome&logoColor=white)
![HTML](https://img.shields.io/badge/HTML-E34F26?style=for-the-badge&logo=html5&logoColor=white)
![CSS](https://img.shields.io/badge/CSS-1572B6?style=for-the-badge&logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)
![Global Hack Week](https://img.shields.io/badge/Global%20Hack%20Week-Cloud-00BFFF?style=for-the-badge)
![Space Dogs Logo 1](https://raw.githubusercontent.com/akabyn5/space-dogs-ghw-cloud/main/docs/images/space%20dogs1.png)
![Space Dogs Logo 2](https://raw.githubusercontent.com/akabyn5/space-dogs-ghw-cloud/main/docs/images/ChatGPT%20Image%2016%20feb%202026%2C%2010_13_02%20p.m..png)

A clean, realistic cloud-based system that simulates the generation, transmission, and consumption of *spacecraft telemetry data*. Includes a powerful Python/Flask backend REST API, a beautiful static web interface, and complete technical documentation.

![Space Dogs Mission Control Dashboard](https://github.com/akabyn5/space-dogs-ghw-cloud/blob/main/docs/ADzIy.jpg)

---

### 🌌 *Space Dogs Cloud Telemetry API*

*Imagine being able to monitor a spacecraft from your laptop.*

That’s exactly what *Space Dogs Cloud Telemetry API* is all about: a clean, functional, and realistic cloud-based system that simulates the generation, transmission, and consumption of *spacecraft telemetry data*.

---
![Logo](https://github.com/akabyn5/space-dogs-ghw-cloud/blob/main/docs/images/Logo.jpg)
### ✨ What is it and how does it work?

It’s a modern backend built with *Python and Flask* that exposes a simple yet powerful REST endpoint: /telemetry.

Every time you call it, the API dynamically generates realistic telemetry data from a spacecraft, including:

- System temperature  
- Battery level  
- Signal strength  
- Overall system status  

All delivered in clean *JSON* format, ready to be consumed by a web frontend, dashboards, analytics tools, or even AI agents.

---

![bestpractice](https://github.com/akabyn5/space-dogs-ghw-cloud/blob/main/docs/images/description.jpeg)
![bestpractice02](https://github.com/akabyn5/space-dogs-ghw-cloud/blob/main/docs/images/description%2002.jpeg)
### 🛠️ Technology & Best Practices

This project isn’t just a toy example — it’s built with care and professionalism:

- Version control with *GitHub*  
- Clean dependency management using requirements.txt  
- Input validation for robustness  
- A simple yet representative architecture of modern distributed systems  

It strikes the perfect balance between educational simplicity and real-world quality.

---
![dashboardtelemetry](https://github.com/akabyn5/space-dogs-ghw-cloud/blob/main/docs/images/dashboard%20telemetry%20api.jpeg)

### 🎯 Why does this project exist?

*Space Dogs* was created as a practical and engaging educational initiative for hackathons like *Global Hack Week*, cybersecurity challenges, and cloud computing projects.

Instead of abstract exercises, it immerses you in a realistic use case: *aerospace telemetry*.

Participants get to experience firsthand how critical systems collect, process, and analyze real-time data. Along the way, they develop valuable skills in:

- Backend development  
- Cloud infrastructure  
- Real-time data analysis  
- Anomaly detection  
- Collaborative teamwork and technical documentation  

---

### 🚀 In essence...

This system simulates the *nervous system* of a space mission.  

Even though the data is synthetic, the entire flow mirrors real-world scenarios: continuous telemetry generation, secure API exposure, optional database storage, and intelligent analysis to detect critical conditions before they become problems.

It’s a practical, accessible gateway into how monitoring systems work in high-stakes environments — adapted for learning and hands-on experimentation.

---

*Ready for launch?*  

*Space Dogs Cloud Telemetry API* is waiting for you to build, experiment, and dream big. 🌠

Because learning by doing is infinitely more exciting when it feels like a real space mission. ✨

---

### 📸 Mission Control Dashboard

![Space Dogs Mission Control Dashboard](https://github.com/akabyn5/space-dogs-ghw-cloud/blob/main/docs/images/dashboard%20README.jpeg)

Beautiful real-time web interface included in the repository

---
![dashboard01](https://github.com/akabyn5/space-dogs-ghw-cloud/blob/main/docs/images/system%20architecture.jpeg)
# 🛰 Space Dogs — Telemetry Dashboard


A real-time telemetry monitoring system built as a Chrome extension connected to a local Flask REST API. Space Dogs demonstrates a full-stack cloud-adjacent architecture: a Python backend that simulates spacecraft sensor data, persists it to a database, and exposes it through a versioned REST API — consumed live by a browser extension that renders the data as a responsive, animated dashboard.

---

## 🧩 Chrome Extension

The Space Dogs extension lives in your browser toolbar and gives you an instant, always-current view of telemetry readings without ever opening a new tab. It was built entirely without third-party UI libraries: the dashboard layout uses CSS Grid, the temperature trend graph is hand-drawn SVG with coordinate math computed in JavaScript, and the animations are pure CSS keyframes. The result is a sub-50KB extension that loads in milliseconds.

### Interface at a glance

The popup is divided into two panels. The upper panel is a history table showing the five most recent telemetry readings in a scannable grid — each row displays a timestamp, temperature, battery level, signal strength, and system status. Values are colour-coded by severity in real time: green for nominal, amber for warning, red for critical. The lower panel is a temperature trend chart rendered as inline SVG, with a gradient fill beneath the line, a soft glow filter on the stroke, and dynamic Y-axis scaling that always keeps the data visually centred regardless of the temperature range.

### Smart polling architecture

Rather than naively fetching on a fixed interval, the extension implements four distinct optimisations that together reduce network usage by roughly 80% compared to a simple polling loop.

**POST throttling** decouples the write cadence from the read cadence. The extension reads new data every 5 seconds but only asks the server to generate a new reading every 30 seconds — a 6× reduction in server writes with no perceptible loss of freshness.

**Session caching** means the popup feels instant on every open. After each successful fetch, the records are persisted to `localStorage` with a timestamp. The next time the popup opens, the cached data is painted immediately while a fresh fetch runs silently in the background. The user never sees a loading spinner after the first open.

**ID-based render diffing** prevents unnecessary DOM work. Before re-rendering, the extension compares the incoming newest record's database ID against what's already on screen. If they match, the data hasn't changed — the full SVG chart and history table rebuild is skipped entirely, and only the footer timestamp updates.

**Exponential backoff** handles server downtime gracefully. After consecutive failures, the retry interval doubles: 5 s → 10 s → 20 s → 40 s → 60 s (capped). This prevents the extension from hammering a temporarily offline server and draining battery on a doomed retry loop.

---

![dashboard2](https://github.com/akabyn5/space-dogs-ghw-cloud/blob/main/docs/images/system%20architecture%20'2.jpeg)
## ⚙️ Telemetry API

The backend is a Flask REST API (`app.py`) that owns the full data lifecycle: simulating sensor readings, persisting them to SQLite, serving them through a versioned endpoint contract, and caching expensive queries in memory.

### How the extension and API connect

```
Chrome Extension (popup.js)
        │
        │  POST /telemetry          — generate a new sensor reading (every 30 s)
        │  GET  /telemetry/history  — fetch the 5 most recent records (every 5 s)
        ▼
Flask REST API (app.py · localhost:5000)
        │
        ├── In-memory TTL cache     — serves /stats and /latest with zero DB queries
        ├── Rate limiter            — 60 requests/minute per IP (non-loopback)
        └── SQLite database         — persists all telemetry records
```

Every response follows a unified contract — `{ "success": bool, "data": ... }` — so the extension never needs to special-case endpoint shapes. HTTP errors are returned as structured JSON with both a human-readable `error` string and an appropriate status code, making error handling on the client straightforward.

### Key API endpoints

`POST /telemetry` generates one telemetry reading and saves it. All fields are optional — any field omitted is simulated with values consistent with the randomly chosen system status (nominal readings cluster around healthy ranges; critical readings simulate degraded sensors). The server validates all provided values, rejects non-JSON bodies with `415 Unsupported Media Type`, and invalidates both in-memory caches on every write.

`GET /telemetry/history` returns paginated records sorted newest-first. The extension requests `?limit=5&page=1` on every poll, feeding the same response array to both the history table and the temperature chart — zero additional network requests needed.

`GET /telemetry/latest` returns the single most recent record with a two-level cache: an in-memory TTL cache is checked first (zero DB queries on a hit), then the database. The cache is eagerly invalidated on every write so it never returns stale data regardless of TTL time remaining.

`GET /telemetry/stats`, `GET /telemetry/anomalies`, `GET /telemetry/search`, `GET /telemetry/export.csv`, and `DELETE /telemetry/old` round out the API for analytics, filtering, data export, and housekeeping.

---

## ✨ Feature Highlights

**Real-time sensor simulation** generates temperature, battery level, and signal strength values with weighted probabilities — 90% nominal, 7% warning, 3% critical — so the dashboard behaves like a live system rather than a static demo.

**Severity-aware visualisation** colours every value independently. A reading can have a nominal temperature but a critical battery level; each cell reflects its own state, not the aggregate system status.

**SVG temperature trend chart** with no dependencies. The chart is built from first principles: two linear mapping functions (`xAt` and `yAt`) translate data coordinates into SVG pixel coordinates, with a flipped Y axis (SVG's origin is top-left), a minimum 15° spread enforced to keep flat lines visible, and a gradient fill computed from the severity colour of the most recent data point.

**Graceful degradation** at every layer. The API returns structured error JSON instead of HTML stack traces. The extension distinguishes network failures (server offline) from data errors (server responded but returned no records) and renders contextually accurate error panels with a one-click retry button.

**Manifest V3 compliant** with minimal permissions. The extension requests only `host_permissions` for `http://127.0.0.1:5000/*` — no broad host access, no `tabs`, no `scripting`, no `storage` permission. The Content Security Policy is declared explicitly in the manifest rather than relying on browser defaults.

---

## 🚀 Installation

### Prerequisites

Before you begin, make sure you have Python 3.10 or later and Google Chrome installed.

### 1 · Clone the repository

```bash
git clone https://github.com/your-username/space-dogs-ghw-cloud.git
cd space-dogs-ghw-cloud
```

### 2 · Start the Flask API

```bash
# Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
.venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Start the server
python app.py
```

The API will start on `http://127.0.0.1:5000`. You should see a startup log line confirming the port, debug mode, and rate limit. Visit `http://127.0.0.1:5000/` in your browser to confirm it's running — you'll see the endpoint map.

### 3 · Generate extension icons

The manifest references PNG icons in an `icons/` folder. Run this script once to generate them:

```bash
cd extension
pip install Pillow
python make_icons.py
```

This creates `icons/icon16.png`, `icon32.png`, `icon48.png`, and `icon128.png` — simple dark circles with a cyan border, consistent with the dashboard aesthetic.

### 4 · Load the extension in Chrome

Open Chrome and navigate to `chrome://extensions`. Enable **Developer mode** using the toggle in the top-right corner. Click **Load unpacked** and select the `extension/` folder from the cloned repository. The Space Dogs icon will appear in your toolbar. Click it — the dashboard will open, connect to the local API, and begin displaying live telemetry data.

### 5 · Verify the connection

The footer of the popup shows a blinking green dot and a timestamp when the extension is successfully connected. If you see a red dot and an "API Connection Lost" message, confirm that the Flask server is running on port 5000 and that no firewall is blocking loopback connections.

---

## 🗂 Project Structure

```
space-dogs-ghw-cloud/
├── app.py              # Flask REST API — routing, caching, rate limiting
├── database.py         # SQLite persistence layer
├── config.py           # Environment-driven configuration
├── requirements.txt
├── make_icons.py       # One-time icon generator script
└── extension/
    ├── manifest.json   # Chrome Extension Manifest V3
    ├── popup.html      # Extension popup shell
    ├── popup.js        # All extension logic — API, rendering, caching, chart
    ├── styles.css      # Dashboard styles
    └── icons/          # Generated by make_icons.py
        ├── icon16.png
        ├── icon32.png
        ├── icon48.png
        └── icon128.png
```

---

## 🛠 Built With

The backend uses **Python 3** with **Flask** for routing and **SQLite** for persistence — no ORM, no migrations, no infrastructure beyond a single process and a file. The frontend is vanilla **JavaScript (ES2022)** organised into a layered module architecture (classifiers, formatters, API, renderer, UI, controller), with layout in **CSS Grid** and data visualisation in hand-authored **SVG**. No npm, no bundler, no build step.

---

![logo02](https://github.com/akabyn5/space-dogs-ghw-cloud/blob/main/docs/images/Logo%2002.jpeg)

*Space Dogs · Global Hack Week: Cloud · March 2026*


Made with ❤️ during *Global Hack Week: Cloud 2026*

*Technologies:* Python • Flask • SQLite • HTML/CSS/JS

---

⭐ *Star the repo* if you're ready to launch your own space mission!
