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
