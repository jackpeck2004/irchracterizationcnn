import logging
from selenium import webdriver
from time import sleep, time
import argparse # Import argparse for command-line arguments
import multiprocessing
from pathlib import Path
from selenium.webdriver.common.by import By
import requests
from selenium.common.exceptions import NoSuchElementException, WebDriverException

JCAMP_DIR = Path("../nist_dataset/jdx")
INCHI_DIR = Path("../nist_dataset/inchi")
JCAMP_DIR.mkdir(parents=True, exist_ok=True)
INCHI_DIR.mkdir(parents=True, exist_ok=True)

# Configure basic logging for the main process
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(processName)s - %(message)s')

def get_nist(ids, headless=False):
    # Configure logging within the function for multiprocessing compatibility
    # Each process will get its own logger instance based on the root config
    log = logging.getLogger()
    log.info(f"Process started for {len(ids)} IDs.")

    driver = None # Initialize driver to None
    try:
        options = webdriver.ChromeOptions()
        if headless:
            log.info("Configuring WebDriver for headless mode.")
            options.add_argument('--headless')
            options.add_argument('--disable-gpu') # Often recommended for headless mode
            options.add_argument('--window-size=1920,1080') # Specify window size for headless
        else:
            log.info("Configuring WebDriver for normal (visible) mode.")
            # options.add_argument("--start-maximized")

        log.info("Initializing WebDriver...")
        driver = webdriver.Chrome(options=options)
        driver.implicitly_wait(5) # Increased implicit wait slightly
        log.info("WebDriver initialized successfully.")

    except WebDriverException as e:
        log.error(f"Failed to initialize WebDriver: {e}", exc_info=True)
        return # Cannot continue without a driver
    except Exception as e:
        log.error(f"An unexpected error occurred during WebDriver setup: {e}", exc_info=True)
        return

    processed_count = 0
    skipped_count = 0
    error_count = 0

    try: # Wrap main loop in try...finally to ensure driver quit
        for i, nist_id in enumerate(ids):
            log.info(f"Processing ID {i+1}/{len(ids)}: {nist_id}")
            inchi_path = INCHI_DIR / f"{nist_id}.inchi"
            jcamp_path = JCAMP_DIR / f"{nist_id}_.jdx" # Note the underscore

            # Check if both files already exist
            if inchi_path.exists() and jcamp_path.exists():
                log.info(f"Files for {nist_id} already exist. Skipping.")
                skipped_count += 1
                continue

            # --- Get InChI using Selenium ---
            inchi = None
            try:
                inchi_url = f'https://webbook.nist.gov/cgi/inchi?ID={nist_id}&Mask=80#IR-Spec'
                log.info(f"Navigating to InChI page: {inchi_url}")
                driver.get(inchi_url)
                # Consider adding a small explicit wait if implicit wait isn't enough
                # from selenium.webdriver.support.ui import WebDriverWait
                # from selenium.webdriver.support import expected_conditions as EC
                # wait = WebDriverWait(driver, 10)
                # inchi_element = wait.until(EC.presence_of_element_located((By.XPATH, '/html/body/main/ul[1]/li[3]/div/div[1]/span')))
                # inchi = inchi_element.text
                inchi_element = driver.find_element(by=By.XPATH, value='/html/body/main/ul[1]/li[3]/div/div[1]/span')
                inchi = inchi_element.text
                log.info(f"Found InChI for {nist_id}: {inchi[:30]}...") # Log truncated InChI
            except NoSuchElementException:
                log.warning(f"InChI element not found on page for {nist_id}. Skipping.")
                error_count += 1
                continue # Skip to the next nist_id if InChI isn't found
            except WebDriverException as e:
                log.error(f"WebDriver error getting InChI for {nist_id}: {e}", exc_info=True)
                error_count += 1
                continue # Skip to next ID on WebDriver errors
            except Exception as e:
                log.error(f"Unexpected error getting InChI for {nist_id}: {e}", exc_info=True)
                error_count += 1
                continue # Skip

            # --- Get JCAMP using requests ---
            jcamp_url = f"https://webbook.nist.gov/cgi/inchi?JCAMP={nist_id}&Index=0&Type=IR"
            log.info(f"Fetching JCAMP data from: {jcamp_url}")
            try:
                r = requests.get(jcamp_url, timeout=30) # Added timeout
                log.info(f"JCAMP request for {nist_id} completed with status code: {r.status_code}")
                r.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

                content = r.content.decode('utf-8') # Decode immediately for checks

                # Check if the response content is empty or indicates an error
                if not content or "##TITLE=Spectrum not found" in content or "<title>Error</title>" in content.lower():
                    log.warning(f"JCAMP spectrum not found or empty for {nist_id} at {jcamp_url}.")
                    error_count += 1
                    # No need to remove InChI file here, as we haven't saved it yet
                    continue # Skip to the next nist_id

                # --- Save Files ---
                try:
                    log.info(f"Writing InChI to {inchi_path}")
                    with open(inchi_path, "w", encoding='utf-8') as inchi_file:
                        inchi_file.write(inchi)

                    log.info(f"Writing JCAMP to {jcamp_path}")
                    with open(jcamp_path, "w", encoding='utf-8') as jcamp_file:
                        jcamp_file.write(content)

                    log.info(f"Successfully saved files for {nist_id}")
                    processed_count += 1

                except IOError as e:
                    log.error(f"Error writing files for {nist_id}: {e}", exc_info=True)
                    error_count += 1
                    # Attempt cleanup if files were partially created
                    if inchi_path.exists(): inchi_path.unlink(missing_ok=True)
                    if jcamp_path.exists(): jcamp_path.unlink(missing_ok=True)

            except requests.exceptions.Timeout:
                log.error(f"Request timed out fetching JCAMP for {nist_id} from {jcamp_url}")
                error_count += 1
            except requests.exceptions.HTTPError as e:
                log.error(f"HTTP error fetching JCAMP for {nist_id} from {jcamp_url}: {e}")
                error_count += 1
            except requests.exceptions.RequestException as e:
                log.error(f"Request exception fetching JCAMP for {nist_id} from {jcamp_url}: {e}", exc_info=True)
                error_count += 1
            except Exception as e:
                log.error(f"Unexpected error processing JCAMP for {nist_id}: {e}", exc_info=True)
                error_count += 1

            # Optional: Add a small delay even after errors to prevent hammering
            sleep(0.5) # Reduced sleep as requests are likely faster than selenium nav

    finally:
        if driver:
            log.info("Closing WebDriver...")
            try:
                driver.quit()
                log.info("WebDriver closed.")
            except Exception as e:
                log.error(f"Error closing WebDriver: {e}", exc_info=True)
        log.info(f"Process finished. Processed: {processed_count}, Skipped: {skipped_count}, Errors: {error_count}")


