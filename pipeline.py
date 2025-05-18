# pipeline.py (MODIFIED - Pass app_root to fetch functions)
import os
import time
import traceback
import re
import logging # Added for logging within pipeline if needed

import pandas as pd
import yfinance as yf

from config import TICKERS
from data_collection import fetch_stock_data
from macro_data import fetch_macro_indicators
from data_preprocessing import preprocess_data
from prophet_model import train_prophet_model

# Configure logging if needed within the pipeline itself
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)

# --- Original pipeline function (MODIFIED) ---
def run_pipeline(ticker, ts, app_root):
    """
    Runs the full analysis pipeline for a given stock ticker.
    Relies on fetch functions for caching, passing app_root for path consistency.
    """
    static_dir_path = os.path.join(app_root, 'static')
    os.makedirs(static_dir_path, exist_ok=True)

    processed_csv = report_path = report_html = None
    model = forecast = None

    try:
        print(f"\n----- Starting ORIGINAL pipeline for {ticker} -----")
        valid_ticker_pattern = r'^[A-Z0-9\^.-]+$'
        if not ticker or not re.match(valid_ticker_pattern, ticker):
             raise ValueError(f"[Original Pipeline] Invalid ticker format: {ticker}.")

        # --- 1. Data Collection (Pass app_root) ---
        print("Step 1: Fetching stock data (checking cache)...")
        stock_data = fetch_stock_data(ticker, app_root=app_root) # Pass app_root
        if stock_data is None or stock_data.empty:
            raise RuntimeError(f"Failed to fetch or load stock data for ticker: {ticker}.")

        print("Step 1b: Fetching macroeconomic data (checking cache)...")
        macro_data = fetch_macro_indicators(app_root=app_root) # Pass app_root
        if macro_data is None or macro_data.empty:
            print("Warning: Failed to fetch or load macroeconomic data. Proceeding without it.")

        # --- 2. Data Preprocessing ---
        print("Step 2: Preprocessing data...")
        processed_data = preprocess_data(stock_data, macro_data if macro_data is not None else None)
        if processed_data is None or processed_data.empty:
            raise RuntimeError("Preprocessing resulted in empty dataset.")
        processed_csv = os.path.join(static_dir_path, f"{ticker}_processed_{ts}.csv")
        processed_data.to_csv(processed_csv, index=False)
        print(f"   Saved processed data -> {os.path.basename(processed_csv)}")

        # --- 3. Prophet Model Training & Aggregation ---
        print("Step 3: Training Prophet model & predicting...")
        model, forecast, actual_df, forecast_df = train_prophet_model(
            processed_data, ticker, forecast_horizon='1y', timestamp=ts
        )
        if model is None or forecast is None or actual_df is None or forecast_df is None:
             raise RuntimeError("Prophet model training or forecasting failed.")
        print(f"   Model trained. Forecast generated for {len(forecast_df)} periods.")

        # --- 4. Fetch Fundamentals ---
        print("Step 4: Fetching fundamentals via yfinance...")
        try:
            yf_ticker = yf.Ticker(ticker)
            info_data = {}
            recs_data = pd.DataFrame()
            news_data = []
            try: info_data = yf_ticker.info or {}
            except Exception as info_err: print(f"  Warning: Could not fetch .info: {info_err}")
            try: recs_data = yf_ticker.recommendations if hasattr(yf_ticker, 'recommendations') and yf_ticker.recommendations is not None else pd.DataFrame()
            except Exception as rec_err: print(f"  Warning: Could not fetch .recommendations: {rec_err}")
            try: news_data = yf_ticker.news if hasattr(yf_ticker, 'news') and yf_ticker.news is not None else []
            except Exception as news_err: print(f"  Warning: Could not fetch .news: {news_err}")

            fundamentals = {
                'info': info_data,
                'recommendations': recs_data,
                'news': news_data
            }
            if not fundamentals['info'].get('symbol'):
                 print(f"Warning: Could not fetch detailed info symbol for {ticker} via yfinance.")
        except Exception as yf_err:
             print(f"Warning: Error fetching yfinance fundamentals object for {ticker}: {yf_err}.")
             fundamentals = {'info': {}, 'recommendations': pd.DataFrame(), 'news': []}


        # --- 5. Generate FULL HTML Report ---
        print("Step 5: Generating FULL HTML report...")
        report_path, report_html = create_full_report(
            ticker=ticker, actual_data=actual_df, forecast_data=forecast_df,
            historical_data=processed_data, fundamentals=fundamentals, ts=ts,
            app_root=app_root
        )
        if report_html is None or "Error Generating Report" in report_html:
            raise RuntimeError(f"Original report generator failed or returned error HTML for {ticker}")
        if report_path:
            print(f"   Report saved -> {os.path.basename(report_path)}")
        else:
             print(f"   Report HTML generated, but failed to save file.")

        print(f"----- ORIGINAL Pipeline successful for {ticker} -----")
        return model, forecast, report_path, report_html

    except (ValueError, RuntimeError) as err:
        print(f"----- ORIGINAL Pipeline Error for {ticker} -----")
        print(f"Error: {err}")
        return None, None, None, None
    except Exception as e:
        print(f"----- ORIGINAL Pipeline failure for {ticker} -----")
        print(f"Unexpected Error: {e}")
        traceback.print_exc()
        if processed_csv and os.path.exists(processed_csv):
            try: os.remove(processed_csv)
            except OSError as rm_err: print(f"Error removing file {processed_csv}: {rm_err}")
        return None, None, None, None


