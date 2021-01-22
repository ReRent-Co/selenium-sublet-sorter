import argparse
import os
from sys import platform
import requests, json

import pandas as pd
import numpy as np
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys
from datetime import datetime
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from utils import (
    clean_name_url,
    clean_post_url,
    clean_title,
    parse_date,
    parse_price,
    df_to_sheet,
)


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

        self.school_group_id = {
            "yale": "1483912085183985",
            "brown": "683411031786289",
        }
        assert self.school in {
            "yale",
            "brown",
            "all",
        }, "`school` not in list!"
        self.num_posts = args.num_posts
        self.browser = create_browser()
        self.SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

        # Sublet Sorter Template sheet and worksheet id
        self.template_sheet_id = "1as_XNiQIXq2AcECHurzxao138udJLo7h6g4wJmYn2Po"
        self.worksheet_id = "245692157"

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
        base_link = "https://mbasic.facebook.com/groups/"
        self.browser.get(f"{base_link}{self.school_group_id[self.school]}/")

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
        # df.to_excel(f"{self.school}_parsed.xlsx", index=False)
        # df.to_csv("result.csv")
        return df

    def create_sheet(self, df):
        creds = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists("token.pickle"):
            with open("token.pickle", "rb") as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", self.SCOPES
                )
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open("token.pickle", "wb") as token:
                pickle.dump(creds, token)

        service = build("sheets", "v4", credentials=creds)

        # Create new spreadsheet with title and save id
        datestamp = datetime.now().strftime("%m/%d/%y")
        spreadsheet = {
            "properties": {
                "title": f"{self.school.capitalize()} Sublet Sorter {datestamp}"
            }
        }
        spreadsheet = (
            service.spreadsheets()
            .create(body=spreadsheet, fields="spreadsheetId")
            .execute()
        )

        source_spreadsheet_id = self.template_sheet_id
        target_spreadsheet_id = spreadsheet.get("spreadsheetId")
        worksheet_id = self.worksheet_id

        # Copy Template into spreadsheet
        sheet = service.spreadsheets()

        request = sheet.sheets().copyTo(
            spreadsheetId=source_spreadsheet_id,
            sheetId=worksheet_id,
            body={"destinationSpreadsheetId": target_spreadsheet_id},
        )
        request.execute()

        body = {"requests": [{"deleteSheet": {"sheetId": 0}}]}
        request = sheet.batchUpdate(spreadsheetId=target_spreadsheet_id, body=body)
        response = request.execute()

        # Prepare Data
        values = df_to_sheet(df)[1:]
        body = {"values": values}
        range_to = str(4 + len(values))

        # Copy data into sheet
        service.spreadsheets().values().update(
            spreadsheetId=target_spreadsheet_id,
            range=f"A4:H{range_to}",
            valueInputOption="USER_ENTERED",
            body=body,
        ).execute()

        return target_spreadsheet_id

    def share_and_get_link(self, file_id):
        SCOPES = ["https://www.googleapis.com/auth/drive"]

        """Shows basic usage of the Drive v3 API.
        Prints the names and ids of the first 10 files the user has access to.
        """
        creds = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists("drive_token.pickle"):
            with open("drive_token.pickle", "rb") as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "drive_credentials.json", SCOPES
                )
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open("drive_token.pickle", "wb") as token:
                pickle.dump(creds, token)

        drive_service = build("drive", "v3", credentials=creds)

        def callback(request_id, response, exception):
            if exception:
                # Handle error
                # print(exception)
                pass
            else:
                # print("Permission Id: %s" % response.get("id"))
                pass

        batch = drive_service.new_batch_http_request(callback=callback)
        user_permission = {
            "type": "anyone",
            "role": "writer",
        }
        batch.add(
            drive_service.permissions().create(
                fileId=file_id,
                body=user_permission,
                fields="id",
            )
        )
        r = batch.execute()

        # Get Link
        file = drive_service.files().get(fileId=file_id, fields="webViewLink").execute()
        # print(file)
        return file["webViewLink"]

    def create_bitly(self, sheet_url):
        access_token = "afc8f422a47ebadd6ec8ff786316f6b3167bf5b4"

        url = "https://api-ssl.bitly.com/v4/shorten"
        data = {"long_url": sheet_url, "domain": "bit.ly"}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        response = requests.post(
            url,
            data=json.dumps(data),
            headers=headers,
        )
        return response.json()["link"]

    def main(self):
        self.login()

        if self.school != "all":
            self.school_group_id = {self.school: self.school_group_id[self.school]}
            print(self.school_group_id)

        for school in self.school_group_id:
            self.school = school
            if school != "all":
                self.browse_group()
                df = self.scrape_posts()
                file_id = self.create_sheet(df)
                sheet_url = self.share_and_get_link(file_id)
                bitly_url = self.create_bitly(sheet_url)
                print(f"{self.school}: {bitly_url}")

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
