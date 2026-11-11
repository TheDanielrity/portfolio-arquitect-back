from app.core.exceptions import ResourceNotFound
from app.models import Project
from app.modules.media.public_schemas import PublicMedia
from app.modules.portfolio.public_repository import PublicPortfolioRepository
from app.modules.portfolio.public_schemas import (
    PublicAttribute,
    PublicCategory,
    PublicProjectCard,
    PublicProjectDetail,
    PublicProjectMedia,
    PublicProjectQuery,
    PublicSection,
    PublicSectionMedia,
    PublicTag,
)
from app.modules.portfolio.schemas import MediaRole, Page, PageQuery
from app.modules.portfolio.section_schemas import SectionType


def project_card(row: Project) -> PublicProjectCard:
    cover = next((link.media_asset for link in row.media_links if link.role == "COVER"), None)
    categories = sorted(
        (link.category for link in row.category_links if link.category.is_active),
        key=lambda category: (category.sort_order, category.slug),
    )
    return PublicProjectCard(
        title=row.title,
        slug=row.slug,
        short_description=row.short_description,
        location=row.location,
        year=row.year,
        cover=PublicMedia.model_validate(cover) if cover is not None else None,
        categories=[PublicCategory.model_validate(category) for category in categories],
    )


class PublicPortfolioService:
    def __init__(self, repository: PublicPortfolioRepository) -> None:
        self.repository = repository

    async def projects(
        self, query: PublicProjectQuery, *, featured: bool = False
    ) -> Page[PublicProjectCard]:
        rows, total = await self.repository.projects(query, featured=featured)
        return Page(
            items=[project_card(row) for row in rows],
            total=total,
            limit=query.limit,
            offset=query.offset,
        )

    async def detail(self, slug: str) -> PublicProjectDetail:
        row = await self.repository.detail(slug)
        if row is None:
            raise ResourceNotFound("Project not found")
        return PublicProjectDetail(
            **project_card(row).model_dump(),
            description=row.description,
            area_m2=row.area_m2,
            client_name=row.client_name,
            seo_title=row.seo_title,
            seo_description=row.seo_description,
            tags=[
                PublicTag.model_validate(link.tag)
                for link in sorted(
                    row.tag_links, key=lambda link: (link.tag.name.lower(), link.tag.slug)
                )
            ],
            attributes=[
                PublicAttribute.model_validate(attribute)
                for attribute in sorted(row.attributes, key=lambda item: (item.sort_order, item.id))
            ],
            media=[
                PublicProjectMedia(
                    role=MediaRole(link.role), asset=PublicMedia.model_validate(link.media_asset)
                )
                for link in sorted(row.media_links, key=lambda item: (item.sort_order, item.id))
            ],
            sections=[
                PublicSection(
                    section_type=SectionType(section.section_type),
                    title=section.title,
                    content=section.content,
                    media=[
                        PublicSectionMedia(
                            caption=link.caption, asset=PublicMedia.model_validate(link.media_asset)
                        )
                        for link in sorted(
                            section.media_links, key=lambda item: (item.sort_order, item.media_id)
                        )
                    ],
                )
                for section in sorted(row.sections, key=lambda item: (item.sort_order, item.id))
                if section.is_visible
            ],
        )

    async def categories(self, query: PageQuery) -> Page[PublicCategory]:
        rows, total = await self.repository.categories(query)
        return Page(
            items=[PublicCategory.model_validate(row) for row in rows],
            total=total,
            limit=query.limit,
            offset=query.offset,
        )

    async def tags(self, query: PageQuery) -> Page[PublicTag]:
        rows, total = await self.repository.tags(query)
        return Page(
            items=[PublicTag.model_validate(row) for row in rows],
            total=total,
            limit=query.limit,
            offset=query.offset,
        )
