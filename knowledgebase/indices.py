"""Index specs for the knowledgebase."""

from __future__ import annotations

from typing import Any

from .setup import IndexSpec


ID_META_FIELDS: dict[str, Any] = {
    "api_id": {"type": "keyword"},
    "param_id": {"type": "keyword"},
    "citation_id": {"type": "keyword"},
}

RECORD_TYPE_FIELD: dict[str, Any] = {
    "recordType": {"type": "keyword"},
}

SEMANTIC_INFERENCE_ID = "my-elser-endpoint"
SEMANTIC_FIELD: dict[str, Any] = {
    "type": "semantic_text",
    "inference_id": SEMANTIC_INFERENCE_ID,
    "chunking_settings": {"strategy": "none"},
}

BILLS_MAPPING: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": True,
        "properties": {
            "id": {"type": "keyword"},
            **ID_META_FIELDS,
            **RECORD_TYPE_FIELD,
            "congress": {"type": "integer"},
            "type": {"type": "keyword"},
            "number": {"type": "keyword"},
            "title": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword"}, "semantic": SEMANTIC_FIELD},
            },
            "originChamber": {"type": "keyword"},
            "originChamberCode": {"type": "keyword"},
            "updateDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "updateDateIncludingText": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "url": {"type": "keyword"},
            "latestAction": {
                "properties": {
                    "actionDate": {
                        "type": "date",
                        "format": "strict_date_optional_time||yyyy-MM-dd",
                    },
                    "text": {
                        "type": "text",
                        "fields": {
                            "keyword": {"type": "keyword"},
                            "semantic": SEMANTIC_FIELD,
                        },
                    },
                }
            },
        },
    },
}

MEMBERS_MAPPING: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": True,
        "properties": {
            "id": {"type": "keyword"},
            **ID_META_FIELDS,
            **RECORD_TYPE_FIELD,
            "bioguideId": {"type": "keyword"},
            "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "fullName": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "partyName": {"type": "keyword"},
            "party": {"type": "keyword"},
            "state": {"type": "keyword"},
            "district": {"type": "integer"},
            "url": {"type": "keyword"},
            "depiction": {
                "properties": {
                    "imageUrl": {"type": "keyword"},
                    "attribution": {"type": "text"},
                }
            },
            "updateDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
        },
    },
}

AMENDMENTS_MAPPING: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": True,
        "properties": {
            "id": {"type": "keyword"},
            **ID_META_FIELDS,
            **RECORD_TYPE_FIELD,
            "congress": {"type": "integer"},
            "type": {"type": "keyword"},
            "number": {"type": "keyword"},
            "purpose": {"type": "text", "fields": {"semantic": SEMANTIC_FIELD}},
            "updateDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "url": {"type": "keyword"},
            "latestAction": {
                "properties": {
                    "actionDate": {
                        "type": "date",
                        "format": "strict_date_optional_time||yyyy-MM-dd",
                    },
                    "text": {
                        "type": "text",
                        "fields": {
                            "keyword": {"type": "keyword"},
                            "semantic": SEMANTIC_FIELD,
                        },
                    },
                }
            },
        },
    },
}

COMMITTEES_MAPPING: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": True,
        "properties": {
            "id": {"type": "keyword"},
            **ID_META_FIELDS,
            **RECORD_TYPE_FIELD,
            "systemCode": {"type": "keyword"},
            "committeeTypeCode": {"type": "keyword"},
            "chamber": {"type": "keyword"},
            "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "updateDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "url": {"type": "keyword"},
        },
    },
}

COMMITTEE_MEETINGS_MAPPING: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": True,
        "properties": {
            "id": {"type": "keyword"},
            **ID_META_FIELDS,
            **RECORD_TYPE_FIELD,
            "congress": {"type": "integer"},
            "chamber": {"type": "keyword"},
            "eventId": {"type": "keyword"},
            "updateDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "url": {"type": "keyword"},
        },
    },
}

