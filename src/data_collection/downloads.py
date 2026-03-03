"""Download helpers for PDF assets."""

from __future__ import annotations

import os
import time
from pydantic import HttpUrl
from selenium import webdriver


def download_pdf(lnk: HttpUrl) -> str:
    """Download a PDF from a link using Selenium.

    Returns the filename of the downloaded PDF.
    """
    options = webdriver.ChromeOptions()
    download_folder = os.path.join(os.getcwd(), "tmp")
    profile = {
        "plugins.plugins_list": [{"enabled": False, "name": "Chrome PDF Viewer"}],
        "download.default_directory": download_folder,
        "download.extensions_to_open": "",
        "plugins.always_open_pdf_externally": True,
    }
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_experimental_option("prefs", profile)
    driver = webdriver.Chrome(options=options)
    driver.get(str(lnk))

    filename = str(lnk).split("/")[-1]
    time.sleep(3)
    driver.close()
    return filename
