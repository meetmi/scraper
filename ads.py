import json
import time
import random
import undetected_chromedriver as uc

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ---------------- LOAD LINKS ----------------

with open("reply_urls.json", "r") as f:
    links = json.load(f)

print(f"[START] Loaded {len(links)} links")

# ---------------- RANDOM DATA ARRAYS ----------------

names = [
    "Mbali",
    "Senzo",
    "John",
    "Mike",
    "Sarah",
    "Amanda"
]

emails = [
    "info@istoko.co.za"
]

messages = [
    
    "Hi there, have you tried Istoko website for meetups?"
]

# ---------------- CHROME OPTIONS ----------------

options = uc.ChromeOptions()

options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = uc.Chrome(
    options=options,
    use_subprocess=True
)

wait = WebDriverWait(driver, 30)

# ---------------- LOOP LINKS ----------------

for index, url in enumerate(links, start=1):

    # RANDOMIZE DATA
    random_name = random.choice(names)
    random_email = random.choice(emails)
    random_message = random.choice(messages)

    print(f"\n[OPENING {index}] {url}")
    print(f"[USING] {random_name} | {random_email}")

    try:
        driver.get(url)

        wait.until(
            lambda d: d.execute_script(
                "return document.readyState"
            ) == "complete"
        )

        time.sleep(3)

    except Exception as e:
        print("[ERROR] Page load failed:", e)
        continue

    # ---------------- CHECK FORM / REPLY ----------------

    try:
        form_ready = driver.find_elements(By.ID, "name_from")

        if form_ready:
            print("[OK] Form already open")
        else:
            print("[STEP] Trying Reply button")

            reply_clicked = False

            possible_selectors = [
                (By.XPATH, "//a[contains(.,'Reply')]"),
                (By.XPATH, "//button[contains(.,'Reply')]"),
                (By.LINK_TEXT, "Reply"),
                (By.PARTIAL_LINK_TEXT, "Reply")
            ]

            for by, sel in possible_selectors:
                try:
                    el = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((by, sel))
                    )

                    el.click()

                    print("[OK] Reply clicked")

                    reply_clicked = True
                    break

                except:
                    continue

            if not reply_clicked:
                print("[ERROR] Reply button not found")
                continue

        time.sleep(2)

    except Exception as e:
        print("[ERROR] Reply detection:", e)
        continue

    # ---------------- NAME ----------------

    try:
        name_field = wait.until(
            EC.presence_of_element_located(
                (By.ID, "name_from")
            )
        )

        name_field.clear()
        name_field.send_keys(random_name)

        print("[OK] Name filled")

    except Exception as e:
        print("[ERROR] Name field:", e)

    # ---------------- EMAIL ----------------

    try:
        email_field = driver.find_element(
            By.ID,
            "email_from"
        )

        email_field.clear()
        email_field.send_keys(random_email)

        print("[OK] Email filled")

    except Exception as e:
        print("[ERROR] Email field:", e)

    # ---------------- MESSAGE ----------------

    try:
        msg_field = driver.find_element(
            By.ID,
            "text"
        )

        msg_field.clear()
        msg_field.send_keys(random_message)

        print("[OK] Message filled")

    except Exception as e:
        print("[ERROR] Message field:", e)

    # ---------------- CAPTCHA ----------------

    print("[STEP] Solve CAPTCHA manually...")

    while True:
        try:
            captcha_value = driver.find_element(
                By.ID,
                "is_captcha_solved"
            ).get_attribute("value")

            if captcha_value == "1":
                print("[OK] CAPTCHA solved!")
                break

        except:
            pass

        time.sleep(1)

    # ---------------- SUBMIT ----------------

    try:
        submit_btn = driver.find_element(
            By.ID,
            "submit"
        )

        submit_btn.click()

        print("[SENT] Form submitted!")

    except Exception as e:
        print("[ERROR] Submit failed:", e)

    # RANDOM HUMAN-LIKE DELAY
    sleep_time = random.randint(3, 8)

    print(f"[WAITING] {sleep_time}s")

    time.sleep(sleep_time)

# ---------------- FINISH ----------------

driver.quit()

print("[DONE] All links processed")