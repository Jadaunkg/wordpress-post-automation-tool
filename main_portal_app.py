from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import os
import json
import sys
import time
from datetime import datetime, timezone # Ensure timezone is imported
from dotenv import load_dotenv
import io
from functools import wraps

# --- Firebase Admin Setup ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from firebase_admin_setup import initialize_firebase_admin, verify_firebase_token, get_firestore_client
    initialize_firebase_admin()
    from firebase_admin_setup import _firebase_app_initialized as FIREBASE_INITIALIZED_SUCCESSFULLY
except ImportError as e_fb_admin:
    print(f"CRITICAL: Failed to import or initialize Firebase Admin from firebase_admin_setup: {e_fb_admin}")
    FIREBASE_INITIALIZED_SUCCESSFULLY = False
    def verify_firebase_token(token): print("Firebase dummy: verify_firebase_token called"); return None
    def get_firestore_client(): print("Firebase dummy: get_firestore_client called"); return None

# --- Auto Publisher Module ---
try:
    import auto_publisher
except ImportError as e_ap:
    print(f"CRITICAL: Failed to import auto_publisher.py: {e_ap}")
    class MockAutoPublisher: # Using the more complete MockAutoPublisher
        SITES_PROFILES_CONFIG = []
        ABSOLUTE_MAX_POSTS_PER_DAY_ENV_CAP = 15
        PROFILES_CONFIG_FILE = "profiles_config.json"
        APP_ROOT = os.path.dirname(os.path.abspath(__file__))
        def load_profiles_config(self): return [] # Removed user_uid as it's not in real one
        def load_state(self, user_uid=None, current_profile_ids_from_run=None):
            print(f"MockAutoPublisher.load_state called (user_uid: {user_uid}) - returning generic state.")
            # Simulate a more complete state structure
            base_state = {'posts_today_by_profile': {},'last_run_date': 'N/A','processed_tickers_detailed_log_by_profile': {}}
            if current_profile_ids_from_run:
                for pid in current_profile_ids_from_run:
                    base_state['posts_today_by_profile'][pid] = 0
                    base_state['processed_tickers_detailed_log_by_profile'][pid] = []
            return base_state
        def trigger_publishing_run(self, user_uid, profiles_to_process_data_list, articles_map, custom_tickers_by_profile_id=None, uploaded_file_details_by_profile_id=None):
            print("MockAutoPublisher.trigger_publishing_run called.")
            profile_ids_list = [p.get('profile_id') for p in profiles_to_process_data_list if p.get('profile_id')]
            return {pid:{"status_summary":f"Mock Run for {pid}", "profile_name": pid, "tickers_processed": [], "errors": []} for pid in profile_ids_list}
    auto_publisher = MockAutoPublisher()


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "a_very_secure_default_secret_key_main_portal")