COMMITTEE_PRINTS_MAPPING: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": True,
        "properties": {
            "id": {"type": "keyword"},
            **ID_META_FIELDS,
            **RECORD_TYPE_FIELD,
            "congress": {"type": "integer"},
            "chamber": {"type": "keyword"},
            "jacketNumber": {"type": "integer"},
            "updateDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "url": {"type": "keyword"},
        },
    },
}

COMMITTEE_REPORTS_MAPPING: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": True,
        "properties": {
            "id": {"type": "keyword"},
            **ID_META_FIELDS,
            **RECORD_TYPE_FIELD,
            "congress": {"type": "integer"},
            "chamber": {"type": "keyword"},
            "type": {"type": "keyword"},
            "number": {"type": "integer"},
            "part": {"type": "integer"},
            "cmte_rpt_id": {"type": "keyword"},
            "citation": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "updateDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "url": {"type": "keyword"},
        },
    },
}

CONGRESSES_MAPPING: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": True,
        "properties": {
            "id": {"type": "keyword"},
            **ID_META_FIELDS,
            **RECORD_TYPE_FIELD,
            "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "startYear": {"type": "keyword"},
            "endYear": {"type": "keyword"},
            "updateDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "url": {"type": "keyword"},
            "sessions": {
                "properties": {
                    "chamber": {"type": "keyword"},
                    "number": {"type": "integer"},
                    "type": {"type": "keyword"},
                    "startDate": {
                        "type": "date",
                        "format": "strict_date_optional_time||yyyy-MM-dd",
                    },
                    "endDate": {
                        "type": "date",
                        "format": "strict_date_optional_time||yyyy-MM-dd",
                    },
                }
            },
        },
    },
}

CONGRESSIONAL_RECORDS_MAPPING: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": True,
        "properties": {
            "id": {"type": "keyword"},
            **ID_META_FIELDS,
            **RECORD_TYPE_FIELD,
            "Congress": {"type": "keyword"},
            "Id": {"type": "integer"},
            "Issue": {"type": "keyword"},
            "PublishDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "Session": {"type": "keyword"},
            "Volume": {"type": "keyword"},
        },
    },
}

DAILY_CONGRESSIONAL_RECORDS_MAPPING: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": True,
        "properties": {
            "id": {"type": "keyword"},
            **ID_META_FIELDS,
            **RECORD_TYPE_FIELD,
            "congress": {"type": "integer"},
            "issueDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "issueNumber": {"type": "keyword"},
            "sessionNumber": {"type": "integer"},
            "updateDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "volumeNumber": {"type": "integer"},
            "url": {"type": "keyword"},
        },
    },
}

CRS_REPORTS_MAPPING: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": True,
        "properties": {
            "id": {"type": "keyword"},
            **ID_META_FIELDS,
            **RECORD_TYPE_FIELD,
            "contentType": {"type": "keyword"},
            "title": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword"}, "semantic": SEMANTIC_FIELD},
            },
            "publishDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "updateDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "version": {"type": "integer"},
            "status": {"type": "keyword"},
            "url": {"type": "keyword"},
        },
    },
}

HEARINGS_MAPPING: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": True,
        "properties": {
            "id": {"type": "keyword"},
            **ID_META_FIELDS,
            **RECORD_TYPE_FIELD,
            "congress": {"type": "integer"},
            "chamber": {"type": "keyword"},
            "jacketNumber": {"type": "integer"},
            "number": {"type": "integer"},
            "updateDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "url": {"type": "keyword"},
        },
    },
}

HOUSE_COMMUNICATIONS_MAPPING: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": True,
        "properties": {
            "id": {"type": "keyword"},
            **ID_META_FIELDS,
            **RECORD_TYPE_FIELD,
            "congress": {"type": "integer"},
            "chamber": {"type": "keyword"},
            "number": {"type": "integer"},
            "updateDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "url": {"type": "keyword"},
            "communicationType": {
                "properties": {
                    "code": {"type": "keyword"},
                    "name": {"type": "keyword"},
                }
            },
        },
    },
}