# --- WordPress Pipeline Function (MODIFIED) ---
def run_wp_pipeline(ticker, ts, app_root):
    """
    Runs the analysis pipeline specifically to generate WordPress assets.
    Relies on fetch functions for caching, passing app_root.
    """
    static_dir_path = os.path.join(app_root, 'static')
    os.makedirs(static_dir_path, exist_ok=True)

    processed_csv = None
    text_report_html = None
    image_urls = {}
    model = forecast = None

    try:
        print(f"\n>>>>> Starting WORDPRESS pipeline for {ticker} <<<<<")
        valid_ticker_pattern = r'^[A-Z0-9\^.-]+$'
        if not ticker or not re.match(valid_ticker_pattern, ticker):
             raise ValueError(f"[WP Pipeline] Invalid ticker format: {ticker}.")

        # --- Steps 1-4: Data Fetching (Cached), Preprocessing, Model Training, Fundamentals ---
        print("WP Step 1: Fetching stock data (checking cache)...")
        stock_data = fetch_stock_data(ticker, app_root=app_root) # Pass app_root
        if stock_data is None or stock_data.empty: raise RuntimeError(f"Failed to fetch/load stock data for {ticker}.")

        print("WP Step 1b: Fetching macroeconomic data (checking cache)...")
        macro_data = fetch_macro_indicators(app_root=app_root) # Pass app_root
        if macro_data is None or macro_data.empty: print("Warning: Failed to fetch/load macro data.")

        print("WP Step 2: Preprocessing data...")
        processed_data = preprocess_data(stock_data, macro_data if macro_data is not None else None)
        if processed_data is None or processed_data.empty: raise RuntimeError("Preprocessing empty.")
        processed_csv = os.path.join(static_dir_path, f"{ticker}_wp_processed_{ts}.csv")
        processed_data.to_csv(processed_csv, index=False)
        print(f"   Saved WP processed data -> {os.path.basename(processed_csv)}")

        print("WP Step 3: Training Prophet model & predicting...")
        model, forecast, actual_df, forecast_df = train_prophet_model(
            processed_data, ticker, forecast_horizon='1y', timestamp=ts
        )
        if model is None or forecast is None or actual_df is None or forecast_df is None:
             raise RuntimeError("Prophet model failed.")
        print(f"   WP Model trained.")

        print("WP Step 4: Fetching fundamentals...")
        try:
            yf_ticker = yf.Ticker(ticker)
            info_data = {}
            recs_data = pd.DataFrame()
            news_data = []
            try: info_data = yf_ticker.info or {}
            except Exception as info_err: print(f"  Warning: Could not fetch .info: {info_err}")
            try: recs_data = yf_ticker.recommendations if hasattr(yf_ticker, 'recommendations') and yf_ticker.recommendations is not None else pd.DataFrame()
            except Exception as rec_err: print(f"  Warning: Could not fetch .recommendations: {rec_err}")
            try: news_data = yf_ticker.news if hasattr(yf_ticker, 'news') and yf_ticker.news is not None else []
            except Exception as news_err: print(f"  Warning: Could not fetch .news: {news_err}")

            fundamentals = {
                'info': info_data,
                'recommendations': recs_data,
                'news': news_data
            }
            if not fundamentals['info'].get('symbol'): print(f"Warning: Could not fetch detailed info symbol for {ticker}.")
        except Exception as yf_err:
             print(f"Warning: Error fetching yfinance fundamentals object for {ticker}: {yf_err}.")
             fundamentals = {'info': {}, 'recommendations': pd.DataFrame(), 'news': []}


        # --- Step 5: Generate WORDPRESS Assets ---
        print("WP Step 5: Generating WordPress assets (Text HTML + Images)...")
        text_report_html, image_urls = create_wordpress_report_assets(
            ticker=ticker, actual_data=actual_df, forecast_data=forecast_df,
            historical_data=processed_data, fundamentals=fundamentals, ts=ts,
            app_root=app_root
        )
        if text_report_html is None or "Error Generating Report" in text_report_html:
            print(f"Error HTML from report generator: {text_report_html}")
            raise RuntimeError(f"WordPress asset generator failed or returned error HTML for {ticker}")

        print(f"   Text HTML generated.")
        print(f"   Chart image URLs generated: {len(image_urls)} URLs returned.")

        print(f">>>>> WORDPRESS Pipeline successful for {ticker} <<<<<")
        return model, forecast, text_report_html, image_urls

    except (ValueError, RuntimeError) as err:
        print(f">>>>> WORDPRESS Pipeline Error for {ticker} <<<<<")
        print(f"Error: {err}")
        return None, None, None, {}
    except Exception as e:
        print(f">>>>> WORDPRESS Pipeline failure for {ticker} <<<<<")
        print(f"Unexpected Error: {e}")
        traceback.print_exc()
        if processed_csv and os.path.exists(processed_csv):
            try: os.remove(processed_csv)
            except OSError as rm_err: print(f"Error removing file {processed_csv}: {rm_err}")
        return None, None, None, {}