# --- App Configuration ---
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(APP_ROOT, 'temp_uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- Jinja Globals & Helpers ---
@app.context_processor
def inject_globals():
    return {
        'now': datetime.now(timezone.utc),
        'is_user_logged_in': 'firebase_user_uid' in session,
        'user_email': session.get('firebase_user_email'),
        'user_displayName': session.get('firebase_user_displayName'), # Already available
        'FIREBASE_INITIALIZED_SUCCESSFULLY': FIREBASE_INITIALIZED_SUCCESSFULLY
    }

# Datetime formatting filter for Jinja
@app.template_filter('format_datetime')
def format_datetime_filter(value, format="%Y-%m-%d %H:%M:%S"):
    if not value:
        return "N/A"
    try:
        # Handle potential timezone info if present (e.g., 'Z' or +HH:MM)
        if isinstance(value, str):
            if value.endswith('Z'):
                dt_obj = datetime.fromisoformat(value.replace('Z', '+00:00'))
            else:
                dt_obj = datetime.fromisoformat(value)
        elif isinstance(value, datetime):
            dt_obj = value
        else:
            return value # Or raise error/log

        # If timezone naive, assume UTC (or make it configurable)
        if dt_obj.tzinfo is None:
            dt_obj = dt_obj.replace(tzinfo=timezone.utc)

        return dt_obj.strftime(format)
    except (ValueError, AttributeError) as e:
        app.logger.warning(f"Could not format datetime value '{value}': {e}")
        return value


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_all_report_section_keys():
    try:
        from wordpress_reporter import ALL_REPORT_SECTIONS # Assuming this exists
        return list(ALL_REPORT_SECTIONS.keys())
    except ImportError:
        app.logger.warning("Could not import ALL_REPORT_SECTIONS from wordpress_reporter. Using fallback.")
        return [
            "introduction", "metrics_summary", "detailed_forecast_table", "company_profile",
            "valuation_metrics", "total_valuation", "profitability_growth", "analyst_insights",
            "financial_health", "technical_analysis_summary", "short_selling_info",
            "stock_price_statistics", "dividends_shareholder_returns", "conclusion_outlook",
            "risk_factors", "faq"
        ]
ALL_SECTIONS = get_all_report_section_keys()


# --- Authentication Decorator ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not FIREBASE_INITIALIZED_SUCCESSFULLY:
            flash("Firebase authentication is currently unavailable. Please try again later or contact support.", "danger")
            return redirect(url_for('homepage'))
        if 'firebase_user_uid' not in session:
            flash("Please login to access this page.", "warning")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# --- Firestore Helper Functions ---
def get_user_site_profiles_from_firestore(user_uid):
    if not FIREBASE_INITIALIZED_SUCCESSFULLY: return []
    db = get_firestore_client()
    if not db:
        app.logger.error(f"Firestore client not available for get_user_site_profiles_from_firestore (user: {user_uid}).")
        return []
    profiles = []
    try:
        profiles_ref = db.collection(u'userSiteProfiles').document(user_uid).collection(u'profiles').order_by(u'last_updated_at', direction='DESCENDING').stream()
        for profile_doc in profiles_ref:
            profile_data = profile_doc.to_dict()
            profile_data['profile_id'] = profile_doc.id
            profiles.append(profile_data)
        app.logger.info(f"Fetched {len(profiles)} site profiles for user {user_uid} from Firestore.")
    except Exception as e:
        app.logger.error(f"Error fetching site profiles for user {user_uid} from Firestore: {e}", exc_info=True)
    return profiles

def save_user_site_profile_to_firestore(user_uid, profile_data):
    if not FIREBASE_INITIALIZED_SUCCESSFULLY: return False
    db = get_firestore_client()
    if not db:
        app.logger.error(f"Firestore client not available for save_user_site_profile_to_firestore (user: {user_uid}).")
        return False
    try:
        profile_id = profile_data.pop('profile_id', None)
        now_iso = datetime.now(timezone.utc).isoformat()
        profile_data['last_updated_at'] = now_iso
        if not profile_id: # If new profile
            profile_data['created_at'] = now_iso

        if profile_id:
            doc_ref = db.collection(u'userSiteProfiles').document(user_uid).collection(u'profiles').document(profile_id)
            doc_ref.set(profile_data, merge=True)
            app.logger.info(f"Updated site profile {profile_id} for user {user_uid} in Firestore.")
        else:
            doc_ref_tuple = db.collection(u'userSiteProfiles').document(user_uid).collection(u'profiles').add(profile_data)
            profile_id = doc_ref_tuple[1].id
            app.logger.info(f"Added new site profile {profile_id} for user {user_uid} in Firestore.")
        return profile_id
    except Exception as e:
        app.logger.error(f"Error saving site profile for user {user_uid} to Firestore: {e}", exc_info=True)
        if profile_id: profile_data['profile_id'] = profile_id
        return False

def delete_user_site_profile_from_firestore(user_uid, profile_id_to_delete):
    if not FIREBASE_INITIALIZED_SUCCESSFULLY: return False
    db = get_firestore_client()
    if not db:
        app.logger.error(f"Firestore client not available for delete_user_site_profile_from_firestore (user: {user_uid}).")
        return False
    try:
        db.collection(u'userSiteProfiles').document(user_uid).collection(u'profiles').document(profile_id_to_delete).delete()
        app.logger.info(f"Deleted site profile {profile_id_to_delete} for user {user_uid} from Firestore.")
        return True
    except Exception as e:
        app.logger.error(f"Error deleting site profile {profile_id_to_delete} for user {user_uid}: {e}", exc_info=True)
        return False

# --- Helper to get context for pages needing auto_publisher state ---
def get_automation_shared_context(user_uid, profiles_list):
    context = {}
    try:
        current_profile_ids = [p['profile_id'] for p in profiles_list if 'profile_id' in p]
        state = auto_publisher.load_state(user_uid=user_uid, current_profile_ids_from_run=current_profile_ids)
        context['posts_today_by_profile'] = state.get('posts_today_by_profile', {})
        context['last_run_date_for_counts'] = state.get('last_run_date', 'N/A')
        context['processed_tickers_log_map'] = state.get('processed_tickers_detailed_log_by_profile', {})
        context['absolute_max_posts_cap'] = auto_publisher.ABSOLUTE_MAX_POSTS_PER_DAY_ENV_CAP
    except Exception as e:
        app.logger.error(f"Error loading publisher state for shared_context (user: {user_uid}): {e}", exc_info=True)
        context['posts_today_by_profile'] = {}
        context['last_run_date_for_counts'] = "Error"
        context['processed_tickers_log_map'] = {}
        context['absolute_max_posts_cap'] = auto_publisher.ABSOLUTE_MAX_POSTS_PER_DAY_ENV_CAP # Fallback
    return context

# --- Routes ---
@app.route('/')
def homepage():
    return render_template('homepage.html', title="Automation Portal")

@app.route('/login')
def login():
    if 'firebase_user_uid' in session:
        return redirect(url_for('manage_site_profiles'))
    return render_template('login.html', title="Login")

@app.route('/register')
def register():
    if 'firebase_user_uid' in session:
        return redirect(url_for('manage_site_profiles'))
    return render_template('register.html', title="Register")

@app.route('/verify-token', methods=['POST'])
def verify_token_route():
    if not FIREBASE_INITIALIZED_SUCCESSFULLY:
        return jsonify({"error": "Authentication service unavailable."}), 503
    data = request.get_json()
    if not data or 'idToken' not in data:
        return jsonify({"error": "No ID token provided."}), 400
    
    id_token = data['idToken']
    decoded_token = None
    try:
        decoded_token = verify_firebase_token(id_token) # Your function from firebase_admin_setup.py
    except Exception as e:
        app.logger.error(f"Token verification exception: {e}", exc_info=True)
        return jsonify({"error": "Invalid or expired token."}), 401

    if decoded_token and 'uid' in decoded_token:
        if not decoded_token.get('email_verified', False):
            # For email/password, this check is crucial. 
            # For Google Sign-in, email is usually pre-verified.
            app.logger.warning(f"User {decoded_token['uid']} email not verified.")
            # You might decide to still log them in but show a persistent "verify email" banner,
            # or strictly enforce verification before backend session creation.
            # The client-side JS already prevents login if not verified for email/pass.
            # If Google sign-in somehow has an unverified email, this would catch it.
            return jsonify({
                "error": "Email not verified. Please check your inbox.",
                "email_not_verified": True 
            }), 403 # Forbidden
            
        session['firebase_user_uid'] = decoded_token['uid']
        session['firebase_user_email'] = decoded_token.get('email', 'N/A')
        # Ensure 'name' from the token (which is displayName) is stored
        session['firebase_user_displayName'] = decoded_token.get('name', '') 
        session.permanent = True # Make session persistent
        app.logger.info(f"User {decoded_token['uid']} ({session['firebase_user_email']}) logged in successfully. Email Verified: {decoded_token.get('email_verified')}. Name: {session['firebase_user_displayName']}")
        return jsonify({"status": "success", "uid": decoded_token['uid']}), 200
    else:
        app.logger.warning(f"Token verification failed. Decoded token: {decoded_token}")
        return jsonify({"error": "Invalid or expired token."}), 401

@app.route('/logout')
def logout():
    session.pop('firebase_user_uid', None)
    session.pop('firebase_user_email', None)
    session.pop('firebase_user_displayName', None)
    flash("You have been successfully logged out.", "info")
    return redirect(url_for('homepage'))

@app.route('/user-profile')
@login_required
def user_profile_page():
    # Information is primarily sourced from the session, which is populated at login
    # and made available globally to templates via context_processor.
    # No new data fetching logic needed here for this iteration of profile improvement.
    # The existing context_processor already makes user_email and user_displayName available.
    return render_template('user_profile.html', title="Your Profile")

@app.route('/site-profiles')
@login_required
def manage_site_profiles():
    user_uid = session['firebase_user_uid']
    profiles = get_user_site_profiles_from_firestore(user_uid)
    shared_context = get_automation_shared_context(user_uid, profiles)

    return render_template('manage_profiles.html',
                           title="Site Profile Dashboard",
                           profiles=profiles,
                           all_report_sections=ALL_SECTIONS,
                           posts_today_by_profile=shared_context.get('posts_today_by_profile'),
                           last_run_date_for_counts=shared_context.get('last_run_date_for_counts'),
                           processed_tickers_log_map=shared_context.get('processed_tickers_log_map'),
                           absolute_max_posts_cap=shared_context.get('absolute_max_posts_cap')
                           )

@app.route('/site-profiles/add', methods=['POST'])
@login_required
def add_site_profile():
    user_uid = session['firebase_user_uid']
    authors_data = []
    author_idx = 0
    while True:
        username_field = f'author_wp_username_{author_idx}'
        if username_field not in request.form: break
        wp_username = request.form.get(username_field, '').strip()
        wp_user_id = request.form.get(f'author_wp_user_id_{author_idx}', '').strip()
        app_password = request.form.get(f'author_app_password_{author_idx}', '').strip()

        if wp_username and wp_user_id and app_password:
            authors_data.append({
                "id": f"author_{int(time.time())}_{author_idx}",
                "wp_username": wp_username,
                "wp_user_id": wp_user_id,
                "app_password": app_password
            })
        elif wp_username or wp_user_id or app_password: # Partial entry
            flash(f"Author {author_idx + 1} details are incomplete. All fields (Username, User ID, App Password) are required if adding an author.", "warning")
        author_idx += 1

    if not authors_data:
        flash("At least one complete WordPress author is required for a site profile.", "error")
        return redirect(url_for('manage_site_profiles'))

    new_profile_data = {
        "profile_name": request.form.get('profile_name', 'Unnamed Profile').strip(),
        "site_url": request.form.get('site_url', '').strip(),
        "sheet_name": request.form.get('sheet_name', '').strip(),
        "stockforecast_category_id": request.form.get('stockforecast_category_id', '').strip(),
        "min_scheduling_gap_minutes": int(request.form.get('min_scheduling_gap_minutes', 45)),
        "max_scheduling_gap_minutes": int(request.form.get('max_scheduling_gap_minutes', 68)),
        "env_prefix_for_feature_image_colors": request.form.get('env_prefix_for_feature_image_colors', '').strip().upper(),
        "authors": authors_data,
        "report_sections_to_include": request.form.getlist('report_sections_to_include[]')
        # Timestamps are set by save_user_site_profile_to_firestore
    }

    if not new_profile_data["profile_name"] or not new_profile_data["site_url"]:
        flash("Profile Name and Site URL are required.", "error")
        return redirect(url_for('manage_site_profiles'))

    saved_profile_id = save_user_site_profile_to_firestore(user_uid, new_profile_data)
    if saved_profile_id:
        flash(f"Site Profile '{new_profile_data['profile_name']}' added successfully!", "success")
    else:
        flash(f"Failed to add Site Profile '{new_profile_data['profile_name']}'.", "error")
    return redirect(url_for('manage_site_profiles'))

@app.route('/site-profiles/edit/<profile_id_from_firestore>', methods=['GET', 'POST'])
@login_required
def edit_site_profile(profile_id_from_firestore):
    user_uid = session['firebase_user_uid']
    db = get_firestore_client()
    if not db:
        flash("Database service not available.", "danger")
        return redirect(url_for('manage_site_profiles'))

    profile_doc_ref = db.collection(u'userSiteProfiles').document(user_uid).collection(u'profiles').document(profile_id_from_firestore)
    profile_snap = profile_doc_ref.get()

    if not profile_snap.exists:
        flash(f"Site Profile with ID '{profile_id_from_firestore}' not found.", "error")
        return redirect(url_for('manage_site_profiles'))
    
    profile_data = profile_snap.to_dict()
    profile_data['profile_id'] = profile_id_from_firestore # Ensure ID is in dict for template

    if request.method == 'POST':
        profile_data['profile_name'] = request.form.get('profile_name', profile_data.get('profile_name','')).strip()
        profile_data['site_url'] = request.form.get('site_url', profile_data.get('site_url','')).strip()
        profile_data['sheet_name'] = request.form.get('sheet_name', profile_data.get('sheet_name','')).strip()
        profile_data['stockforecast_category_id'] = request.form.get('stockforecast_category_id', profile_data.get('stockforecast_category_id','')).strip()
        profile_data['min_scheduling_gap_minutes'] = int(request.form.get('min_scheduling_gap_minutes', profile_data.get('min_scheduling_gap_minutes',45)))
        profile_data['max_scheduling_gap_minutes'] = int(request.form.get('max_scheduling_gap_minutes', profile_data.get('max_scheduling_gap_minutes',68)))
        profile_data['env_prefix_for_feature_image_colors'] = request.form.get('env_prefix_for_feature_image_colors', profile_data.get('env_prefix_for_feature_image_colors','')).strip().upper()
        profile_data['report_sections_to_include'] = request.form.getlist('report_sections_to_include[]')

        updated_authors = []
        author_idx = 0
        while True:
            username_field = f'author_wp_username_{author_idx}' 
            author_id_field = f'author_id_{author_idx}'

            if not (username_field in request.form or 
                    f'author_wp_user_id_{author_idx}' in request.form or 
                    f'author_app_password_{author_idx}' in request.form or
                    author_id_field in request.form):
                if author_idx == 0 and not (username_field in request.form and \
                                          f'author_wp_user_id_{author_idx}' in request.form and \
                                          f'author_app_password_{author_idx}' in request.form):
                    pass 
                elif not any(key.startswith(f'author_wp_username_{author_idx}') or \
                             key.startswith(f'author_id_{author_idx}') for key in request.form):
                    break 

            wp_username = request.form.get(username_field, '').strip()
            wp_user_id = request.form.get(f'author_wp_user_id_{author_idx}', '').strip()
            app_password = request.form.get(f'author_app_password_{author_idx}', '').strip()
            author_id = request.form.get(author_id_field, f"new_author_{int(time.time())}_{author_idx}")


            if wp_username and wp_user_id and app_password:
                 updated_authors.append({
                    "id": author_id, 
                    "wp_username": wp_username, 
                    "wp_user_id": wp_user_id, 
                    "app_password": app_password 
                })
            elif wp_username or wp_user_id or app_password:
                flash(f"Author entry {author_idx + 1} was incomplete and has been ignored.", "warning")
            author_idx += 1
        
        if not updated_authors:
            flash("At least one complete WordPress author is required. Profile not updated.", "error")
            return render_template('edit_profile.html', title=f"Edit {profile_data.get('profile_name', 'Profile')}", profile=profile_data, all_report_sections=ALL_SECTIONS)

        profile_data['authors'] = updated_authors
        
        data_to_save = profile_data.copy()
        data_to_save['profile_id'] = profile_id_from_firestore


        if save_user_site_profile_to_firestore(user_uid, data_to_save):
            flash(f"Site Profile '{profile_data['profile_name']}' updated successfully!", "success")
        else:
            flash(f"Failed to update Site Profile '{profile_data['profile_name']}'.", "error")
        return redirect(url_for('manage_site_profiles'))

    return render_template('edit_profile.html', title=f"Edit {profile_data.get('profile_name', 'Profile')}", profile=profile_data, all_report_sections=ALL_SECTIONS)

@app.route('/site-profiles/delete/<profile_id_to_delete>', methods=['POST'])
@login_required
def delete_site_profile(profile_id_to_delete):
    user_uid = session['firebase_user_uid']
    if delete_user_site_profile_from_firestore(user_uid, profile_id_to_delete):
        flash(f"Site Profile ID '{profile_id_to_delete}' deleted.", "success")
    else:
        flash(f"Failed to delete Site Profile ID '{profile_id_to_delete}'.", "error")
    return redirect(url_for('manage_site_profiles'))

@app.route('/automation-runner')
@login_required
def automation_runner_page():
    user_uid = session['firebase_user_uid']
    user_site_profiles = get_user_site_profiles_from_firestore(user_uid)
    shared_context = get_automation_shared_context(user_uid, user_site_profiles)
    return render_template('run_automation_page.html',
                           title="Run Automation",
                           user_site_profiles=user_site_profiles,
                           posts_today_by_profile=shared_context.get('posts_today_by_profile'),
                           last_run_date_for_counts=shared_context.get('last_run_date_for_counts'),
                           processed_tickers_log_map=shared_context.get('processed_tickers_log_map'),
                           absolute_max_posts_cap=shared_context.get('absolute_max_posts_cap')
                           )

@app.route('/run-automation-now', methods=['POST'])
@login_required
def run_automation_now():
    user_uid = session['firebase_user_uid']
    profile_ids_to_run_from_form = request.form.getlist('run_profile_ids[]')

    if not profile_ids_to_run_from_form:
        flash("No site profiles selected to run.", "info")
        return redirect(url_for('automation_runner_page'))

    all_user_profiles_data = get_user_site_profiles_from_firestore(user_uid)
    selected_profiles_data_list = [
        p_data for p_data in all_user_profiles_data
        if p_data.get("profile_id") in profile_ids_to_run_from_form
    ]

    if not selected_profiles_data_list:
        flash("Selected profiles could not be found. Please refresh and try again.", "warning")
        return redirect(url_for('automation_runner_page'))

    articles_map = {}
    custom_tickers_for_run = {}
    uploaded_files_for_run = {}

    for profile_data_item in selected_profiles_data_list:
        profile_id = profile_data_item.get("profile_id")
        if not profile_id: continue

        try:
            num_posts = int(request.form.get(f'posts_for_profile_{profile_id}', 0))
            articles_map[profile_id] = max(0, num_posts)
        except ValueError:
            articles_map[profile_id] = 0
        
        custom_ticker_input_str = request.form.get(f'custom_tickers_{profile_id}', '').strip() 
        if custom_ticker_input_str:
            custom_tickers_for_run[profile_id] = [t.strip().upper() for t in custom_ticker_input_str.split(',') if t.strip()]
        
        uploaded_file_field_name = f'ticker_file_{profile_id}'
        if uploaded_file_field_name in request.files:
            file = request.files[uploaded_file_field_name]
            if file and file.filename and allowed_file(file.filename):
                try:
                    from werkzeug.utils import secure_filename
                    filename = secure_filename(file.filename)
                    file_content_bytes = file.read()
                    file.seek(0)
                    uploaded_files_for_run[profile_id] = {
                        "original_filename": filename,
                        "content_bytes": file_content_bytes
                    }
                except Exception as e_upload:
                    app.logger.error(f"Error processing uploaded file '{file.filename}' for profile {profile_id}: {e_upload}", exc_info=True)
                    flash(f"Error processing file for profile {profile_data_item.get('profile_name', profile_id)}.", "error")
            elif file and file.filename: 
                 flash(f"File type not allowed for '{file.filename}' for profile {profile_data_item.get('profile_name', profile_id)}. Allowed: {ALLOWED_EXTENSIONS}", "warning")


    flash(f"Attempting automation for {len(selected_profiles_data_list)} selected profile(s)...", "info")
    try:
        results = auto_publisher.trigger_publishing_run(
            user_uid,
            selected_profiles_data_list,
            articles_map,
            custom_tickers_by_profile_id=custom_tickers_for_run,
            uploaded_file_details_by_profile_id=uploaded_files_for_run
        )
        
        if results:
            for pid_res, res_data in results.items():
                if res_data: 
                    profile_name = res_data.get("profile_name", pid_res) 
                    status_summary = res_data.get("status_summary", "No summary available.")
                    tickers_processed_count = len(res_data.get("tickers_processed", []))
                    errors = res_data.get("errors", [])
                    
                    if errors:
                        flash(f"Profile '{profile_name}': Run completed with issues. Summary: {status_summary}. Details in log. Errors: {'; '.join(errors[:2])}{'...' if len(errors) > 2 else ''}", "warning")
                    else:
                        flash(f"Profile '{profile_name}': Run completed. Summary: {status_summary}. Processed: {tickers_processed_count} tickers.", "success")
                else:
                    flash(f"No result data found for profile ID {pid_res} after run.", "warning")
        else:
            flash("Automation run did not return a summary. Check logs for details.", "warning")

    except Exception as e:
        flash(f"A critical error occurred during the automation run: {str(e)}", "error")
        app.logger.error(f"Automation run error for user {user_uid}: {e}", exc_info=True)
        
    return redirect(url_for('automation_runner_page'))

# --- Main Execution ---
if __name__ == '__main__':
    if not FIREBASE_INITIALIZED_SUCCESSFULLY:
        app.logger.error("App starting with Firebase Admin SDK NOT INITIALIZED.")
    else:
        app.logger.info(f"Starting Main Portal Flask App (Firebase Admin SDK Init: {FIREBASE_INITIALIZED_SUCCESSFULLY}).")
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv("PORT", 5000)))