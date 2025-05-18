# Stock Report Automation Portal

## Introduction

The Stock Report Automation Portal is a web application designed to automate the generation and publication of financial stock reports. Users can manage multiple website profiles, configure various report parameters, and trigger automation runs to create and publish detailed stock analysis content to their WordPress sites.

The portal leverages a data pipeline that includes data collection for stock prices and macro indicators, fundamental and technical analysis, feature engineering, and predictive modeling using Facebook Prophet. Generated reports are composed of various configurable sections like company profiles, valuation metrics, financial health, technical summaries, and forecasts. User authentication and profile management are handled via Firebase.

**Core Idea:** To streamline the process of creating in-depth, data-driven financial reports for multiple tickers and publishing them efficiently across different web platforms.

## Key Features

* **User Authentication:** Secure login and registration using email/password and Google Sign-In, powered by Firebase Authentication.
* **User Profile Management:** A dedicated user profile page to view account details and navigate the application.
* **Site Profile Management:**
    * Add, edit, and delete "Site Profiles," which are configurations for target WordPress websites.
    * Each profile includes site URL, WordPress author credentials (username, user ID, app password), Google Sheet names for data input, WordPress category IDs, and scheduling parameters.
    * Select specific report sections to include for each profile.
* **Automation Runner:**
    * Select one or more configured site profiles to run the automation.
    * Specify the number of posts (articles) to generate per profile.
    * Optionally provide custom stock tickers for processing.
    * Upload ticker lists via Excel/CSV files for batch processing.
    * View daily post counts and limits.
* **Financial Report Generation:**
    * **Data Collection:** Fetches stock data (historical prices, volume) and relevant macro-economic indicators.
    * **Data Preprocessing & Feature Engineering:** Cleans data and creates relevant features for analysis and modeling.
    * **Fundamental Analysis:** Gathers company profile information, financial statements, key ratios, and other fundamental data.
    * **Technical Analysis:** Calculates various technical indicators (SMAs, RSI, MACD, Bollinger Bands), support/resistance levels, and determines market sentiment.
    * **Predictive Modeling:** Utilizes Facebook Prophet to generate short-term and long-term price forecasts.
    * **Report Composition:** Assembles detailed reports from various HTML components based on the analyses (e.g., introduction, metrics summary, company profile, valuation, financial health, technical analysis, forecasts, risk factors, FAQ).
* **WordPress Publishing:** (Handled by the `auto_publisher.py` module)
    * Automatically posts the generated reports to the configured WordPress sites.
    * Manages scheduling to avoid overwhelming sites or hitting API limits.
    * Distributes posts among multiple authors if configured.
* **Firebase Integration:**
    * User authentication.
    * Firestore database for storing user-specific site profiles.


## Setup and Installation

### Prerequisites

* Python 3.8+
* Pip (Python package installer)
* Firebase Project:
    * Firebase Authentication enabled (Email/Password and Google Sign-In).
    * Firestore Database created.
    * Firebase Admin SDK Service Account Key.
* Access to a WordPress site with Application Passwords enabled for authors if you intend to use the auto-publishing feature.
* Various API keys for data sources if used directly (e.g., financial data APIs) - configure in `.env`.

### Installation Steps

1.  **Clone the Repository (if applicable):**
    ```bash
    git clone <your-repository-url>
    cd <project-directory-name>
    ```

