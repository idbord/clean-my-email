# Clean My Email

This repository contains a Flask web application and a Python script designed to help you manage and clean up your Gmail inbox. It allows you to pull your email data, visualize it, and perform bulk actions like deleting or marking emails as read, based on various filters.

### Features

*   **Email Data Pulling**: Fetches emails from your Gmail account and stores relevant metadata in a local SQLite database.
*   **Web Interface**: A Flask-based web application provides a user-friendly interface to interact with your email data.
*   **Data Visualization**: Displays charts showing email reception trends and emails per sender.
*   **Filtering**: Filter emails by date range, sender, and various labels (starred, important, personal, read).
*   **Bulk Actions**:
    *   Delete selected emails from Gmail and the local database.
    *   Mark selected emails as read in Gmail and the local database.
    *   Perform bulk delete/mark as read operations based on applied filters.
    *   Delete/mark as read all emails from a specific sender.

### Setup

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/your-username/clean-my-email.git
    cd clean-my-email
    ```
2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Google API Credentials**:
    *   Go to the [Google Cloud Console](https://console.developers.google.com/).
    *   Create a new project or select an existing one.
    *   Enable the "Gmail API".
    *   Go to "Credentials" and create "OAuth client ID" credentials. Choose "Desktop app" as the application type.
    *   Download the `credentials.json` file and place it in the root directory of this project.
4.  **Pull your emails**:
    Run the `email_puller.py` script to populate your local database with email data. The first time you run this, it will open a browser window for Google authentication.
    ```bash
    python email_puller.py
    ```

### Usage

1.  **Start the Flask application**:
    ```bash
    python app.py
    ```
2.  Open your web browser and navigate to `http://127.0.0.1:5000/` (or the address shown in your console).
3.  Use the web interface to filter, visualize, and manage your emails.

### Technologies Used

*   **Flask**: Web framework for the application.
*   **SQLite**: Local database to store email metadata.
*   **Google Gmail API**: For interacting with Gmail to fetch and modify emails.
*   **Pandas**: For data manipulation and analysis.
*   **gunicorn**: (Optional) For production deployment of the Flask app.
*   **HTML/CSS/JavaScript**: For the frontend interface.