HOUSE_REQUIREMENTS_MAPPING: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": True,
        "properties": {
            "id": {"type": "keyword"},
            **ID_META_FIELDS,
            **RECORD_TYPE_FIELD,
            "number": {"type": "integer"},
            "updateDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "url": {"type": "keyword"},
        },
    },
}

HOUSE_VOTES_MAPPING: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": True,
        "properties": {
            "id": {"type": "keyword"},
            **ID_META_FIELDS,
            **RECORD_TYPE_FIELD,
            "congress": {"type": "integer"},
            "identifier": {"type": "long"},
            "legislationNumber": {"type": "keyword"},
            "legislationType": {"type": "keyword"},
            "legislationUrl": {"type": "keyword"},
            "result": {"type": "keyword"},
            "rollCallNumber": {"type": "integer"},
            "sessionNumber": {"type": "integer"},
            "sourceDataURL": {"type": "keyword"},
            "startDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "updateDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "url": {"type": "keyword"},
            "voteType": {"type": "keyword"},
        },
    },
}

LAWS_MAPPING: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": True,
        "properties": {
            "id": {"type": "keyword"},
            **ID_META_FIELDS,
            **RECORD_TYPE_FIELD,
            "congress": {"type": "integer"},
            "type": {"type": "keyword"},
            "number": {"type": "keyword"},
            "title": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword"}, "semantic": SEMANTIC_FIELD},
            },
            "originChamber": {"type": "keyword"},
            "originChamberCode": {"type": "keyword"},
            "updateDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "updateDateIncludingText": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "url": {"type": "keyword"},
            "laws": {
                "properties": {
                    "number": {"type": "keyword"},
                    "type": {"type": "keyword"},
                }
            },
            "latestAction": {
                "properties": {
                    "actionDate": {
                        "type": "date",
                        "format": "strict_date_optional_time||yyyy-MM-dd",
                    },
                    "text": {
                        "type": "text",
                        "fields": {
                            "keyword": {"type": "keyword"},
                            "semantic": SEMANTIC_FIELD,
                        },
                    },
                }
            },
        },
    },
}

NOMINATIONS_MAPPING: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": True,
        "properties": {
            "id": {"type": "keyword"},
            **ID_META_FIELDS,
            **RECORD_TYPE_FIELD,
            "congress": {"type": "integer"},
            "number": {"type": "integer"},
            "partNumber": {"type": "keyword"},
            "citation": {"type": "keyword"},
            "organization": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "description": {"type": "text", "fields": {"semantic": SEMANTIC_FIELD}},
            "receivedDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "updateDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "url": {"type": "keyword"},
            "latestAction": {
                "properties": {
                    "actionDate": {
                        "type": "date",
                        "format": "strict_date_optional_time||yyyy-MM-dd",
                    },
                    "text": {
                        "type": "text",
                        "fields": {
                            "keyword": {"type": "keyword"},
                            "semantic": SEMANTIC_FIELD,
                        },
                    },
                }
            },
        },
    },
}

SENATE_COMMUNICATIONS_MAPPING: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": True,
        "properties": {
            "id": {"type": "keyword"},
            **ID_META_FIELDS,
            **RECORD_TYPE_FIELD,
            "congress": {"type": "integer"},
            "chamber": {"type": "keyword"},
            "number": {"type": "integer"},
            "updateDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "url": {"type": "keyword"},
            "communicationType": {
                "properties": {
                    "code": {"type": "keyword"},
                    "name": {"type": "keyword"},
                }
            },
        },
    },
}

