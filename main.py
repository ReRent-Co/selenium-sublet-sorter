import argparse
import os
from sys import platform

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys

from utils import clean_name_url, clean_post_url, clean_title, parse_date, parse_price


def create_browser():
    options = webdriver.ChromeOptions()
    options.headless = bool(1 - int(os.getenv("DEBUG", 1)))
    options.add_argument("--no-sandbox")
    options.add_argument("disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("window-size=1920,1080")
    try:
        driver_path = (
            "/usr/local/share/chromedriver"
            if platform == "linux"
            else "/Users/jaketae/opt/chrome/chromedriver"
        )
        browser = webdriver.Chrome(
            executable_path=driver_path,
            options=options,
        )
    except Exception as e:
        browser = webdriver.Chrome(options=options)
    return browser


def parse_post(post):
    h3_tag = post.find_element_by_tag_name("h3")
    if h3_tag.text == "Suggested Groups":
        return
    profile = h3_tag.find_element_by_tag_name("a").get_attribute("href")
    title = (
        post.find_element_by_xpath("./div/div/div/div")
        .find_elements_by_tag_name("span")[1]
        .text
    )
    price = post.find_element_by_xpath("./div/div/div/div[2]/div").text
    date = post.find_element_by_xpath("./footer/div/abbr").text
    location = post.find_element_by_xpath("./div/div/div/div[3]").text
    p_tags = post.find_element_by_xpath(
        "./div/div/div/div[4]"
    ).find_elements_by_tag_name("p")
    text = " ".join(p.text for p in p_tags).replace("\n", " ")
    name = post.find_element_by_xpath("//header/h3/span/strong/a").text
    bottom_links = post.find_elements_by_xpath("//footer/div")[
        1
    ].find_elements_by_tag_name("a")
    link = ""
    for candidate in bottom_links:
        if candidate.get_attribute("text") == "Full Story":
            link = candidate.get_attribute("href")
            break
    return {
        "Name": name,
        "Profile URL": profile,
        "Title": title,
        "Price": price,
        "Area": location,
        "Description": text,
        "Date": date,
        "Post URL": link,
    }


class SubletSorter:
    def __init__(self, args):
        self.school = args.school.lower()
        assert self.school in {
            "yale",
            "brown",
        }, "`school` must be one of 'yale' or 'brown'"
        self.num_posts = args.num_posts
        self.browser = create_browser()

    def login(self):
        self.browser.get("https://mbasic.facebook.com")
        self.browser.find_element_by_id("m_login_email").send_keys(
            os.getenv("FACEBOOK_USERNAME")
        )
        self.browser.find_element_by_xpath("//input[@type='password']").send_keys(
            os.getenv("FACEBOOK_PASSWORD")
        )
        self.browser.find_element_by_xpath("//input[@name='login']").click()

    def browse_group(self):
        if self.school == "yale":
            self.browser.get("https://mbasic.facebook.com/groups/1483912085183985/")
        elif self.school == "brown":
            self.browser.get("https://mbasic.facebook.com/groups/683411031786289/")

    def remove(self, element):
        self.browser.execute_script(
            "var element = arguments[0];element.parentNode.removeChild(element);",
            element,
        )

    def scrape_posts(self):
        count = 0
        result = []
        link = None
        while count < self.num_posts:
            if link is None:
                link = (
                    self.browser.find_element_by_id("m_group_stories_container")
                    .find_element_by_xpath("./div/a")
                    .get_attribute("href")
                )
                # remove Kopa post
                self.remove(self.browser.find_element_by_tag_name("article"))
            try:
                post = self.browser.find_element_by_tag_name("article")
            except NoSuchElementException:
                self.browser.get(link)
                link = None
                continue
            try:
                parsed = parse_post(post)
                if parsed:
                    result.append(parsed)
                    count += 1
            except Exception as e:
                print(e)
            self.remove(post)
        df = pd.DataFrame(result)
        df = df[df["Price"].apply(parse_price) > 450]
        df = df[df["Price"].apply(parse_price) < 15000]
        df["Price"] = df["Price"].apply(lambda p: f"${parse_price(p)}")
        df["Date"] = df["Date"].apply(parse_date)
        df["Profile URL"] = df["Profile URL"].apply(clean_name_url)
        df["Post URL"] = df["Post URL"].apply(clean_post_url)
        df["Title"] = df["Title"].apply(clean_title)
        df.to_excel("parsed.xlsx", index=False)
        # df.to_csv("result.csv")

    def main(self):
        self.login()
        self.browse_group()
        self.scrape_posts()
        self.browser.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--school",
        type=str,
        default="yale",
        help="which school housing group to scrape",
    )
    parser.add_argument(
        "--num_posts",
        type=int,
        default=200,
        help="how many posts to scrape",
    )
    args = parser.parse_args()
    sublet_sorter = SubletSorter(args)
    sublet_sorter.main()
