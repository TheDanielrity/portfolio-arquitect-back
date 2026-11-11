from typing import Annotated

from fastapi import Depends

from app.core.database import SessionDependency
from app.modules.portfolio.relations_service import ProjectRelationsService
from app.modules.portfolio.service import ProjectService
from app.modules.portfolio.taxonomy_service import TaxonomyService


def get_project_service(session: SessionDependency) -> ProjectService:
    return ProjectService(session)


def get_taxonomy_service(session: SessionDependency) -> TaxonomyService:
    return TaxonomyService(session)


def get_relations_service(session: SessionDependency) -> ProjectRelationsService:
    return ProjectRelationsService(session)


Projects = Annotated[ProjectService, Depends(get_project_service)]
Taxonomy = Annotated[TaxonomyService, Depends(get_taxonomy_service)]
Relations = Annotated[ProjectRelationsService, Depends(get_relations_service)]
