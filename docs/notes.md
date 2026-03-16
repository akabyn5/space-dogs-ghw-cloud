
viernes 13 de marzo
# Project Notes

This document will track development notes, challenge progress,
and documentation for the Global Hack Week Cloud project.
# Development Decisions

In our action plan, we established the operational strategy for participating in Global Hack Week: Cloud. Our purpose is to guide the actions of the International Projects team during the event, prioritize the most relevant technical challenges, and ensure that our participation produces concrete learning outcomes aligned with the long-term technological objectives of Space Dogs.

Our strategy is not to complete every available challenge, but rather to focus on those that directly contribute to the development of skills in cloud infrastructure, collaborative software development, and basic distributed systems implementation.

## Priority Level A: High Priority

These challenges directly contribute to the development of cloud architecture and application deployment capabilities.

### 1. Create and deploy a simple REST API

This challenge consists of building a web service using a framework such as Flask  or FastAPI and deploying it on a cloud platform. It represents the main technical objective of the week.

### 2. Set up a static website with Vultr

This challenge introduces cloud storage and static website hosting.

### 3. Deploy a managed database on Vultr

This challenge teaches the process of creating and connecting to a managed database service in a cloud environment.

Together, these three tasks form a complete cloud system architecture consisting of:

*Frontend (static website) → Backend API → Cloud database*

## Priority Level B: Development Workflow Skills

These challenges focus on collaborative development practices using GitHub.

### 4. Introduction to GitHub

### 5. Coding with Codespaces

### 6. Introduction to repository management

These exercises are relatively short, but essential for establishing a proper project structure and sound version control practices.

## Priority Level C: AI and Development Productivity

These challenges introduce AI-assisted coding workflows.

### 7. Getting started with Copilot

### 8. Using GitHub Copilot to build a simple application

These steps are optional, but recommended if time allows.

## Priority Level D: Optional Technical Exploration

The Gaffa browser automation challenges provide experience with API-based automation systems. These tasks are optional and should only be attempted if the main objectives have already been completed.

## Priority Level E: Social Participation Challenges

These activities provide extra points, but do not require significant development effort.

Examples include:

* Creating a short video about Global Hack Week
* Posting about participation in the event on social media

These activities can be completed quickly to gain additional experience points.

Among the specific decisions we made was following the moderator known on Discord as “Goose,”who guided us through the calls, activities, and webinars. We then moved forward with Introduction to GitHub and Code with Codespaces.

We created a GitHub repository where we are storing the materials for the Space Dogs Cloud Telemetry API project. In this repository, we are developing the documentation as well as defining the folder structure where the project components will be hosted. This forms the main foundation of the project.

One issue we experienced outside the platform was that the *MLH registration links did not direct participants straight to the introductory webinars on Twitch* and YouTube. However, we solved this by following the instructions provided by the moderators.

During the creation of the project repository, one difficulty was making newly created folders visible in GitHub when working with a local version of VS Code. The solution was to include a gitkeepfile inside the folders.

In the Introduction to GitHub challenge, there were no major difficulties, since the instructions were clear and the tasks were straightforward to solve.

In contrast, the Code with Codespaces challenge was much more difficult due to the length of the instructions, the number of required installations, the challenges involved in loading extensions, writing code for each file, the very slow rebuild processes, and the fact that, despite being an online version of VS Code, it felt slow and somewhat unintuitive to use. The solution was to iterate several times and persevere until we learned how to use this new environment effectively.

So far, we have also validated the use of *mobile devices as a complementary tool* for managing the GitHub repository. On a phone, it is not possible to create folders directly, but it is possible to upload text files and documents. Therefore, the folder structure is created from the laptop, while the phone is used to upload evidence and progress related to projects, hackathons, and webinars.

Sábado 14 de marzo 
## Development Report – March 14

On March 14, the team worked on the development of the **first functional version of the Space Dogs Cloud Telemetry API**, using **Python** and the **Flask framework**. The main objective was to implement a **/telemetry endpoint** capable of generating and returning **simulated satellite telemetry data in JSON format**, while also documenting the system and performing a basic functional validation of the API.

### Backend Development

José was responsible for the backend implementation. He began by cloning the project repository, configuring the Python environment, and installing the required dependencies. After setting up the development environment, he created the **app.py** file inside the **/api module**, where the API logic was implemented.

Within this file, José developed the **/telemetry endpoint**, which generates simulated telemetry values representing key spacecraft parameters. These include:

* Temperature
* Battery level
* Signal strength
* Timestamp
* Subsystem status

The endpoint dynamically produces randomized values within realistic ranges to simulate telemetry data that could be received from a satellite or remote system.

Once the implementation was completed, José ran the API locally using **Flask** and accessed the endpoint through a web browser to validate its behavior. The response was successfully generated in **JSON format**, confirming that the endpoint was functioning as expected.

### Issue Encountered and Resolution

During the initial testing phase, an issue appeared when running the API using the command:

```
python app.py
```

When accessing the base URL in the browser, the page returned a **404 Not Found** error. After investigating the issue, the team realized that this behavior was expected because the application did not yet define a **root route ("/")**.

To improve the user experience and provide confirmation that the API was running correctly, the code was expanded to include a root endpoint that returns a simple status message.

The updated implementation was as follows:

```python
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
```

With this update, the root page now displays the message **"Space Dogs Telemetry API is running"**, confirming that the service is active. When accessing the URL with the **/telemetry** path, the API returns simulated telemetry data in JSON format.

After verifying the correct functionality of the API, José committed the changes to the repository using **Git** and pushed the updated code to **GitHub**.

### Documentation and Functional Review

Maryfer supported the project remotely from her phone by contributing to the **documentation and functional review** of the system. She prepared written notes explaining the purpose of the API, the behavior of the **/telemetry endpoint**, and the meaning of each simulated telemetry variable.

Additionally, she reviewed the API response based on the testing evidence provided by José and verified that:

* The API response was correctly formatted in **JSON**
* All telemetry variables were present
* The endpoint returned consistent simulated data

Using this information, she drafted the **endpoint documentation and validation notes**, which were added to the **/docs directory** of the project repository.

### Results of the Day

By the end of the development session, the team successfully achieved the following milestones:

* Implemented a **functional REST API**
* Generated **simulated telemetry data in JSON format**
* Conducted **basic endpoint testing**
* Produced **initial system documentation**

This progress established the **foundational backend infrastructure** for the project. The API can later be expanded to integrate with **cloud databases, monitoring dashboards, or data analysis platforms**, enabling more advanced telemetry processing and visualization capabilities.

domingo 15 de marzo
Summary – Space Dogs Telemetry System Development (March 15)
During the March 15 work session, the team continued developing the backend infrastructure for the Space Dogs Telemetry Dashboard, focusing on improving telemetry data storage, API architecture, and system reliability.

José worked mainly on backend development. He implemented a SQLite database module to persist telemetry data generated by the API. The database schema includes fields such as temperature, battery level, signal strength, timestamp, and subsystem status, along with an auto-incremented record ID. The Flask API was updated so that each time the /telemetry endpoint generates simulated telemetry data, the system also stores it in the database while still returning the data in JSON format.

After integrating the database, the API was executed locally and tested by repeatedly accessing the telemetry endpoint. This simulated multiple telemetry transmissions and confirmed that the system successfully created and stored records in the database file telemetry.db. Additional validation was performed through Python queries to ensure the telemetry entries were correctly saved.

Once the system was verified, the implementation was committed to the GitHub repository with the message “Add SQLite telemetry storage system.” This documented the new feature and ensured version control for the project.

Maryfer contributed by reviewing the repository updates and preparing documentation explaining how the telemetry storage system works. The documentation describes the purpose of storing telemetry data, the importance of historical telemetry logging in spacecraft monitoring systems, and how the SQLite implementation simulates real mission telemetry tracking.

The document also describes three major improvement versions of the system:

Version 1 introduced architectural improvements such as a database context manager, separation of database logic from API routes, better error handling, timezone-aware timestamps, and new API endpoints for telemetry history, statistics, and health checks.

Version 2 focused on software engineering practices, including the use of dataclasses for structured telemetry records, custom database exceptions, database indexing, WAL mode for better performance, environment-based configuration, CORS support, lifecycle request hooks for performance monitoring, and improved anomaly simulation.

Version 3 added advanced system capabilities such as schema migrations for safe database updates, validation mechanisms for telemetry data, bulk data insertion for performance, secure query building to prevent SQL injection, rate limiting to protect the API, caching for telemetry statistics, request tracing with unique IDs, support for sending telemetry via POST requests, and the ability to export stored telemetry data as a CSV file.

Overall, the work completed on March 15 significantly strengthened the backend architecture, reliability, and scalability of the Space Dogs Telemetry API. The system now supports telemetry generation, persistent storage, historical analysis, improved monitoring, and safer API operation, representing a major step toward a realistic spacecraft telemetry monitoring platform.


domingo 15 de marzo

Extended Summary – Space Dogs Telemetry System Development (March 15)

During the work session on March 15, the team continued developing the backend infrastructure of the Space Dogs Telemetry Dashboard, focusing on improving telemetry data persistence, API architecture, reliability, and system observability. The work carried out during this session significantly strengthened the system’s ability to simulate and manage spacecraft telemetry data in a realistic and scalable way.

José focused primarily on backend development and system architecture. One of the first tasks was implementing a SQLite database layer inside the API project structure by creating the database.py module. This module is responsible for initializing the database and defining the telemetry table schema. The schema includes fields commonly used in spacecraft telemetry systems such as temperature, battery level, signal strength, timestamp, and subsystem status, along with an automatically incrementing identifier that uniquely tracks every telemetry record.

