import os
import re # <--- Keep the import for the module
import traceback
from flask import Flask, render_template, request, flash, redirect, url_for
from datetime import datetime

# --- Import your report generation function ---
try:
    from wordpress_reporter import generate_wordpress_report
except ImportError as e:
    print(f"Error: Could not import generate_wordpress_report from wordpress_reporter.py: {e}")
    def generate_wordpress_report(site_name, ticker, app_root):
        print("!!! DUMMY FUNCTION CALLED - IMPORT FAILED !!!")
        error_html = f'<div class="stock-report-container error"><p><strong>Error: Could not load the report generation function. Please check server logs.</strong></p></div>'
        error_css = ".stock-report-container.error { border: 2px solid red; background-color: #ffebee; color: #c00; }"
        return error_html, error_css

# --- Flask App Setup ---
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'a_default_insecure_secret_key')
CACHE_DIR = os.path.join(app.root_path, 'data_cache')
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)
    print(f"Created cache directory: {CACHE_DIR}")

# --- Define Site Choices ---
SITE_CHOICES = ["finances forecast", "radar stocks", "bernini capital"]

# --- Add datetime to Jinja globals ---
@app.context_processor
def inject_now():
    return {'now': datetime.now}

# --- Routes ---

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html', site_choices=SITE_CHOICES)

@app.route('/generate', methods=['POST'])
def generate():
    ticker = request.form.get('ticker', '').strip().upper()
    site_name = request.form.get('site_name', '').strip()

    # --- Basic Input Validation ---
    valid_ticker_pattern = r'^[A-Z0-9\^.-]+$'
    # Use the imported 're' module here
    if not ticker or not re.match(valid_ticker_pattern, ticker):
        flash('Invalid or missing ticker symbol format.', 'error')
        return redirect(url_for('index'))
    if not site_name or site_name not in SITE_CHOICES:
        flash('Invalid or missing site name selected.', 'error')
        return redirect(url_for('index'))

    # --- Run Report Generation ---
    html_code = None
    css_code = None
    error_message = None

    try:
        app_root_path = app.root_path
        print(f"Calling generator with: Ticker={ticker}, Site={site_name}, AppRoot={app_root_path}")
        html_code, css_code = generate_wordpress_report(site_name, ticker, app_root_path)

        if html_code and 'class="stock-report-container error"' in html_code:
            error_message = f"Report generation failed for {ticker}. See details in the output."
        elif not html_code or not css_code:
             error_message = f"Report generation failed for {ticker}. No HTML/CSS returned."
             html_code = None
             css_code = None

    except ImportError:
        error_message = "Critical Error: Report generation function could not be loaded."
        print("!!! IMPORT ERROR CAUGHT IN ROUTE !!!")
        traceback.print_exc()
    except ValueError as ve:
         error_message = f"Input Error: {ve}"
         print(f"ValueError during report generation: {ve}")
         traceback.print_exc()
    # --- FIX: Changed 're' to 'runtime_err' ---
    except RuntimeError as runtime_err:
         error_message = f"Processing Error: {runtime_err}"
         print(f"RuntimeError during report generation: {runtime_err}")
         traceback.print_exc()
    # --- End FIX ---
    except Exception as e:
        error_message = f"An unexpected error occurred: {e}"
        print(f"!!! UNEXPECTED ERROR in /generate route for {ticker} !!!")
        traceback.print_exc()

    # --- Render Results Page ---
    return render_template('results.html',
                           ticker=ticker,
                           site_name=site_name,
                           html_code=html_code,
                           css_code=css_code,
                           error_message=error_message)

# --- Run the App ---
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)