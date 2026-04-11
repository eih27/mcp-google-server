"""
Thin wrappers around Google API service builders.
Suppresses the noisy file_cache warning from the discovery client.
"""

import logging

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# The Google client library warns about file_cache on every request in some envs.
logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)


def gmail_service(credentials: Credentials):
    return build("gmail", "v1", credentials=credentials)


def calendar_service(credentials: Credentials):
    return build("calendar", "v3", credentials=credentials)
