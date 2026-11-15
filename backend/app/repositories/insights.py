from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.edge.agents import QA_AGENT
from app.models.domain import AgentRequest, AgentSession, QARun


class InsightRecords:
    """Database access only; the service owns transaction boundaries."""

    def __init__(self, session: Session):
        self.session = session

    def unsessioned_agent_requests(self, site_id, limit: int = 5000) -> list[AgentRequest]:
        return list(
            self.session.scalars(
                select(AgentRequest)
                .where(
                    AgentRequest.site_id == site_id,
                    AgentRequest.agent_kind == "agent",
                    AgentRequest.agent != QA_AGENT,  # QA runs are not visitor traffic.
                    AgentRequest.session_id.is_(None),
                )
                .order_by(AgentRequest.received_at)
                .limit(limit)
            )
        )

    def latest_session(self, site_id, agent: str, client_hash: str) -> AgentSession | None:
        return self.session.scalar(
            select(AgentSession)
            .where(
                AgentSession.site_id == site_id,
                AgentSession.agent == agent,
                AgentSession.client_hash == client_hash,
            )
            .order_by(AgentSession.ended_at.desc())
            .limit(1)
        )

    def unlabeled_sessions(self, site_id, limit: int) -> list[AgentSession]:
        return list(
            self.session.scalars(
                select(AgentSession)
                .where(AgentSession.site_id == site_id, AgentSession.label_source == "none")
                .order_by(AgentSession.started_at)
                .limit(limit)
            )
        )

    def session_requests(self, session_id) -> list[AgentRequest]:
        return list(
            self.session.scalars(
                select(AgentRequest)
                .where(AgentRequest.session_id == session_id)
                .order_by(AgentRequest.received_at)
                .limit(200)
            )
        )

    def agent_activity(self, site_id, since: datetime) -> list:
        return list(
            self.session.execute(
                select(
                    AgentRequest.agent,
                    AgentRequest.agent_kind,
                    func.count().label("requests"),
                    func.sum(case((AgentRequest.served_by == "variant", 1), else_=0)).label(
                        "variant_requests"
                    ),
                    func.sum(case((AgentRequest.status >= 400, 1), else_=0)).label("errors"),
                    func.max(AgentRequest.received_at).label("last_seen"),
                )
                .where(
                    AgentRequest.site_id == site_id,
                    AgentRequest.received_at >= since,
                    AgentRequest.agent != QA_AGENT,
                )
                .group_by(AgentRequest.agent, AgentRequest.agent_kind)
                .order_by(func.count().desc())
                .limit(50)
            )
        )

    def sessions_since(self, site_id, since: datetime, limit: int = 2000) -> list[AgentSession]:
        return list(
            self.session.scalars(
                select(AgentSession)
                .where(AgentSession.site_id == site_id, AgentSession.started_at >= since)
                .order_by(AgentSession.started_at.desc())
                .limit(limit)
            )
        )

    def latest_qa_batch(self, site_id) -> list[QARun]:
        batch = self.session.scalar(
            select(QARun.batch_id)
            .where(QARun.site_id == site_id)
            .order_by(QARun.created_at.desc())
            .limit(1)
        )
        if batch is None:
            return []
        return list(
            self.session.scalars(
                select(QARun)
                .where(QARun.site_id == site_id, QARun.batch_id == batch)
                .order_by(QARun.task_key, QARun.target)
            )
        )
