#!/bin/bash

pip3 install pipenv
pipenv install -r requirements.txt
pipenv run python main.py --num_posts=$1 --driver_path=$2