"""Atomic, readback-verified bill creation without upsert or replacement."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Literal, Self

from elasticsearch import Elasticsearch
from pydantic import BaseModel, Field, TypeAdapter, field_validator, model_validator

from cdm.config.create_only import (
    AliasName,
    CreateOnlySettings,
    CreateOnlyTarget,
    IndexName,
)
from cdm.utils.json_types import JsonObject

BillId = Annotated[
    str,
    Field(
        pattern=r"^bill:[1-9]\d*:(?:hr|s|hres|sres|hjres|sjres|hconres|sconres):[1-9]\d*$"
    ),
]


class MeasureType(StrEnum):
    HR = "hr"
    S = "s"
    HRES = "hres"
    SRES = "sres"
    HJRES = "hjres"
    SJRES = "sjres"
    HCONRES = "hconres"
    SCONRES = "sconres"


class CanonicalBillIdentity(BaseModel):
    id: BillId
    congress: int = Field(gt=0)
    type: MeasureType
    number: int = Field(gt=0)

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, value: object) -> object:
        return value.lower() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        if self.id != f"bill:{self.congress}:{self.type.value}:{self.number}":
            raise ValueError("Bill source identity disagrees with its fields")
        return self


class BillSourceIdentity(CanonicalBillIdentity):
    source_type: Literal["bill"]


class BillCreation(BaseModel):
    identity: BillId
    source: JsonObject

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        if BillSourceIdentity.model_validate(self.source).id != self.identity:
            raise ValueError("Bill creation identity differs from its source")
        return self


class BillCreationStatus(StrEnum):
    CREATED = "created"
    ALREADY_PRESENT = "already_present"


class VerifiedBillCreation(BaseModel):
    identity: BillId
    status: BillCreationStatus
    sequence_number: int = Field(ge=0)
    primary_term: int = Field(ge=1)
    source_sha256: str


class RejectedBillCreation(BaseModel):
    identity: BillId
    status_code: int
    error: JsonObject


class BillCreationResult(BaseModel):
    verified: list[VerifiedBillCreation]
    rejected: list[RejectedBillCreation]


class BillCreationError(RuntimeError):
    def __init__(self, result: BillCreationResult) -> None:
        self.result = result
        super().__init__(
            "Create-only bill batch rejected: "
            + ", ".join(
                f"{item.identity} HTTP {item.status_code}: {item.error}"
                for item in result.rejected
            )
        )


class SourceDigest:
    @staticmethod
    def of(source: JsonObject) -> str:
        encoded = json.dumps(
            source, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
        return hashlib.sha256(encoded).hexdigest()


class ClusterIdentity(BaseModel):
    cluster_uuid: str


class IndexUuid(BaseModel):
    uuid: str


class IndexSettings(BaseModel):
    index: IndexUuid


class IndexState(BaseModel):
    settings: IndexSettings


class AliasState(BaseModel):
    aliases: dict[AliasName, JsonObject]


class BulkCreation(BaseModel):
    index: IndexName = Field(validation_alias="_index")
    identity: BillId = Field(validation_alias="_id")
    status: int
    result: str | None = None
    sequence_number: int | None = Field(default=None, validation_alias="_seq_no")
    primary_term: int | None = Field(default=None, validation_alias="_primary_term")
    error: JsonObject | None = None


class BulkCreationItem(BaseModel):
    create: BulkCreation


class BulkCreationResponse(BaseModel):
    errors: bool
    items: list[BulkCreationItem]


class BillReadback(BaseModel):
    index: IndexName = Field(validation_alias="_index")
    identity: BillId = Field(validation_alias="_id")
    found: Literal[True]
    source: JsonObject = Field(validation_alias="_source")
    sequence_number: int = Field(ge=0, validation_alias="_seq_no")
    primary_term: int = Field(ge=1, validation_alias="_primary_term")


class BillReadbacks(BaseModel):
    docs: list[BillReadback]


class CreateOnlyBillWriter:
    """A 409 is a verified existing record, never an update or a replacement."""

    def __init__(
        self,
        client: Elasticsearch,
        target: CreateOnlyTarget,
        settings: CreateOnlySettings,
    ) -> None:
        self.client = client.options(
            max_retries=0,
            retry_on_timeout=False,
            request_timeout=settings.request_timeout,
        )
        self.target = target
        self.settings = settings

    def validate_target(self) -> None:
        cluster = ClusterIdentity.model_validate(self.client.info().body)
        if cluster.cluster_uuid != self.target.cluster_uuid:
            raise RuntimeError("Create-only target cluster UUID changed")
        states = TypeAdapter(dict[IndexName, IndexState]).validate_python(
            self.client.indices.get_settings(
                index=self.target.index_name, name="index.uuid"
            ).body
        )
        if set(states) != {self.target.index_name}:
            raise RuntimeError("Create-only target is not the pinned physical index")
        if states[self.target.index_name].settings.index.uuid != self.target.index_uuid:
            raise RuntimeError("Create-only target index UUID changed")
        if self.target.aliases:
            bindings = TypeAdapter(dict[IndexName, AliasState]).validate_python(
                self.client.indices.get_alias(name=",".join(self.target.aliases)).body
            )
            if set(bindings) != {self.target.index_name} or set(
                bindings[self.target.index_name].aliases
            ) != set(self.target.aliases):
                raise RuntimeError("Create-only target alias bindings changed")

    def read(self, identities: list[BillId]) -> list[BillReadback]:
        if not identities or len(identities) > self.settings.maximum_batch_size:
            raise ValueError("Bill readback batch is empty or exceeds its bound")
        response = BillReadbacks.model_validate(
            self.client.mget(index=self.target.index_name, ids=identities).body
        )
        if [item.identity for item in response.docs] != identities:
            raise RuntimeError("Bill readback identities/order differ from the request")
        for item in response.docs:
            if item.index != self.target.index_name:
                raise RuntimeError("Bill readback came from a different physical index")
            if BillSourceIdentity.model_validate(item.source).id != item.identity:
                raise RuntimeError("Bill readback source identity differs")
        return response.docs

    def create(self, documents: list[BillCreation]) -> BillCreationResult:
        if not documents or len(documents) > self.settings.maximum_batch_size:
            raise ValueError("Bill creation batch is empty or exceeds its bound")
        identities = [document.identity for document in documents]
        if len(set(identities)) != len(identities):
            raise ValueError("Bill creation batch contains duplicate identities")
        for document in documents:
            BillCreation.model_validate(document.model_dump())
        self.validate_target()
        operations: list[JsonObject] = []
        for document in documents:
            operations.extend([{"create": {"_id": document.identity}}, document.source])
        response = BulkCreationResponse.model_validate(
            self.client.bulk(index=self.target.index_name, operations=operations).body
        )
        if [item.create.identity for item in response.items] != identities:
            raise RuntimeError("Create-only bulk response identities/order differ")
        accepted: list[tuple[BillCreation, BulkCreation]] = []
        rejected: list[RejectedBillCreation] = []
        for document, wrapped in zip(documents, response.items, strict=True):
            item = wrapped.create
            if item.index != self.target.index_name:
                raise RuntimeError("Create-only bulk response target differs")
            if item.status == 201:
                if (
                    item.result != "created"
                    or item.sequence_number is None
                    or item.primary_term is None
                    or item.error is not None
                ):
                    raise RuntimeError("Malformed successful create-only response")
                accepted.append((document, item))
            elif item.status == 409:
                if (
                    item.error is None
                    or item.error.get("type") != "version_conflict_engine_exception"
                ):
                    raise RuntimeError("Create-only conflict is not a version conflict")
                accepted.append((document, item))
            else:
                if item.error is None:
                    raise RuntimeError("Rejected create-only response has no error")
                rejected.append(
                    RejectedBillCreation(
                        identity=document.identity,
                        status_code=item.status,
                        error=item.error,
                    )
                )
        if response.errors != any(item.create.status != 201 for item in response.items):
            raise RuntimeError("Create-only bulk error summary contradicts its items")
        readbacks = (
            self.read([document.identity for document, _ in accepted])
            if accepted
            else []
        )
        verified: list[VerifiedBillCreation] = []
        for (document, item), readback in zip(accepted, readbacks, strict=True):
            created = item.status == 201
            if created and (
                readback.source != document.source
                or readback.sequence_number != item.sequence_number
                or readback.primary_term != item.primary_term
            ):
                raise RuntimeError(
                    "Created bill differs from acknowledged source/version"
                )
            verified.append(
                VerifiedBillCreation(
                    identity=document.identity,
                    status=(
                        BillCreationStatus.CREATED
                        if created
                        else BillCreationStatus.ALREADY_PRESENT
                    ),
                    sequence_number=readback.sequence_number,
                    primary_term=readback.primary_term,
                    source_sha256=SourceDigest.of(readback.source),
                )
            )
        result = BillCreationResult(verified=verified, rejected=rejected)
        if rejected:
            raise BillCreationError(result)
        return result