SUMMARIES_MAPPING: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": True,
        "properties": {
            "id": {"type": "keyword"},
            **ID_META_FIELDS,
            **RECORD_TYPE_FIELD,
            "actionDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "actionDesc": {"type": "keyword"},
            "currentChamber": {"type": "keyword"},
            "currentChamberCode": {"type": "keyword"},
            "lastSummaryUpdateDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "updateDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "versionCode": {"type": "keyword"},
            "text": {"type": "text", "fields": {"semantic": SEMANTIC_FIELD}},
            "bill": {
                "properties": {
                    "congress": {"type": "integer"},
                    "number": {"type": "keyword"},
                    "type": {"type": "keyword"},
                    "title": {
                        "type": "text",
                        "fields": {
                            "keyword": {"type": "keyword"},
                            "semantic": SEMANTIC_FIELD,
                        },
                    },
                    "originChamber": {"type": "keyword"},
                    "originChamberCode": {"type": "keyword"},
                    "updateDateIncludingText": {
                        "type": "date",
                        "format": "strict_date_optional_time||yyyy-MM-dd",
                    },
                    "url": {"type": "keyword"},
                }
            },
        },
    },
}

TREATIES_MAPPING: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": True,
        "properties": {
            "id": {"type": "keyword"},
            **ID_META_FIELDS,
            **RECORD_TYPE_FIELD,
            "congressReceived": {"type": "integer"},
            "congressConsidered": {"type": "integer"},
            "number": {"type": "integer"},
            "suffix": {"type": "keyword"},
            "transmittedDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "topic": {"type": "keyword"},
            "updateDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "url": {"type": "keyword"},
        },
    },
}

BOUND_CONGRESSIONAL_RECORDS_MAPPING: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": True,
        "properties": {
            "id": {"type": "keyword"},
            **ID_META_FIELDS,
            **RECORD_TYPE_FIELD,
            "date": {"type": "date", "format": "strict_date_optional_time||yyyy-MM-dd"},
            "volumeNumber": {"type": "integer"},
            "congress": {"type": "integer"},
            "sessionNumber": {"type": "keyword"},
            "updateDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "url": {"type": "keyword"},
        },
    },
}


def build_default_specs() -> list[IndexSpec]:
    """Return default index specs for bills and members."""
    specs: list[tuple[str, dict[str, Any]]] = [
        ("congress-bills", BILLS_MAPPING),
        ("congress-members", MEMBERS_MAPPING),
        ("congress-amendments", AMENDMENTS_MAPPING),
        ("congress-committees", COMMITTEES_MAPPING),
        ("congress-committee-meetings", COMMITTEE_MEETINGS_MAPPING),
        ("congress-committee-prints", COMMITTEE_PRINTS_MAPPING),
        ("congress-committee-reports", COMMITTEE_REPORTS_MAPPING),
        ("congress-congresses", CONGRESSES_MAPPING),
        ("congress-congressional-records", CONGRESSIONAL_RECORDS_MAPPING),
        (
            "congress-daily-congressional-records",
            DAILY_CONGRESSIONAL_RECORDS_MAPPING,
        ),
        ("congress-crs-reports", CRS_REPORTS_MAPPING),
        ("congress-hearings", HEARINGS_MAPPING),
        ("congress-house-communications", HOUSE_COMMUNICATIONS_MAPPING),
        ("congress-house-requirements", HOUSE_REQUIREMENTS_MAPPING),
        ("congress-house-votes", HOUSE_VOTES_MAPPING),
        ("congress-laws", LAWS_MAPPING),
        ("congress-nominations", NOMINATIONS_MAPPING),
        ("congress-senate-communications", SENATE_COMMUNICATIONS_MAPPING),
        ("congress-summaries", SUMMARIES_MAPPING),
        ("congress-treaties", TREATIES_MAPPING),
        (
            "congress-bound-congressional-records",
            BOUND_CONGRESSIONAL_RECORDS_MAPPING,
        ),
    ]
    return [IndexSpec(name=name, mapping=mapping) for name, mapping in specs]


def index_name_for_record(record_type: str) -> str:
    """Return the index name for a record type."""
    if not record_type:
        raise ValueError("recordType is required")
    return record_type
