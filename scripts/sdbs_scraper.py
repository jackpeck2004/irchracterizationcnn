from selenium import webdriver
from selenium.webdriver.common.by import By
from time import sleep

driver = webdriver.Chrome()

URL = "https://sdbs.db.aist.go.jp/"
driver.get(URL)

title = driver.title

driver.set_window_size(1920, 1920)

driver.implicitly_wait(1)

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

sdbs_no_text_box = driver.find_element(by=By.ID, value="BodyContentPlaceHolder_INP_sdbsno")
search_btn = driver.find_element(by=By.ID, value="BodyContentPlaceHolder_SearchButton")

sdbs_no = "1"
sdbs_no_text_box.send_keys(sdbs_no)
search_btn.click()

ir_data_btn = driver.find_element(by=By.CSS_SELECTOR, value=".ir-val > a")
ir_data_btn.click()

img_element = driver.find_element(by=By.CSS_SELECTOR, value=".MainBody > div > img")
img_src = img_element.get_attribute("src")

print(sdbs_no, img_src)

driver.quit()
