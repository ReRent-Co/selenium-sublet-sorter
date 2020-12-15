import argparse
import os
from sys import platform

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.keys import Keys


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
    profile = (
        post.find_element_by_tag_name("h3")
        .find_element_by_tag_name("a")
        .get_attribute("href")
    )
    title = (
        post.find_element_by_xpath("//div[@class='ek']")
        .find_elements_by_tag_name("span")[1]
        .text
    )
    location = post.find_element_by_xpath("//span[@class='eo']").text
    p_tags = post.find_element_by_xpath("//div[@class='ep']").find_elements_by_tag_name(
        "p"
    )
    text = " ".join(p.text for p in p_tags)
    bottom_links = post.find_elements_by_xpath("//div[@class='cp cq']")[
        -1
    ].find_elements_by_tag_name("a")
    link = ""
    for candidate in bottom_links:
        if candidate.get_attribute("text") == "Full Story":
            link = candidate.get_attribute("href")
            break
    return {
        "profile": profile,
        "title": title,
        "location": location,
        "text": text,
        "link": link,
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

    def scrape_posts(self):
        count = 0
        result = []
        while count < self.num_posts:
            print(len(result))
            posts = self.browser.find_elements_by_tag_name("article")
            print(posts)
            for post in posts:
                print("here!")
                result.append(parse_post(post))
                count += 1
            # self.browser.find_element_by_id(
            #     "m_group_stories_container"
            # ).find_element_by_xpath("//div/span").click()
        df = pd.DataFrame(result)
        df.to_csv("result.csv")

    def main(self):
        self.login()
        self.browse_group()
        self.scrape_posts()


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
        default=30,
        help="how many posts to scrape",
    )
    args = parser.parse_args()
    sublet_sorter = SubletSorter(args)
    sublet_sorter.main()
