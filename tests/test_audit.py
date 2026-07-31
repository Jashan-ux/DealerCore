import pytest
import uuid
from decimal import Decimal

from app.models.audit import AuditAction
from app.repositories.audit_repository import AuditRepository


@pytest.mark.asyncio
async def test_create_audit_log_stores_all_fields(db_session):
    repo = AuditRepository(db_session)
    user_id = uuid.uuid4()
    entity_id = uuid.uuid4()

    log = await repo.create(
        action=AuditAction.VEHICLE_CREATED,
        performed_by=user_id,
        entity_type="vehicle",
        entity_id=entity_id,
        details={"make": "Toyota", "model": "Camry", "quantity": 5},
    )

    assert log.id is not None
    assert log.action == AuditAction.VEHICLE_CREATED
    assert log.performed_by == user_id
    assert log.entity_id == entity_id
    assert log.details["make"] == "Toyota"


@pytest.mark.asyncio
async def test_get_audit_logs_by_entity_returns_correct_records(db_session):
    repo = AuditRepository(db_session)
    entity_id = uuid.uuid4()

    await repo.create(
        action=AuditAction.VEHICLE_CREATED,
        performed_by=uuid.uuid4(),
        entity_type="vehicle",
        entity_id=entity_id,
        details={"make": "Toyota"},
    )
    await repo.create(
        action=AuditAction.VEHICLE_UPDATED,
        performed_by=uuid.uuid4(),
        entity_type="vehicle",
        entity_id=entity_id,
        details={"price": "3000000.00"},
    )

    logs = await repo.get_by_entity(entity_id)
    assert len(logs) == 2
    assert all(log.entity_id == entity_id for log in logs)


@pytest.mark.asyncio
async def test_get_audit_logs_by_user_returns_correct_records(db_session):
    repo = AuditRepository(db_session)
    user_id = uuid.uuid4()

    await repo.create(
        action=AuditAction.VEHICLE_PURCHASED,
        performed_by=user_id,
        entity_type="purchase",
        entity_id=uuid.uuid4(),
        details={"quantity": 1},
    )

    logs = await repo.get_by_user(user_id)
    assert len(logs) >= 1
    assert all(log.performed_by == user_id for log in logs)


@pytest.mark.asyncio
async def test_audit_logs_are_ordered_newest_first(db_session):
    repo = AuditRepository(db_session)
    entity_id = uuid.uuid4()

    await repo.create(
        action=AuditAction.VEHICLE_CREATED,
        performed_by=uuid.uuid4(),
        entity_type="vehicle",
        entity_id=entity_id,
        details={},
    )
    await repo.create(
        action=AuditAction.VEHICLE_UPDATED,
        performed_by=uuid.uuid4(),
        entity_type="vehicle",
        entity_id=entity_id,
        details={},
    )

    logs = await repo.get_by_entity(entity_id)
    assert logs[0].action == AuditAction.VEHICLE_UPDATED
    assert logs[1].action == AuditAction.VEHICLE_CREATED