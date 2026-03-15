# Space Dogs Telemetry API Documentation

## 1. API Purpose (Purpose of the API)

The **Space Dogs Telemetry API** was created to simulate satellite telemetry data in a simple and accessible way using Python and Flask. The main objective of this API is to provide a controlled environment where developers can test applications that process telemetry data without requiring access to real satellite systems or specialized hardware.

Telemetry systems are essential in aerospace and space missions because they allow engineers to monitor the health and performance of spacecraft in real time. These systems collect operational data from onboard sensors and transmit it to ground stations for analysis.

This API reproduces that concept by generating simulated telemetry values such as temperature, battery level, signal strength, timestamps, and subsystem status. These variables represent typical parameters that would be monitored in a satellite or remote spacecraft system.

By using simulated telemetry, developers can safely experiment with:

* telemetry monitoring systems
* backend data processing pipelines
* real-time dashboards
* cloud-based analytics tools
* educational demonstrations of telemetry concepts

The API therefore serves as a **learning tool, development platform, and testing environment** for projects related to space technology and data monitoring.

---

## 2. Endpoint Description (Endpoint Overview)

**HTTP Method:** GET
**Endpoint:** `/telemetry`

The `/telemetry` endpoint is responsible for generating and returning simulated telemetry data in **JSON format**.

Each time the endpoint is accessed, the API produces a new set of randomized values that represent the current status of a simulated spacecraft system. These values are generated within predefined ranges to maintain realistic telemetry behavior.

The endpoint includes the following telemetry parameters:

**Temperature**
Represents the internal temperature of a spacecraft subsystem. Temperature monitoring is important to ensure that electronic components operate within safe limits.

**Battery Level**
Simulates the percentage of battery charge available in the spacecraft’s power system. Monitoring battery levels is critical for maintaining mission operations.

**Signal Strength**
Represents the strength of the communication signal between the spacecraft and the ground station. Strong signal strength indicates stable communication.

**Timestamp**
Records the exact time when the telemetry data was generated using UTC format. This allows systems to track when each data sample was produced.

**Subsystem Status**
Indicates the operational condition of a spacecraft subsystem. In the current version of the API, the value is set to `”nominal”` to represent normal operation.

The endpoint is designed to be simple but flexible, allowing it to be easily integrated with visualization tools, monitoring platforms, or other backend services.

## 3. Example Response (Sample JSON Output)

Below is an example of the JSON response returned by the `/telemetry` endpoint:

```json
{
  “temperature”: 26.74,
  “battery_level”: 88,
  “signal_strength”: 92,
  “timestamp”: “2026-03-14T22:18:34.245631”,
  “subsystem_status”: “nominal”
}
```

### Response Field Explanation

**temperature**
A floating-point number representing the spacecraft temperature in degrees Celsius.

**battery_level**
An integer representing the battery charge percentage (0–100).

**signal_strength**
An integer value indicating communication signal quality, expressed as a percentage.

**timestamp**
An ISO 8601 formatted timestamp showing when the telemetry data was generated.

**subsystem_status**
A string indicating the current operational state of the spacecraft subsystem.


## 4. Use Cases (Applications and Use Cases)

The **Space Dogs Telemetry API** can be used in several practical scenarios related to software development, data analysis, and educational demonstrations.

### Hackathon Telemetry Simulation

During hackathons or rapid prototyping events, teams often need data sources to test their systems. This API provides a simulated telemetry stream that allows developers to quickly build and test applications without relying on external data sources.

### Monitoring Dashboards

Developers can connect the API to visualization tools or web dashboards to display telemetry information in real time. For example, charts could be created to monitor temperature trends, battery levels, or signal stability over time.

### Data Pipeline Experiments

The API can also serve as a data generator for testing data pipelines in cloud environments. The telemetry data could be streamed into databases, analytics platforms, or machine learning systems for experimentation.

### Educational Demonstrations

Because the system is simple and easy to understand, it can be used to demonstrate how telemetry systems work in space missions. Students and developers can observe how telemetry data is generated, transmitted, and processed.

### Backend Integration Testing

Developers building larger systems can use the API to test integrations with:

* cloud services
* databases
* real-time monitoring tools
* distributed systems

Without needing access to real satellite telemetry data.

