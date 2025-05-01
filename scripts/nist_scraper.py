
import time
from pathlib import Path
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, TimeoutException


# --- Configuration ---
# Define paths relative to the script location for robustness
SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent # Assumes script is in a 'scripts' or similar subdir
IDS_FILE = BASE_DIR / "nist_dataset/ids.txt"
OUTPUT_DIR = BASE_DIR / "nist_dataset/jcamp"
# Use a template string for the URL, the {id} will be replaced in the loop
BASE_URL_TEMPLATE = "https://webbook.nist.gov/cgi/inchi?JCAMP={id}&Index=0&Type=IR"
REQUEST_DELAY_SECONDS = 0.5 # Delay between requests to be polite
# Optional: Specify path to chromedriver if not in PATH
# CHROMEDRIVER_PATH = '/path/to/chromedriver'
# --- End Configuration ---

def download_jcamp_files():
    """
    Downloads JCAMP files from NIST WebBook based on IDs in a file.
    """
    # Create output directory if it doesn't exist
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Output directory: {OUTPUT_DIR}")
    except OSError as e:
        print(f"Error creating output directory {OUTPUT_DIR}: {e}")
        return # Cannot proceed without output directory

    # Read IDs from the file
    try:
        with open(IDS_FILE, 'r') as f:
            # Read lines, strip whitespace, and filter out empty lines
            ids = [line.strip() for line in f if line.strip()]
        if not ids:
            print(f"No IDs found in {IDS_FILE}. Exiting.")
            return
        print(f"Found {len(ids)} IDs to process from {IDS_FILE}.")
    except FileNotFoundError:
        print(f"Error: ID file not found at {IDS_FILE}")
        return # Cannot proceed without IDs
    except Exception as e:
        print(f"Error reading ID file {IDS_FILE}: {e}")
        return

    # --- Initialize WebDriver ---
    driver = None # Initialize driver to None
    try:
        # Setup Chrome options (optional, e.g., for headless mode)
        chrome_options = Options()
        # chrome_options.add_argument("--headless") # Uncomment to run without opening a browser window
        chrome_options.add_argument("--disable-gpu") # Often needed for headless mode
        chrome_options.add_argument("--window-size=1920,1080") # Specify window size

        # Initialize WebDriver (adjust path if necessary)
        # If chromedriver is in your PATH, you might not need Service
        # service = Service(executable_path=CHROMEDRIVER_PATH) # Uncomment if specifying path
        # driver = webdriver.Chrome(service=service, options=chrome_options) # Uncomment if specifying path
        driver = webdriver.Chrome(options=chrome_options) # Assumes chromedriver is in PATH

        # Set a page load timeout
        driver.set_page_load_timeout(30) # Wait up to 30 seconds for page to load

    except WebDriverException as e:
        print(f"Error initializing WebDriver: {e}")
        print("Please ensure ChromeDriver is installed and accessible in your PATH or specify its path.")
        return # Cannot proceed without a driver
    except Exception as e:
        print(f"An unexpected error occurred during WebDriver setup: {e}")
        return

    # --- Main Download Loop ---
    success_count = 0
    skip_count = 0
    error_count = 0

    try: # Wrap the loop in try...finally to ensure driver.quit() is called
        for jcamp_id in ids:
            output_path = OUTPUT_DIR / f"{jcamp_id}.jdx" # Standard extension for JCAMP-DX

            # Check if file already exists
            if output_path.exists():
                print(f"File for {jcamp_id} already exists. Skipping.")
                skip_count += 1
                continue

            # Construct the specific URL for the current ID
            url = BASE_URL_TEMPLATE.format(id=jcamp_id)
            print(f"Processing {jcamp_id}: Navigating to {url}...")


            try:
                # Navigate to the URL
                driver.get(url)

                # Get the page source (which should be the JCAMP data)
                # No need for complex waits as the content is served directly
                content = driver.page_source

                # Basic check if content looks like JCAMP
                # NIST sometimes returns HTML error pages even with Selenium
                if "##TITLE=" not in content and "##JCAMP-DX=" not in content:
                     print(f"Warning: Content for {jcamp_id} from {url} doesn't look like a JCAMP file (might be HTML error). Skipping.")
                     error_count += 1
                     # Optional: Save the unexpected content for debugging
                     # with open(OUTPUT_DIR / f"{jcamp_id}_error.html", 'w', encoding='utf-8') as err_f:
                     #     err_f.write(content)
                     continue # Skip saving this file

                # Save the valid JCAMP file
                try:
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"Successfully downloaded and saved {output_path}")
                    success_count += 1
                except IOError as e:
                    print(f"Error saving file {output_path}: {e}")
                    error_count += 1

            except TimeoutException:
                print(f"Error: Page load timed out for {jcamp_id} at {url}")
                error_count += 1
            except WebDriverException as e:
                # Catch Selenium-specific errors during navigation/page source access
                print(f"Error: WebDriver error for {jcamp_id} at {url}: {e}")
                error_count += 1
            except Exception as e:
                # Catch any other unexpected errors during processing of a single ID
                print(f"An unexpected error occurred for {jcamp_id}: {e}")
                error_count += 1

            # Be polite to the server - add a delay
            time.sleep(REQUEST_DELAY_SECONDS)

    finally: # Ensure the browser is closed even if errors occur
        if driver:
            print("\nClosing WebDriver...")
            driver.quit()
            print("WebDriver closed.")

    # --- End of Loop - Print Summary ---
    print("\n--- Download Summary ---")
    print(f"Successfully downloaded: {success_count}")
    print(f"Skipped (already exist): {skip_count}")
    print(f"Errors encountered:      {error_count}")
    print(f"Total IDs processed:     {len(ids)}")
    print("------------------------")

if __name__ == "__main__":
    print("Starting NIST JCAMP file download...")
    download_jcamp_files()
    print("NIST JCAMP file download finished.")

