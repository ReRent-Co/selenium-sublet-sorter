# Selenium Sublet Sorter

This repository contains code for selenium sublet sorter.

## Introduction

Sublet Sorter is an internal ReRent project that seeks to make subletting, leasing, and housing search easier for students. A lot of properties are currently being shared on college-specific housing Facebook groups, such as the [Yale Housing Group](https://www.facebook.com/groups/yalehousing). While these groups allow students to reach a wider audience, they are somewhat hindered by the fact that searching and sorting housing items is very difficult or near impossible due to how Facebook group UI's and functionalities are designed. 

Sublet sorter seeks to solve this problem by providing a bird's eye, spreadsheet view of all available listings. Spreadsheets are advantageous for sorting and searching, as it allows items to be listed in specific order, or enables people to apply filters by, for instance, zip code. 

## Setup

Clone this repository. 

```
git clone
```

Install `pipenv` via

```
pip3 install pipenv 
```

Next, activate the `pipenv` shell and install all Python requirements.

```
pipenv shell
pipenv install -r requirements.txt
```

Download an appropriate [Chrome driver](https://chromedriver.chromium.org/downloads) according to the OS and Chrome version of your device. Unzip the driver in an appropriate directory and take note of the full path. 

### Environmental Variables

The app requires the following environmental variables.

```
FACEBOOK_PASSWORD
FACEBOOK_USERNAME
EMAIL_PASSWORD
DEBUG
```

Facebook username and password are self-explanatory; these constitute the credentials of the account with which the program will access the Facebook housing groups. This necessarily means that the account must be registered members of those Facebook groups, the vast majority of which are private.

`EMAIL_PASSWORD` is the password to host.rerent@gmail.com, the ReRent Gmail account. This environmental variable is used to send emails of the completed sublet sorter links. More explanation is available below.

It is recommended that `DEBUG` be set to 1 on your local machine, and 0 on a production server, should this script be run on the cloud or a non-local device. If `DEBUG` is 0, Chrome will run in headless mode, meaning you will not see anything on your screen. If it is set to 1, you will be able to see the script scrape through the Facebook groups. 

## Implementation

The sublet sorter script can be understood as a pipeline that spans the following processes. Note that this process happens multiple times, for each housing group.

1. Scraping posts from a housing group on Facebook
2. Creating a [pandas](https://pandas.pydata.org) DataFrame from scraped information
3. Copying a template spreadsheet from Google Sheets
4. Pasting the pandas DataFrame to the duplicated spreadsheet
5. Generating a [bitly](https://bitly.com) link to the Google sheet
6. Sending an email containing all the bitly links upon process completion

## Execution

To run the script, you must supply two script arguments, `num_posts` and `driver_path`. `num_posts` determines how many posts to scrape per Facebook group. `driver_path` should point to the directory path to the Chrome driver. 

```
usage: main.py [-h] [--num_posts NUM_POSTS] [--driver_path DRIVER_PATH]

optional arguments:
  -h, --help            show this help message and exit
  --num_posts NUM_POSTS
                        how many posts to scrape
  --driver_path DRIVER_PATH
                        chrome driver directory
```

Below is an example command to run the script.

```
python main.py --num_posts=100 --driver_path=/Users/jaketae/opt/chrome/chromedriver
```

After a couple of minutes, the script will send out an email that looks like this:

```
Yale: https://bit.ly/3b4VU5B
Brown: https://bit.ly/3b0XdlY
Bc: https://bit.ly/3bOA1X9
Tufts: https://bit.ly/3bNFqxH
```

By default, the recipient is Alikiah, abarclay321@gmail.com. 