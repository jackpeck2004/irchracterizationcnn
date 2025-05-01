from logging import exception
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from time import sleep
import urllib.request
import multiprocessing
from pathlib import Path
import os # Import the os module for path checking

IMAGE_DIR = Path("../sdbs_dataset/sdbs_images")
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

error_title = '//*[@id="content"]/div/fieldset/h2'

def download_image(url, save_as):
    urllib.request.urlretrieve(url, save_as)

def get_gif(ids):
    # start in headless mode
    # options = webdriver.ChromeOptions()
    # options.add_argument('--headless')
    # driver = webdriver.Chrome(options=options)
    # driver = webdriver.Chrome() # Moved inside the loop

    BASE_URL = "https://sdbs.db.aist.go.jp/SearchInformation.aspx"
    # driver.get(BASE_URL) # Moved inside the loop
    # sleep(1) # Moved inside the loop

    # driver.set_window_size(1920, 1920)

    # driver.implicitly_wait(1) # Implicit waits can sometimes cause issues with dynamic pages. Consider explicit waits if problems persist.
    max_retries = 3
    retry_delay_seconds = 5 # Wait time after a 403 refresh

    # Initialize driver ONCE before the loop
    print(f"Initializing WebDriver for process handling {len(ids)} IDs...")
    driver = webdriver.Chrome()
    # Consider adding options like headless mode back here if needed
    # options = webdriver.ChromeOptions()
    # options.add_argument('--headless')
    # driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(2) # Set implicit wait once for the driver instance
    print("WebDriver initialized.")

    for sdbs_no in ids:
        # Construct the expected output file path FIRST
        output_path = IMAGE_DIR / f"{sdbs_no}.gif"

        # Check if the image file already exists
        if output_path.exists():
            print(f"Image for {sdbs_no} already exists. Skipping.")
            continue # Move to the next ID

        # File doesn't exist, proceed with processing using the shared driver
        print(f"Processing {sdbs_no}...")

        attempts = 0
        processed = False
        while attempts < max_retries and not processed:
            attempts += 1
            try:
                # Start from the base URL for each attempt *within the while loop*
                # This handles cases where a previous attempt within the while loop failed
                # after navigating away from the base URL.
                driver.get(BASE_URL)
                sleep(1) # Allow initial load

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

                # Check if there is an agreement to accept
                try:
                    agreement_box = driver.find_element(by=By.CSS_SELECTOR, value=".DisclaimeraAcceptClass")
                    print("Found agreement to accept")
                    ActionChains(driver).move_to_element(agreement_box).perform()
                    sleep(1)
                    agreement_button = driver.find_element(by=By.CSS_SELECTOR, value=".DisclaimeraAcceptClass > input")
                    agreement_button.click()
                    print("Agreement accepted")
                except Exception:
                    # Agreement not found or already accepted
                    pass

                # Search for SDBS No
                sdbs_no_text_box = driver.find_element(by=By.ID, value="BodyContentPlaceHolder_INP_sdbsno")
                search_btn = driver.find_element(by=By.ID, value="BodyContentPlaceHolder_SearchButton")
                sdbs_no_text_box.clear()
                sdbs_no_text_box.send_keys(sdbs_no)
                search_btn.click()
                sleep(1) # Wait for search results page

                # Click IR data link
                ir_data_btn = driver.find_element(by=By.CSS_SELECTOR, value=".ir-val > a")
                ir_data_btn.click()
                sleep(1) # Wait for IR data page

                # Download image
                # Consider using explicit wait here for robustness
                # from selenium.webdriver.support.ui import WebDriverWait
                # from selenium.webdriver.support import expected_conditions as EC
                # wait = WebDriverWait(driver, 10)
                # img_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".MainBody > div > img")))
                driver.implicitly_wait(2) # Using implicit wait as per original code for now
                img_element = driver.find_element(by=By.CSS_SELECTOR, value=".MainBody > div > img")
                img_src = img_element.get_attribute("src")

                print(f"{sdbs_no}: {img_src}")
                # Use the defined output_path variable
                download_image(img_src, output_path)
                processed = True # Mark as successfully processed

            except Exception as e:
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
    #get the number of cores in the system
    cores = 4

    ids = []
    for i in range(cores):
        ids.append([])
    ids_file = open("../sdbs_dataset/sdbs_ids.txt", "r")

    for i, id in enumerate(ids_file):
        ids[i % cores].append(id.strip())
        # ids.append(id.strip())
    ids_file.close()

    # get_gif(ids)

    for i in range(cores):
        p = multiprocessing.Process(target=get_gif, args=(ids[i],))
        p.start()
    
