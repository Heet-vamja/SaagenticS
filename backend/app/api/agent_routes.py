from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.routes import Limit, Offset
from app.core.config import get_settings
from app.db.session import get_session
from app.schemas.agent import AgentStepRead, AgentTestCreate, AgentTestRead
from app.services.agents import AgentService, execute_agent_test
from app.services.audits import AuditService, RecordNotFound

router = APIRouter(prefix="/api/v1", tags=["Agent tests"])


def get_agent_service(session: Annotated[Session, Depends(get_session)]):
    return AgentService(session)


Service = Annotated[AgentService, Depends(get_agent_service)]


@router.post("/scans/{scan_id}/agent-tests", response_model=AgentTestRead, status_code=201)
def create_test(
    scan_id: UUID, data: AgentTestCreate, service: Service, background_tasks: BackgroundTasks
):
    test = service.create(scan_id, data)
    background_tasks.add_task(execute_agent_test, test.id)
    return test


@router.get("/scans/{scan_id}/agent-tests", response_model=list[AgentTestRead])
def list_tests(scan_id: UUID, service: Service, limit: Limit = 100, offset: Offset = 0):
    AuditService(service.session).scan(scan_id)
    return service.records.tests(scan_id, limit, offset)


@router.get("/agent-tests/{test_id}", response_model=AgentTestRead)
def get_test(test_id: UUID, service: Service):
    return service.test(test_id)


@router.get("/agent-tests/{test_id}/steps", response_model=list[AgentStepRead])
def steps(test_id: UUID, service: Service, limit: Limit = 100, offset: Offset = 0):
    service.test(test_id)
    return [
        AgentStepRead.model_validate(step).model_copy(
            update={"has_screenshot": bool(step.screenshot_path)}
        )
        for step in service.records.steps(test_id, limit, offset)
    ]


@router.get("/agent-tests/{test_id}/steps/{step_id}/screenshot")
def screenshot(test_id: UUID, step_id: UUID, service: Service):
    service.test(test_id)
    step = service.records.step(test_id, step_id)
    if not step or not step.screenshot_path:
        raise RecordNotFound("Screenshot not found")
    path = Path(step.screenshot_path).resolve()
    root = (Path(get_settings().agent_screenshot_dir) / str(test_id)).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise RecordNotFound("Screenshot not found")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})
