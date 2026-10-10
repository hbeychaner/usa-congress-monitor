"""FastAPI dependency providers backed by the process-wide container."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from cdm.backend.services.admin_service import AdminService
from cdm.backend.services.bill_service import BillService
from cdm.backend.services.committee_service import CommitteeService
from cdm.backend.services.graph_service import GraphService
from cdm.backend.services.member_service import MemberService
from cdm.backend.services.neighborhood_service import NeighborhoodService
from cdm.backend.services.search_service import SearchService
from cdm.backend.services.similar_bill_service import SimilarBillService
from cdm.backend.services.state_service import StateService
from cdm.backend.services.subject_service import SubjectService
from cdm.backend.services.topic_service import TopicService
from cdm.backend.services.vote_service import VoteService
from cdm.config import get_config
from cdm.container import Container


@lru_cache
def get_container() -> Container:
    return Container(get_config())


ContainerDep = Annotated[Container, Depends(get_container)]


def get_similar_bill_service(container: ContainerDep) -> SimilarBillService:
    return container.similar_bill_service


def get_committee_service(container: ContainerDep) -> CommitteeService:
    return container.committee_service


def get_bill_service(container: ContainerDep) -> BillService:
    return container.bill_service


def get_vote_service(container: ContainerDep) -> VoteService:
    return container.vote_service


def get_state_service(container: ContainerDep) -> StateService:
    return container.state_service


def get_search_service(container: ContainerDep) -> SearchService:
    return container.search_service


def get_subject_service(container: ContainerDep) -> SubjectService:
    return container.subject_service


def get_admin_service(container: ContainerDep) -> AdminService:
    return container.admin_service


def get_topic_service(container: ContainerDep) -> TopicService:
    return container.topic_service


def get_member_service(container: ContainerDep) -> MemberService:
    return container.member_service


def get_graph_service(container: ContainerDep) -> GraphService:
    return container.graph_service


def get_neighborhood_service(container: ContainerDep) -> NeighborhoodService:
    return container.neighborhood_service


AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]
SimilarBillServiceDep = Annotated[SimilarBillService, Depends(get_similar_bill_service)]
CommitteeServiceDep = Annotated[CommitteeService, Depends(get_committee_service)]
BillServiceDep = Annotated[BillService, Depends(get_bill_service)]
VoteServiceDep = Annotated[VoteService, Depends(get_vote_service)]
StateServiceDep = Annotated[StateService, Depends(get_state_service)]
SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]
SubjectServiceDep = Annotated[SubjectService, Depends(get_subject_service)]
TopicServiceDep = Annotated[TopicService, Depends(get_topic_service)]
MemberServiceDep = Annotated[MemberService, Depends(get_member_service)]
GraphServiceDep = Annotated[GraphService, Depends(get_graph_service)]
NeighborhoodServiceDep = Annotated[NeighborhoodService, Depends(get_neighborhood_service)]