if __name__ == "__main__":
    # Setup argument parser as before
    parser = argparse.ArgumentParser(description="Scrape IR spectra (JCAMP) and InChI data from NIST WebBook.")
    parser.add_argument(
        '--headless',
        action='store_true',
        help='Run the browser in headless mode (no GUI).'
    )
    parser.add_argument(
        '--single-process',
        action='store_true',
        help='Run the scraping sequentially in a single process instead of using multiprocessing.'
    )
    parser.add_argument(
        '--cores',
        type=int,
        default=4,
        help='Number of cores to use for multiprocessing (default: 4). Ignored if --single-process is set.'
    )
    args = parser.parse_args()

    # Read all IDs first
    all_ids = []
    ids_file_path = Path("../nist_dataset/ids.txt")
    try:
        logging.info(f"Reading IDs from {ids_file_path}...")
        with open(ids_file_path, "r") as ids_file:
            all_ids = [line.strip() for line in ids_file if line.strip()] # Read and strip non-empty lines
        logging.info(f"Read {len(all_ids)} IDs.")
    except FileNotFoundError:
        logging.error(f"Error: ID file not found at {ids_file_path}")
        exit(1)
    except Exception as e:
        logging.error(f"Error reading ID file {ids_file_path}: {e}", exc_info=True)
        exit(1)

    if not all_ids:
        logging.warning("No valid IDs found in the ID file. Exiting.")
        exit(0)

    start_time = time()

    if args.single_process:
        logging.info("Running in single-process mode.")
        # Pass the headless argument to get_nist
        get_nist(all_ids, headless=args.headless)
    else:
        cores_to_use = min(args.cores, len(all_ids)) # Don't use more cores than IDs
        if cores_to_use < args.cores:
             logging.warning(f"Requested {args.cores} cores, but only {len(all_ids)} IDs exist. Using {cores_to_use} cores.")
        if cores_to_use <= 0:
             logging.error("Cannot run multiprocessing with 0 cores.")
             exit(1)

        logging.info(f"Running in multiprocessing mode with {cores_to_use} processes.")
        # Distribute IDs among processes
        ids_per_process = [[] for _ in range(cores_to_use)]
        for i, nist_id in enumerate(all_ids):
            ids_per_process[i % cores_to_use].append(nist_id)

        processes = []
        logging.info("Starting processes...")
        for i in range(cores_to_use):
            if not ids_per_process[i]: # Should not happen with the check above, but good practice
                continue
            # Pass the headless argument to the target function
            # Give each process a name for better logging
            process_name = f"Scraper-{i+1}"
            p = multiprocessing.Process(target=get_nist, args=(ids_per_process[i], args.headless), name=process_name)
            processes.append(p)
            p.start()
            logging.info(f"Started process {process_name} with {len(ids_per_process[i])} IDs.")

        # Wait for all processes to finish
        logging.info("Waiting for all processes to finish...")
        for p in processes:
            p.join() # Wait for this process to terminate
            logging.info(f"Process {p.name} finished with exit code {p.exitcode}.")

    end_time = time.time()
    total_time = end_time - start_time
    logging.info(f"All scraping tasks finished. Total execution time: {total_time:.2f} seconds.")
    
