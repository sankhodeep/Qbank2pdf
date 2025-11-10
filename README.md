# QBank PDF Generator

This is a desktop application that converts MCQ (Multiple Choice Question) question banks from a specific JSON format into a single, well-formatted PDF file. The application provides a user-friendly interface to select and order the question folders for processing.

## Features

-   **Graphical User Interface**: Built with PySide6 for ease of use.
-   **Folder Selection & Ordering**: A dialog allows you to select which question bank folders to include and specify their order in the final PDF.
-   **Handles Complex Content**: Processes questions with text, images, and tables in both the question and explanation sections.
-   **High-Quality PDF Output**: Uses Node.js and Puppeteer (a headless Chrome browser) to render HTML into a clean, styled PDF.
-   **Responsive UI**: The core processing logic runs in a background thread to prevent the application from freezing.

## Prerequisites

-   **Python**: Version 3.7 or newer.
-   **Node.js**: Version 14 or newer, with `npm`.

## Setup Instructions

1.  **Clone the Repository**:
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Install Python Dependencies**:
    It is recommended to use a virtual environment.
    ```bash
    # Create and activate a virtual environment (optional but recommended)
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`

    # Install the required Python packages
    pip install -r requirements.txt
    ```

3.  **Install Node.js Dependencies**:
    This will install Puppeteer and download a compatible version of Chromium.
    ```bash
    npm install
    ```

## How to Run

1.  Make sure you have completed the setup steps above.
2.  Run the main application script:
    ```bash
    python main.py
    ```
3.  **Using the Application**:
    a. Click **"Choose Folder..."** to select the root directory that contains your `output_*` sub-folders.
    b. A dialog will appear. Check the folders you want to include and drag them to set the desired order. Click **OK**.
    c. Click **"Set Output File..."** and specify the name and location for the final PDF file.
    d. Once a root folder and an output file are set, the **"Start Generation"** button will become active. Click it to begin the process.
    e. The status bar at the bottom will show the progress. You will be notified upon completion or if an error occurs.