# --- Main execution block (Unchanged) ---
if __name__ == "__main__":
    print("Starting batch pipeline execution (with Caching)...")
    APP_ROOT_STANDALONE = os.path.dirname(os.path.abspath(__file__))
    print(f"Running standalone from: {APP_ROOT_STANDALONE}")

    successful_orig, failed_orig = [], []
    successful_wp, failed_wp = [], []

    print("\n--- Running Original Pipeline Batch ---")
    for ticker in TICKERS:
        ts = str(int(time.time()))
        model, forecast, report_path, report_html = run_pipeline(ticker, ts, APP_ROOT_STANDALONE)
        if report_path and report_html and "Error Generating Report" not in report_html:
            successful_orig.append(ticker)
            print(f"[✔ Orig] {ticker} - Report HTML generated and saved.")
        elif report_html and "Error Generating Report" not in report_html:
            successful_orig.append(f"{ticker} (HTML Only)")
            print(f"[✔ Orig] {ticker} - Report HTML generated (Save Failed).")
        else:
            failed_orig.append(ticker)
            print(f"[✖ Orig] {ticker} - Failed.")
        time.sleep(1)

    print("\nBatch Summary (Original Reports):")
    print(f"  Successful: {', '.join(successful_orig) or 'None'}")
    print(f"  Failed:     {', '.join(failed_orig) or 'None'}")

    print("\n--- Running WP Asset Pipeline Batch ---")
    for ticker in TICKERS:
        ts_wp = str(int(time.time()))
        model_wp, forecast_wp, text_html_wp, img_urls_wp = run_wp_pipeline(ticker, ts_wp, APP_ROOT_STANDALONE)
        if text_html_wp and "Error Generating Report" not in text_html_wp and isinstance(img_urls_wp, dict):
            successful_wp.append(ticker)
            print(f"[✔ WP] {ticker} - Text HTML generated.")
            if img_urls_wp:
                 print(f"[✔ WP] {ticker} - Image URLs generated: {len(img_urls_wp)} URLs")
            else:
                 print(f"[✔ WP] {ticker} - Image URLs dictionary is empty.")
        else:
            failed_wp.append(ticker)
            print(f"[✖ WP] {ticker} - Failed.")
        time.sleep(1)

    print("\nBatch Summary (WordPress Assets):")
    print(f"  Successful: {', '.join(successful_wp) or 'None'}")
    print(f"  Failed:     {', '.join(failed_wp) or 'None'}")

    print("\nBatch pipeline execution completed.")