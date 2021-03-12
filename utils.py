import json
import os
import pickle
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from sys import platform

import numpy as np
import requests
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys


def create_browser(driver_path):
    options = webdriver.ChromeOptions()
    options.headless = bool(1 - int(os.getenv("DEBUG", 0)))
    options.add_argument("--no-sandbox")
    options.add_argument("disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("window-size=1920,1080")
    browser = webdriver.Chrome(executable_path=driver_path, options=options)
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


def df_to_sheet(df):
    df_columns = [np.array(df.columns)]
    df_values = df.values.tolist()
    sheet = np.concatenate((df_columns, df_values)).tolist()
    return sheet


def make_gsheets_service():
    creds = None
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    token_path = os.path.join("credentials", "token.pickle")
    if os.path.exists(token_path):
        with open(token_path, "rb") as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                os.path.join("credentials", "credentials.json"), SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(token_path, "wb") as token:
            pickle.dump(creds, token)
    service = build("sheets", "v4", credentials=creds)
    return service


def fetch_sheet(sheet_id, range_):
    # sheet_id: 1ug5AYylGKym3kog-AfT7sQusZ8sFDs9Xc77c4rrK-gg
    # range_: 'A:D'
    service = make_gsheets_service()
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=sheet_id, range=range_).execute()
    values = result.get("values", [])
    return values


def sheet2schools(sheet_info):
    # [
    #     ["yale", "1483912085183985", "yalehousing"],
    #     ["brown", "683411031786289"],
    #     ["bc", "1435056483467446"],
    #     ["tufts", "1552232378374052"],
    # ]
    result = {row[0]: row[1:] for row in sheet_info}
    return result


def share_and_get_link(file_id):
    SCOPES = ["https://www.googleapis.com/auth/drive"]
    """Shows basic usage of the Drive v3 API.
    Prints the names and ids of the first 10 files the user has access to.
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    drive_token_path = os.path.join("credentials", "drive_token.pickle")
    if os.path.exists(drive_token_path):
        with open(drive_token_path, "rb") as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                os.path.join("credentials", "drive_credentials.json"), SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(drive_token_path, "wb") as token:
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
            fileId=file_id, body=user_permission, fields="id",
        )
    )
    r = batch.execute()

    # Get Link
    file = drive_service.files().get(fileId=file_id, fields="webViewLink").execute()
    # print(file)
    return file["webViewLink"]


def create_bitly(sheet_url):
    access_token = "afc8f422a47ebadd6ec8ff786316f6b3167bf5b4"

    url = "https://api-ssl.bitly.com/v4/shorten"
    data = {"long_url": sheet_url, "domain": "bit.ly"}
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    response = requests.post(url, data=json.dumps(data), headers=headers,)
    return response.json()["link"]


def create_sheet(df, school):
    service = make_gsheets_service()

    # Create new spreadsheet with title and save id
    datestamp = datetime.now().strftime("%m/%d/%y")
    spreadsheet = {
        "properties": {"title": f"{school.capitalize()} Sublet Sorter {datestamp}"}
    }
    spreadsheet = (
        service.spreadsheets()
        .create(body=spreadsheet, fields="spreadsheetId")
        .execute()
    )

    source_spreadsheet_id = "1as_XNiQIXq2AcECHurzxao138udJLo7h6g4wJmYn2Po"
    target_spreadsheet_id = spreadsheet.get("spreadsheetId")
    worksheet_id = "245692157"

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


def send_email(text, cc=[]):
    # email config
    port = 465
    email = "host.rerent@gmail.com"
    password = os.environ["EMAIL_PASSWORD"]
    smtp_server = "smtp.gmail.com"

    # email content
    message = EmailMessage()
    message.set_content(text)
    message["Subject"] = "Sublet Sorter"
    message["From"] = email
    message["To"] = ["abarclay321@gmail.com"]
    message["CC"] = cc

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
        server.login(email, password)
        server.send_message(message)
