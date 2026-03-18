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