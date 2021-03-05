import os

import flask

app = flask.Flask(__name__)

app.run(os.environ.get("PORT"))
