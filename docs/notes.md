
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
