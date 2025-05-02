from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from time import sleep
import urllib.request
import multiprocessing
from pathlib import Path
import os # Import the os module for path checking
import argparse # Import argparse for command-line arguments

IMAGE_DIR = Path("../sdbs_dataset/sdbs_images")
OTHER_DIR = Path("../sdbs_dataset/other")
IMAGE_DIR.mkdir(parents=True, exist_ok=True)
OTHER_DIR.mkdir(parents=True, exist_ok=True)

error_title = '//*[@id="content"]/div/fieldset/h2'

def download_image(url, save_as):
    urllib.request.urlretrieve(url, save_as)

# Modify get_gif to accept the headless flag
def get_gif(ids, headless=False):
    # start in headless mode
    # options = webdriver.ChromeOptions()
    # options.add_argument('--headless')
    # driver = webdriver.Chrome(options=options)
    # driver = webdriver.Chrome() # Moved inside the loop

    # driver.get(BASE_URL) # Moved inside the loop
    # sleep(1) # Moved inside the loop

    # driver.set_window_size(1920, 1920)

    # driver.implicitly_wait(1) # Implicit waits can sometimes cause issues with dynamic pages. Consider explicit waits if problems persist.
    max_retries = 3
    retry_delay_seconds = 5 # Wait time after a 403 refresh

    # Initialize driver ONCE before the loop
    print(f"Initializing WebDriver for process handling {len(ids)} IDs...")
    # Set up Chrome options based on the headless flag
    options = webdriver.ChromeOptions()
    if headless:
        print("Configuring WebDriver for headless mode.")
        options.add_argument('--headless')
        options.add_argument('--disable-gpu') # Often recommended for headless mode
        options.add_argument('--window-size=1920,1080') # Specify window size for headless
    else:
        print("Configuring WebDriver for normal (visible) mode.")
        # You might add other options for non-headless mode if needed,
        # like maximizing the window, etc.
        # options.add_argument("--start-maximized")

    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(2) # Set implicit wait once for the driver instance
    print("WebDriver initialized.")

    for sdbs_no in ids:
        attempts = 0
        processed = False
        while attempts < max_retries and not processed:
            attempts += 1
            try:
                BASE_URL = f"https://sdbs.db.aist.go.jp/CompoundLanding.aspx?sdbsno={sdbs_no}"
                # Construct the expected output file path FIRST
                other_path = OTHER_DIR / f"{sdbs_no}_other.txt"
                mediums = ['KBr', 'nujol', 'liquid']
                output_paths = [IMAGE_DIR / f"{sdbs_no}_{medium}.gif" for medium in mediums]

                # Check if the image file already exists
                if sum(map(lambda x: x.exists(), output_paths)) > 1 and other_path.exists():
                    print(f"Image and Other text for {sdbs_no} already exists. Skipping.")
                    continue # Move to the next ID

                # File doesn't exist, proceed with processing using the shared driver
                print(f"Processing {sdbs_no}...")

                # Start from the base URL for each attempt *within the while loop*
                # This handles cases where a previous attempt within the while loop failed
                # after navigating away from the base URL.
                driver.get(BASE_URL)
                # sleep(1) # Allow initial load
                # replace = with :\s

                # Check for 403 error first
                try:
                    error_element = driver.find_element(By.XPATH, error_title)
                    print(f"403 error detected for {sdbs_no} on attempt {attempts}/{max_retries}. Refreshing...")
                    driver.refresh()
                    sleep(retry_delay_seconds) # Wait after refresh before retrying
                    continue # Go to next attempt in the while loop
                except Exception:
                    # No 403 error, proceed
                    pass

                # --- Extract "Other" Data ---
                # Check if other data file already exists
                if not other_path.exists():
                    try:
                        print(f"Extracting other data for {sdbs_no}...")
                        # Find the table containing compound information
                        info_table = driver.find_element(By.CSS_SELECTOR, "table.MainTable")
                        rows = info_table.find_elements(By.TAG_NAME, "tr")
                        other_data = {}
                        for row in rows:
                            cells = row.find_elements(By.TAG_NAME, "td")
                            if len(cells) == 2:
                                key = cells[0].text.strip().replace(':', '')
                                value = cells[1].text.strip()
                                other_data[key] = value

                        # Save the extracted data
                        with open(other_path, 'w') as f:
                            for key, value in other_data.items():
                                f.write(f"{key}: {value}\n")
                        print(f"Saved other data for {sdbs_no} to {other_path}")
                    except Exception as data_ex:
                        print(f"Could not extract other data for {sdbs_no}: {data_ex}")
                        # Decide if you want to continue without other data or mark as failed
                        # For now, we'll continue to try and get the images

                # --- Find and Process Spectrum Links ---
                spectrum_links_to_download = {
                        'KBr': False,
                        'nujol': False,
                        'liquid': False
                } 

                # Extract the related pages links
                related_pages_elements = driver.find_elements(By.CSS_SELECTOR, "#RelatedpagesLink > a")
                base = driver.current_url

                for link_element in related_pages_elements:
                    link_text = link_element.text
                    link_url = link_element.get_attribute('href')
                    if "IR : KBr" in link_text:
                        spectrum_links_to_download['KBr'] = True
                        # print(f"Found KBr link for {sdbs_no}: {link_url}")
                    elif "IR : nujol" in link_text:
                        spectrum_links_to_download['nujol'] = True
                        print(f"Found nujol link for {sdbs_no}: {link_url}")
                    elif "IR : liquid" in link_text:
                        spectrum_links_to_download['liquid'] = True
                        print(f"Found liquid link for {sdbs_no}: {link_url}")


                # Check if we found the links we need
                downloaded_count = 0
                required_mediums = [key if value else None for key, value in spectrum_links_to_download.items()]

                for medium, has_medium in spectrum_links_to_download.items():
                    if not has_medium:
                        print(f"No {medium} spectrum link found for {sdbs_no}. Skipping...")
                        continue

                    output_path = IMAGE_DIR / f"{sdbs_no}_{medium}.gif"
                    if output_path.exists():
                        print(f"Image {output_path} already exists. Skipping download.")
                        downloaded_count += 1
                        continue

                    try:

                        print(f"Processing {medium} spectrum link for {sdbs_no}...")
                        # --- Find the specific link element AGAIN ---
                        # (Necessary because we might have navigated away and back, or the DOM changed)
                        related_pages_elements = driver.find_elements(By.CSS_SELECTOR, "#RelatedpagesLink > a")
                        found_link = False
                        for link_element in related_pages_elements:
                            link_text = link_element.text

                            if f"IR : {medium}" in link_text:
                                print(f"Clicking link for {medium}...")
                                link_element.click()
                                found_link = True
                                break
                        if not found_link:
                            print(f"Could not re-find link for {medium} on page {driver.current_url}. Skipping medium.")
                            continue # Skip this medium

                        # --- Wait briefly and handle agreement ---
                        sleep(1) # Small pause for page transition initiated by click
                        try:
                            # Use a short wait for the button to be clickable
                            agreement_button = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((By.ID, "UseSDBSButton"))
                            )
                            # print("Found agreement on spectrum page, clicking...")
                            # Using ActionChains can sometimes be more reliable
                            ActionChains(driver).move_to_element(agreement_button).click().perform()
                            # print("Clicked agreement button.")
                            sleep(0.5) # Pause after clicking agreement
                        except Exception:
                            # Agreement not found, already accepted, or timed out - proceed
                            # print("Agreement button not found or not needed.")
                            pass

                        # --- Wait for and download image ---
                        wait = WebDriverWait(driver, 15) # Increased wait time for image
                        # print(f"Waiting for image element for {medium}...")
                        img_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".MainBody > div > img")))

                        img_src = img_element.get_attribute("src")

                        print(f"Downloading {medium} image for {sdbs_no} from {img_src}")
                        download_image(img_src, output_path)
                        print(f"Successfully downloaded {output_path}")
                        downloaded_count += 1
                        sleep(0.5) # Small delay between downloads

                    except Exception as img_ex:
                        print(f"Error processing {medium} spectrum for {sdbs_no}: {img_ex}")
                        # Optionally remove the failed output path if it was partially created
                        if output_path.exists():
                            try:
                                os.remove(output_path)
                            except OSError as rm_err:
                                print(f"Error removing potentially incomplete file {output_path}: {rm_err}")
                    finally:
                        # --- Navigate back to base page BEFORE next medium ---
                        # Ensures we start from the compound page for the next medium type
                        print(f"Returning to base page for {sdbs_no} after attempting {medium}.")
                        driver.get(base)
                        sleep(1) # Allow base page to load before next medium loop iteration


                # Check if all required images were downloaded (or already existed)
                # And if the other data file exists
                if downloaded_count == len(required_mediums) and other_path.exists():
                     processed = True # Mark as successfully processed only if all parts are done
                     print(f"Successfully processed {sdbs_no} (all required images and data present).")
                else:
                    print(f"Incomplete processing for {sdbs_no}. Downloaded {downloaded_count}/{len(required_mediums)} images. Other data exists: {other_path.exists()}")
                    # Keep processed = False, so it might be retried if attempts remain

            except Exception as e:
                # Catch errors during the main page loading or initial data extraction phase
                print(f"Error processing {sdbs_no} on attempt {attempts}/{max_retries}: {e}")
                if attempts >= max_retries:
                    print(f"Failed to process {sdbs_no} after {max_retries} attempts.")
                else:
                    sleep(2) # Wait a bit before the next attempt if it wasn't a 403

        # Optional: Add a small delay between processing different IDs to be less aggressive
        # sleep(0.5)

    # --- End of the for loop for sdbs_no ---

    # Quit the driver AFTER the loop finishes processing all IDs for this process
    print("Finished processing all assigned IDs. Quitting WebDriver.")
    try:
        driver.quit()
    except NameError:
         # This might happen if the 'ids' list was empty for this process
         print("Driver was not initialized (likely no IDs assigned to this process).")
         pass
    except Exception as quit_error:
        print(f"Error quitting driver: {quit_error}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape IR spectra images and data from SDBS.")
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
    try:
        with open("../sdbs_dataset/sdbs_ids.txt", "r") as ids_file:
            for id_line in ids_file:
                all_ids.append(id_line.strip())
    except FileNotFoundError:
        print("Error: ../sdbs_dataset/sdbs_ids.txt not found.")
        exit(1)

    if not all_ids:
        print("No IDs found in sdbs_ids.txt. Exiting.")
        exit(0)

    if args.single_process:
        print("Running in single-process mode.")
        # Pass the headless argument to get_gif
        get_gif(all_ids, headless=args.headless)
    else:
        cores_to_use = args.cores
        print(f"Running in multiprocessing mode with {cores_to_use} processes.")
        # Distribute IDs among processes
        ids_per_process = [[] for _ in range(cores_to_use)]
        for i, sdbs_id in enumerate(all_ids):
            ids_per_process[i % cores_to_use].append(sdbs_id)

        processes = []
        for i in range(cores_to_use):
            if not ids_per_process[i]: # Don't start a process if it has no IDs
                continue
            # Pass the headless argument to the target function
            p = multiprocessing.Process(target=get_gif, args=(ids_per_process[i], args.headless))
            processes.append(p)
            p.start()

        # Wait for all processes to finish
        for p in processes:
            p.join()

        print("All multiprocessing processes finished.")
    
