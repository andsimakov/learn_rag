from app.services.query_service import QueryService


def get_query_service() -> QueryService:
    return QueryService()