2.  **Create and Activate a Virtual Environment:**
    ```bash
    python -m venv venv
    # On Windows
    venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Firebase Setup:**

    * **Admin SDK (Backend):**
        * Download your Firebase Admin SDK service account key JSON file from your Firebase Project Settings > Service accounts.
        * Place it in a secure location, for example, in the `config/` directory (e.g., `current automation tool/config/firebase-service-account-key.json`).
            **IMPORTANT:** Ensure this file is **NEVER** committed to a public Git repository. Add its path to your `.gitignore` file (e.g., `config/firebase-service-account-key.json`).
        * The `firebase_admin_setup.py` script will try to load this key.

    * **Client-Side SDK (Frontend):**
        * Open `current automation tool/static/js/firebase-init.js`.
        * Replace the placeholder `firebaseConfig` object with your actual Firebase web app configuration details (apiKey, authDomain, projectId, etc.). You can find this in your Firebase Project Settings > General > Your apps > (select your web app) > Firebase SDK snippet > Config.
            ```javascript
            const firebaseConfig = {
                apiKey: "YOUR_ACTUAL_API_KEY",
                authDomain: "YOUR_ACTUAL_AUTH_DOMAIN",
                projectId: "YOUR_ACTUAL_PROJECT_ID",
                storageBucket: "YOUR_ACTUAL_STORAGE_BUCKET",
                messagingSenderId: "YOUR_ACTUAL_MESSAGING_SENDER_ID",
                appId: "YOUR_ACTUAL_APP_ID"
            };
            ```

    * **Authorized Domains for Authentication:**
        * In the Firebase Console > Authentication > Settings > Authorized domains, add the domains from which you'll be accessing the app (e.g., `localhost`, `127.0.0.1`, and your specific local IP if accessing from other devices on your network, like `192.168.X.X`). Add your production domain when deployed.

5.  **Environment Variables:**
    * Create a `.env` file in the `current automation tool/` directory (root of the Flask app).
    * Add necessary environment variables. Minimally, you'll need a `FLASK_SECRET_KEY`. You might also have API keys for financial data sources or other configurations.
        ```env
        FLASK_SECRET_KEY='a_very_strong_and_random_secret_key_here'
        # GOOGLE_APPLICATION_CREDENTIALS="path/to/your/config/firebase-service-account-key.json" # (firebase_admin_setup.py might use this)
        # Other API keys or config variables used by your Python modules
        # e.g., FRED_API_KEY='your_fred_api_key' (if macro_data.py uses it)
        ```
    * **Important:** Add `.env` to your `.gitignore` file.

6.  **Running the Application:**
    * Ensure your virtual environment is activated.
    * Navigate to the `current automation tool/` directory.
    * Run the main Flask application:
        ```bash
        python main_portal_app.py
        ```
    * The application will typically be available at `http://localhost:5000` or `http://0.0.0.0:5000` (accessible via your machine's IP address on the local network).

## Usage

1.  **Register/Login:** Access the web portal and create an account or log in. Google Sign-In is also available.
2.  **Manage Site Profiles:**
    * Navigate to the "Site Profiles" page.
    * Add new profiles by providing the WordPress site URL, author credentials, desired report sections, etc.
    * Edit or delete existing profiles.
3.  **Run Automation:**
    * Go to the "Run Automation" page.
    * Select the site profiles you want to process.
    * Specify the number of posts, custom tickers, or upload a ticker file.
    * Initiate the automation run. The backend will process the data, generate reports, and attempt to publish them.

## Main Modules & Technologies

* **Backend:** Python, Flask
* **Frontend:** HTML, CSS, JavaScript
* **Authentication & Database:** Firebase (Authentication, Firestore for user site profiles)
* **Data Analysis & Modeling:** Pandas, NumPy, Facebook Prophet, Scikit-learn (likely for feature scaling or other ML tasks)
* **Financial Data:** `yfinance` (likely for stock data), FRED API (potentially for macro data)
* **WordPress Integration:** Python `requests` library or WordPress REST API interaction (via `auto_publisher.py`)

## Future Enhancements / Areas to Improve

* Detailed logging and status updates for automation runs on the frontend.
* More sophisticated error handling and reporting to the user.
* Advanced user roles and permissions.
* Direct editing of WordPress author credentials within the portal (requires secure storage).
* More visualization of generated report data or forecast accuracy within the portal.
* Enhanced security for storing sensitive credentials (e.g., using a dedicated secrets manager).
* Unit and integration tests for various modules.
* Refactoring `app.py` and `site_manager_app.py` if they contain overlapping or outdated logic compared to `main_portal_app.py`.

