# This file contains configuration settings for the application.
# In realistc applications, sensitive information like API keys should not be hardcoded.
SECRET_KEY = "6bffb7fcb26f966baf5b31e6ecc5ded8e69800ba63e562838d3e53364ed7e552"

import os
from dotenv import load_dotenv
load_dotenv()

SQLALCHEMY_DATABASE_URI = os.getenv("DB_URL")
SQLALCHEMY_TRACK_MODIFICATIONS = False