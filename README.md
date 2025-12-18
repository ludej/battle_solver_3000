# Battle Solver 3000

Backend development hands-on test by Matej Duras.

## Overview
This application is attempting to solve a set of requirements, in details described in the attached document. There were some assumptions and some design decisions made on my part, that I will try to describe here.

Application is written in Python 3.13 using FastAPI framework. FastAPI was chosen due to its speed, ease of use and great support for asynchronous programming. Redis is being utilized as the main data storage as well as battle processing queue.

## Running the Application
To run the application, you will need to have Python 3.13 and Redis installed on your machine. You can follow these steps:
1. Clone the repository to your local machine.
2. Navigate to the project directory.
3. Install the required dependencies using pip:
   ```
   pip install -r requirements.txt
   ```
4. Start the Redis server.
5. Start at least one worker to process battles:
   ```
   rq worker battle_queue
   ```
6. Run the FastAPI application using Uvicorn:
   ```
    uvicorn main:app --reload
    ```
7. Enjoy!

## Authentication
For the purposes of this excercise, a simple token-based authentication mechanism is implemented. 
Each request to the API must include an `x-api-key` header with a valid token - in this case `supersecretapikey`.
In a real-world application, this would be replaced with a more robust authentication system.

## API Endpoints
- `POST /players`: Create a new player. Requires authentication.
- `POST /battles`: Initiate a new battle between two players. Requires authentication.
- `GET /leaderboard`: Retrieve the current leaderboard. Requires authentication.

Both POST endpoint validate inputs and return appropriate error messages for invalid data.

## Battle Processing and Other Considerations
Battle processing is handled asynchronously using RQ (Redis Queue).
When a battle is initiated, it is added to the Redis queue and processed by a worker in the background.
This allows the API to respond quickly without waiting for the battle to complete.
Based on the amount of workers, more battles can be processed in parallel.
There is a simple locking mechanism making sure that a player can not be involved in multiple battles at the same time.

The leaderboard is updated in real-time as battles are processed.
The application is designed to be scalable and can handle a large number of players and battles.

## Testing
Unit tests are included in the `tests` file.
To run the tests, use the following command:
```
pytest tests.py
```