After defining the schema, the database layer was integrated into the existing Flask API. The /telemetry endpoint, which previously generated simulated telemetry values and returned them as JSON, was updated to also store each telemetry reading in the SQLite database. This change transformed the system from a simple simulation endpoint into a persistent telemetry logging system, allowing telemetry readings to be recorded for later analysis.

Once the integration was completed, the API server was executed locally using the command python app.py. Multiple requests were sent to the telemetry endpoint using a web browser in order to simulate repeated telemetry transmissions from a spacecraft system. These tests confirmed that the API was correctly generating telemetry data, responding with structured JSON, and simultaneously inserting the records into the telemetry database table.

The persistence layer was validated by confirming that the telemetry.db database file was automatically created in the project directory. Additional verification was performed by querying the database through the Python interpreter to ensure that multiple telemetry entries had been successfully stored. This step confirmed that the telemetry storage mechanism was working correctly and that the database schema was properly implemented.

After verifying that the telemetry persistence feature worked as intended, José documented the changes in the project repository managed with Git and hosted on GitHub. The modified files were staged and committed using the message “Add SQLite telemetry storage system”, and then pushed to the remote repository. This step ensured proper version control and documented the new system capability within the project's development history.

Maryfer contributed to the documentation and validation process. Using her mobile device, she reviewed the repository updates after the commit was pushed and prepared documentation explaining the telemetry storage mechanism. The documentation explains the purpose of storing telemetry data, the importance of historical telemetry logging in real spacecraft monitoring systems, and how the SQLite implementation used in the project simulates how mission control centers track spacecraft health over time. Her work helped clarify the system’s functionality and ensured that the project’s development process was properly recorded.

During the session, the team also analyzed and implemented three progressive versions of improvements to the API and database architecture.

The first version focused on improving the reliability and maintainability of the code. One major change was replacing relative database paths with an absolute path using the os.path module, ensuring the database file is always created in the correct directory regardless of where the API is executed. A context manager for database connections was implemented to guarantee that database connections are properly opened and closed, preventing resource leaks and ensuring safe commits or rollbacks during database operations. The system also introduced row_factory = sqlite3.Row, allowing database results to be accessed using descriptive field names rather than numeric indexes, which improves code readability.

Additionally, database logic was separated from the API routes through functions such as save_telemetry(), get_all_telemetry(), and get_telemetry_stats(). This separation of concerns makes the codebase easier to maintain and test. New API endpoints were also added, including endpoints for retrieving telemetry history, obtaining summary statistics, and performing system health checks.

The second version introduced more advanced software engineering practices. Telemetry data structures were improved using Python dataclasses, which provide a strongly defined structure for telemetry records and reduce the likelihood of programming errors. A custom DatabaseError exception class was implemented to standardize how database-related errors are handled throughout the system.

Performance improvements were also introduced. SQLite was configured to use Write-Ahead Logging (WAL) mode, allowing the database to handle concurrent read and write operations more efficiently. Database indexes were added to important fields such as timestamps and subsystem status, significantly improving query performance as the database grows. Pagination support was also implemented so that telemetry history can be retrieved in manageable pages instead of returning all records at once.

In addition, the API configuration was improved using environment variables, allowing deployment environments to control settings like port numbers and debug modes without modifying source code. Request lifecycle hooks were added to measure response time for every API request, enabling performance monitoring. Cross-Origin Resource Sharing (CORS) headers were also introduced so that web-based dashboards hosted on other domains can safely interact with the API.

The third version introduced even more advanced architectural improvements designed to simulate real-world backend systems. A database migration system was implemented to safely evolve the database schema over time without deleting existing data. This approach uses a schema version table to track which structural updates have already been applied.

Input validation was also implemented to ensure that telemetry values remain within acceptable ranges. Separate exception classes were created to distinguish between database errors and validation errors, allowing the API to return the appropriate HTTP status codes when problems occur.

Additional features introduced in this version include bulk telemetry insertion for improved performance when inserting multiple records, secure query building techniques that prevent SQL injection attacks, and an API rate limiting system that protects the server from excessive request traffic.

To improve performance further, a statistics caching mechanism was added so that frequently requested telemetry statistics do not require repeated full-table database scans. Request tracing was also implemented using unique request IDs, allowing developers to track individual requests across log files for easier debugging.

Another important capability added in this stage was the ability for the /telemetry endpoint to accept JSON input via POST requests, allowing users to submit specific telemetry values rather than relying entirely on randomly generated data. Finally, an endpoint was added to export telemetry data as a CSV file, allowing the stored telemetry records to be easily downloaded and analyzed using spreadsheet tools.

Overall, the work completed during the March 15 session significantly enhanced the functionality, reliability, scalability, and realism of the Space Dogs Telemetry API. The system now supports telemetry generation, persistent data storage, historical data analysis, performance monitoring, error handling, and data export capabilities. These improvements represent an important step toward building a fully functional telemetry monitoring platform similar to those used in real spacecraft mission control environments.
