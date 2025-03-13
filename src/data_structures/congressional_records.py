
from http.client import IncompleteRead
from io import BytesIO
import os
from PyPDF2 import PdfReader
from pydantic import BaseModel, HttpUrl, Field
from typing import List, Annotated, Optional
from requests.exceptions import ChunkedEncodingError
import requests

from src.data_collection.data_collection import create_session_with_retries, download_pdf


class CongressionalPDFLink(BaseModel):
    """
    A link to a PDF in the Congressional Record, which includes the part number, url, and text
    """
    part: Annotated[int, Field(description="The part number", alias="Part")]
    url: Annotated[HttpUrl, Field(description="The url to the pdf", alias="Url")]
    text: Optional[str] = Field(description="The text of the pdf", alias="Text", default="")

    def session_get(self, url: str) -> requests.Response:
        """
        Make a GET request to the url with retries

        Args:
            url (str): The url to make the request to

        Returns:
            requests.Response: The response from the request
        """
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
        return None

    def extract_text_from_pdf(self) -> str:
        """
        Extract the text from the pdf
        """
        text = ""
        response = self.session_get(self.url)
        if response is None:
            print(f"Failed to retrieve the PDF from {self.url}")
            try: 
                filename = download_pdf(self.url)
                if filename:
                    with open(filename, "rb") as f:
                        pdf = PdfReader(f)
                        for page in pdf.pages:
                            text += "\n" + page.extract_text() or ""
                    # Clean up the downloaded file
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
                    # Clean up the downloaded file
                    os.remove(filename)
                return text
    
    def model_post_init(self, __context):
        """
        Validate that the text was extracted from the pdf
        """
        if not self.text:
            self.text = self.extract_text_from_pdf()
        return super().model_post_init(__context)


class CongressionalDigest(BaseModel):
    """
    The daily digest of the Congressional Record, which includes the label, ordinal value, pdf links, and full text
    """
    label: Annotated[str, Field(description="The label of the digest", alias="Label")]
    ordinal: Annotated[int, Field(description="The ordinal of the digest", alias="Ordinal")]
    pdf: Annotated[List[CongressionalPDFLink], Field(description="The PDF links, which may be broken into 'parts'.", alias="PDF")]
    full_text: Optional[str] = Field(description="The full text of the digest", alias="FullText", default="")

    def model_post_init(self, __context):
        # Add full text to the digest from the pdf child objects
        self.full_text = ""
        for pdf in self.pdf:
            self.full_text += pdf.text or ""
        return super().model_post_init(__context)

class CongressionalRecordLinkCollection(BaseModel):
    """
    Collection of links to the Congressional Record, including the digest, full record, house, and remarks
    """
    digest: Annotated[CongressionalDigest, Field(description="The daily digest", alias="Digest")]
    full_record: Annotated[CongressionalDigest, Field(description="The entire issue", alias="FullRecord")]
    house: Annotated[CongressionalDigest, Field(description="The house section", alias="House")] = None
    remarks: Annotated[CongressionalDigest, Field(description="The extensions of remarks section", alias="Remarks")] = None

class BoundCongressionalRecord(BaseModel):
    """
    The Congressional Record, bound by congress, volume, issue, and session
    """
    congress: Annotated[int, Field(description="The congress number", alias="Congress")]
    id: Annotated[int, Field(description="The record id", alias="Id")]
    issue: Annotated[str, Field(description="The issue number", alias="Issue")]
    links: Annotated[CongressionalRecordLinkCollection, Field(description="Links to the record", alias="Links")]
    publish_date: Annotated[str, Field(description="The date the record was published", alias="PublishDate")]
    session: Annotated[str, Field(description="The session number", alias="Session")]
    volume: Annotated[str, Field(description="The volume number", alias="Volume")]
