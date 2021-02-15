import argparse
import os

import pandas as pd
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from selenium.common.exceptions import NoSuchElementException

from preprocess import (
    clean_name_url,
    clean_post_url,
    clean_title,
    parse_date,
    parse_price,
)
from utils import (
    create_bitly,
    create_browser,
    create_sheet,
    parse_post,
    send_email,
    share_and_get_link,
)


class SubletSorter:
    def __init__(self, args):
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

    def browse_group(self, school_id):
        base_link = "https://mbasic.facebook.com/groups/"
        self.browser.get(f"{base_link}{school_id}/")

    def remove(self, element):
        self.browser.execute_script(
            "var element = arguments[0];element.parentNode.removeChild(element);",
            element,
        )

    def scrape_posts(self):
        count = 0
        result = []
        descriptions = set()
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
                    description = parsed["Description"]

                    if not description or description not in descriptions:
                        result.append(parsed)
                        descriptions.add(description)
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
        return df

    def main(self):
        school_group_id = {
            "yale": "1483912085183985",
            "brown": "683411031786289",
        }
        text = ""
        self.login()
        for school, school_id in school_group_id.items():
            self.browse_group(school_id)
            df = self.scrape_posts()
            file_id = create_sheet(df, school)
            sheet_url = share_and_get_link(file_id)
            bitly_url = create_bitly(sheet_url)
            text += f"{school.capitalize()}: {bitly_url}\n"
        send_email(text)
        self.browser.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--num_posts", type=int, default=200, help="how many posts to scrape",
    )
    args = parser.parse_args()
    sublet_sorter = SubletSorter(args)
    sublet_sorter.main()
