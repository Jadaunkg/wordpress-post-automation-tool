from flask import Flask, render_template, request, redirect, url_for, flash
import os
import sys
from dotenv import load_dotenv

# Add the directory of auto_publisher to sys.path if it's not in the same directory
# For example, if auto_publisher.py is in the parent directory:
# sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
# If in the same directory, this is not strictly needed but doesn't hurt.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import auto_publisher
except ImportError as e:
    print(f"Failed to import auto_publisher: {e}")
    print("Ensure auto_publisher.py is in the Python path or the same directory as automation_controller.py.")
    # Provide a fallback SITES_CONFIG for the UI to at least load
    auto_publisher = type('obj', (object,), {'SITES_CONFIG': {}, 'load_sites_config': lambda: {}, 'trigger_publishing_run': None, 'MAX_POSTS_PER_DAY_FROM_ENV': 15})


load_dotenv() # Load .env variables for Flask app if any, and for auto_publisher

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your_super_secret_key_for_flask_sessions")

# Ensure SITES_CONFIG is loaded when Flask app starts
auto_publisher.load_sites_config()

@app.route('/', methods=['GET'])
def control_panel():
    # Get current post counts for display
    try:
        state = auto_publisher.load_state()
        posts_today = state.get('posts_today_by_site', {})
        last_run_date = state.get('last_run_date', 'N/A')
    except Exception as e: # Handle case where state file might be problematic briefly
        flash(f"Error loading current state: {e}", "warning")
        posts_today = {}
        last_run_date = 'Error loading'

    # Make sure SITES_CONFIG is current
    current_sites_config = auto_publisher.load_sites_config()


    site_details = []
    for site_name in current_sites_config.keys():
        site_details.append({
            "name": site_name,
            "posts_today": posts_today.get(site_name, 0)
        })

    return render_template('control_panel.html', 
                           sites=site_details, 
                           max_daily_posts=auto_publisher.MAX_POSTS_PER_DAY_FROM_ENV,
                           last_run_date_for_counts=last_run_date)

@app.route('/run-automation', methods=['POST'])
def run_automation():
    if auto_publisher.trigger_publishing_run is None:
        flash("Auto publisher module could not be loaded correctly. Cannot run automation.", "error")
        return redirect(url_for('control_panel'))

    selected_sites_list = []
    articles_to_publish_map = {}

    # Reload site config in case .env changed since app start
    auto_publisher.load_sites_config()

    for site_name in auto_publisher.SITES_CONFIG.keys():
        if request.form.get(f"run_{site_name}"): # Checkbox for enabling site
            selected_sites_list.append(site_name)
            try:
                # Number of posts for this specific run, not the daily total
                num_posts_for_run = int(request.form.get(f"posts_{site_name}", 0))
                if num_posts_for_run < 0: num_posts_for_run = 0
                # The auto_publisher will cap this against MAX_POSTS_PER_DAY_FROM_ENV and posts_already_made_today
                articles_to_publish_map[site_name] = num_posts_for_run
            except ValueError:
                flash(f"Invalid number of posts for {site_name}. Defaulting to 0 for this run.", "warning")
                articles_to_publish_map[site_name] = 0
    
    if not selected_sites_list:
        flash("No sites selected for automation.", "info")
        return redirect(url_for('control_panel'))

    flash(f"Starting automation for: {', '.join(selected_sites_list)} with targets: {articles_to_publish_map}", "info")
    
    # It's better to run this in a background thread for a real app
    # For simplicity here, it's a blocking call.
    try:
        results = auto_publisher.trigger_publishing_run(selected_sites_list, articles_to_publish_map)
        for site, message in results.items():
            flash(f"{site}: {message}", "success" if "Successfully published" in message or "already met" in message or "No posts requested" in message else "warning")
    except Exception as e:
        flash(f"An error occurred during automation: {e}", "error")
        app.logger.error(f"Error during trigger_publishing_run: {e}", exc_info=True)


    return redirect(url_for('control_panel'))

if __name__ == '__main__':
    # Ensure logging for Flask app itself if needed
    # app.logger.setLevel(logging.INFO) # Example
    app.run(debug=True, host='0.0.0.0', port=5002) # Use a different port if your other app.py uses 5001