from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.models.domain import ReportFixEvent


class FixRecords:
    def __init__(self, session):
        self.session = session

    def events(self, share_id):
        return list(
            self.session.scalars(
                select(ReportFixEvent)
                .where(ReportFixEvent.share_id == share_id)
                .order_by(ReportFixEvent.created_at, ReportFixEvent.id)
                .limit(1000)
            )
        )

    def record(self, share_id, key, event_type):
        self.session.execute(
            insert(ReportFixEvent)
            .values(share_id=share_id, fix_key=key, event_type=event_type)
            .on_conflict_do_nothing(constraint="uq_report_fix_event")
        )
