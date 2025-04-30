from selenium import webdriver
from selenium.webdriver.common.by import By
from time import sleep
import urllib.request
import multiprocessing
from pathlib import Path

Path("../sdbs_dataset/sdbs_images").mkdir(parents=True, exist_ok=True)

def download_image(url, save_as):
    urllib.request.urlretrieve(url, save_as)

def get_gif(ids):
    # start in headless mode
    # options = webdriver.ChromeOptions()
    # options.add_argument('--headless')
    # driver = webdriver.Chrome(options=options)
    driver = webdriver.Chrome()

    BASE_URL = "https://sdbs.db.aist.go.jp/SearchInformation.aspx"
    driver.get(BASE_URL)
    # check if there is an agreement to accept
    agreement_box = driver.find_element(by=By.CSS_SELECTOR, value=".DisclaimeraAcceptClass")
    if agreement_box.is_displayed():
        # scroll to the bottom of the page
        print("Found agreement to accept")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        sleep(1)
        agreement_button = driver.find_element(by=By.CSS_SELECTOR, value=".DisclaimeraAcceptClass > input")
        agreement_button.click()
        print("Agreement accepted")

    driver.set_window_size(1920, 1920)

    # driver.implicitly_wait(1)
    for sdbs_no in ids:

        try:
            sdbs_no_text_box = driver.find_element(by=By.ID, value="BodyContentPlaceHolder_INP_sdbsno")
            search_btn = driver.find_element(by=By.ID, value="BodyContentPlaceHolder_SearchButton")

            sdbs_no_text_box.send_keys(sdbs_no)
            search_btn.click()

            ir_data_btn = driver.find_element(by=By.CSS_SELECTOR, value=".ir-val > a")
            ir_data_btn.click()


            driver.implicitly_wait(1)
            img_element = driver.find_element(by=By.CSS_SELECTOR, value=".MainBody > div > img")
            img_src = img_element.get_attribute("src")

            print(sdbs_no, img_src)
            download_image(img_src, "../sdbs_dataset/sdbs_images/" + sdbs_no + ".gif")
        except Exception as e:
            print(e)

        driver.get(BASE_URL)

    driver.quit()


if __name__ == "__main__":
    # get the number of cores in the system
    cores = multiprocessing.cpu_count() - 1

    ids = []
    for i in range(cores):
        ids.append([])
    ids_file = open("../sdbs_dataset/sdbs_ids.txt", "r")

    for i, id in enumerate(ids_file):
        ids[i % cores].append(id.strip())
    ids_file.close()

    for i in range(cores):
        p = multiprocessing.Process(target=get_gif, args=(ids[i],))
        p.start()
