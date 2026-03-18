## Engineering Evolution

**From a basic telemetry API to a structured and controlled backend system**

This project started as a minimal telemetry API — a simple Flask endpoint that accepted raw sensor data with minimal safeguards and direct database interaction. While functional for testing, the system lacked validation, observability, and protection mechanisms.

Through iterative improvements, the backend evolved into a more structured and reliable system by introducing core engineering practices commonly used in real-world applications.

### Key Evolution Highlights

| Stage               | What It Was                    | What It Became                                      | Engineering Benefit                     |
|---------------------|--------------------------------|-----------------------------------------------------|----------------------------------------|
| Initial Version     | Raw endpoint, no checks        | Input validation added (**implemented in `app.py`**) | Prevents invalid data & runtime errors |
| Observability       | No logging                     | Basic request and error logging (**in `app.py`**)   | Enables debugging and system visibility|
| Protection          | Unlimited requests             | Basic rate limiting (per IP) (**in `app.py`**)      | Reduces risk of API abuse              |
| Performance         | DB queried every time          | In-memory caching for latest telemetry (**in `app.py`**) | Faster responses, reduced DB load      |
| Architecture        | Logic concentrated in `app.py` | Separation using `database.py` and `config.py`      | Improved maintainability               |
| Database Layer      | Direct DB access in routes     | Dedicated database module (**in `database.py`**)    | Clear separation of concerns           |

### Why This Matters

These improvements introduce fundamental backend engineering principles:

- Input validation ensures only valid data is processed
- Logging provides visibility into system behavior
- Rate limiting protects system resources
- Caching improves response efficiency
- Modular structure improves maintainability

**Together, these changes transform the API from a passive data receiver into a controlled system that actively enforces data integrity, monitors behavior, and manages resource usage.**

The result is no longer just a basic API prototype, but a **controlled and structured backend system** that reflects production-oriented design principles in a simplified implementation.

This demonstrates a key engineering approach: starting simple and progressively adding control, visibility, and structure.

---

## Before vs After

### Before (Initial Version)
- Basic POST `/telemetry` endpoint
- No validation of incoming data
- No logging
- No rate limiting
- Direct database writes inside route logic
- Inconsistent or minimal response structure

### After (Improved Version)
- Input validation added to prevent invalid telemetry data (**in `app.py`**)
- Logging implemented for requests and error tracking (**in `app.py`**)
- Basic rate limiting applied to reduce abuse (**in `app.py`**)
- Introduction of simple in-memory caching for latest telemetry (**in `app.py`**)
- Database logic separated into `database.py`
- Consistent JSON response structure across endpoints

This transformation demonstrates the application of core backend engineering practices, **improving reliability, enforcing control over data flow, and introducing visibility into system behavior**.

## Technical Improvements

### Caching

A simple in-memory caching mechanism was implemented to store the most recent telemetry record.

Instead of querying the database for every request, the system stores the latest telemetry data in a temporary variable. This allows instant retrieval for the `/telemetry/latest` endpoint without hitting SQLite.

**Location:**  
Implemented in `app.py` as a global variable (`latest_telemetry`) that is updated on every successful POST request.

**Note:** This cache reflects the most recent in-memory state and is updated on each new telemetry submission.

**Problem it solves:**  
- Reduces unnecessary database queries  
- Improves response time for `/telemetry/latest`  
- Lowers overall system load in high-frequency scenarios

### Logging

A logging mechanism was introduced to track system activity and errors during execution.

The application logs incoming telemetry requests, validation failures, and any runtime errors using Python’s built-in logging module.

**Location:**  
Implemented in `app.py` using `import logging` and `logging.basicConfig`, with `logging.info()` and `logging.error()` calls inside the endpoints.

**Problem it solves:**  
- Enables debugging and error tracing without guessing what happened  
- Provides a basic trace of API activity during execution  
- Makes it possible to diagnose issues in production-like conditions

### Rate Limiting

A basic rate limiting mechanism was implemented to control how frequently clients can access the API.

The system tracks the timestamp of the last request per client IP address and rejects requests that arrive too quickly (returning HTTP 429).

**Location:**  
Implemented in `app.py` with a dictionary (`last_request_time`) and a helper function that checks timing before processing any endpoint.

**Problem it solves:**  
- Prevents excessive or abusive API usage (rapid repeated requests)  
- Protects system resources from overload  
- Ensures fair access for legitimate users

### Database Layer

A dedicated database module was implemented to handle all data-related operations separately from the API logic.

The database layer manages SQLite connections and provides clean functions for inserting and retrieving telemetry records, keeping all SQL and cursor logic isolated.

**Location:**  
Fully contained in `database.py` (with functions like `insert_telemetry()` and `get_latest_telemetry()`), imported and used by `app.py`.

**Problem it solves:**  
- Separates concerns between API routing and data handling  
- Encapsulates SQLite connection and query execution in reusable functions  
- Improves code organization and maintainability