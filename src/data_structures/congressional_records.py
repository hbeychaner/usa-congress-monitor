
from http.client import IncompleteRead
from io import BytesIO
import os
from PyPDF2 import PdfReader
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from requests.exceptions import ChunkedEncodingError
import requests
from requests import Response

from src.data_collection.data_collection import create_session_with_retries, download_pdf


from src.data_structures.other_models import VolumeNumber, IssueNumber

class CongressionalPDFLink(BaseModel):
    """
    A link to a PDF in the Congressional Record, which includes the part number, url, and text
    """
    part: int
    url: HttpUrl
    text: Optional[str] = ""

    def session_get(self, url: str) -> requests.Response:
        session = create_session_with_retries()
        try:
            with session.get(url) as response:
                response.raise_for_status()
                return response
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}")
        except ChunkedEncodingError as chunk_err:
            print(f"Chunked encoding error occurred: {chunk_err}")
        except IncompleteRead as read_err:
            print(f"Incomplete read error occurred: {read_err}")
        except requests.exceptions.RequestException as req_err:
            print(f"Request error occurred: {req_err}")
        except Exception as e:
            print(f"An error occurred: {e}")
        return Response()

    def extract_text_from_pdf(self) -> str:
        text = ""
        response = self.session_get(str(self.url))
        if response is None:
            print(f"Failed to retrieve the PDF from {self.url}")
            try: 
                filename = download_pdf(self.url)
                if filename:
                    with open(filename, "rb") as f:
                        pdf = PdfReader(f)
                        for page in pdf.pages:
                            text += "\n" + page.extract_text() or ""
                    os.remove(filename)
                return text
            except Exception as e:
                print(f"An error occurred: {e}")
                return text
        with response:
            if response.status_code != 403:
                pdf_bytes = BytesIO(response.content)
                pdf = PdfReader(pdf_bytes)
                for page in pdf.pages:
                    text += "\n" + page.extract_text() or ""
                return text
            else:
                print(f"Failed to retrieve the PDF from {self.url}. Attempting with Selenium.")
                filename = download_pdf(self.url)
                if filename:
                    with open(filename, "rb") as f:
                        pdf = PdfReader(f)
                        for page in pdf.pages:
                            text += "\n" + page.extract_text() or ""
                    os.remove(filename)
                return text

    def model_post_init(self, __context):
        if not self.text:
            self.text = self.extract_text_from_pdf()
        return super().model_post_init(__context)


class CongressionalDigest(BaseModel):
    """
    The daily digest of the Congressional Record, which includes the label, ordinal value, pdf links, and full text
    """
    label: str
    ordinal: int
    pdf: List[CongressionalPDFLink]
    full_text: Optional[str] = ""

    def model_post_init(self, __context):
        self.full_text = ""
        for pdf in self.pdf:
            self.full_text += pdf.text or ""
        return super().model_post_init(__context)

class CongressionalRecordLinkCollection(BaseModel):
    """
    Collection of links to the Congressional Record, including the digest, full record, house, and remarks
    """
    digest: CongressionalDigest
    full_record: CongressionalDigest
    house: Optional[CongressionalDigest] = None
    remarks: Optional[CongressionalDigest] = None

class BoundCongressionalRecord(BaseModel):
    """
    The Congressional Record, bound by congress, volume, issue, and session
    """
    congress: int
    id: int
    issue: IssueNumber
    links: CongressionalRecordLinkCollection
    publish_date: str
    session: str
    volume: VolumeNumber
