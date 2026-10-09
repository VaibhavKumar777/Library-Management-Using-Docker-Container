# Library Management System

## About

A Library Management System built with FastAPI and PostgreSQL that allows users to manage books, authors, and borrowers.

## Prerequisites

- Docker
- Docker Compose

## How to Run

1. Clone this repository and navigate to the project directory.

2. Create a `.env` file in the project root with the following variables:

   ```env
   postgres_url=postgresql+psycopg://postgres:password@postgres:5432/mydatabase
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=password
   POSTGRES_DB=mydatabase
   ```

   Replace the example credentials with your own values. These are for local development only.

3. Build the Docker image:

   ```bash
   docker compose build
   ```

4. Start the application and PostgreSQL:

   ```bash
   docker compose up -d
   ```

5. Open the interactive API documentation:

   **http://localhost:8080/docs**

## Stopping the Application

```bash
docker compose down
```
    
The PostgreSQL database uses a named volume for data persistence.

## Configuration

The application and database are configured through environment variables in the `.env` file. Do not commit real credentials or secrets to version control.