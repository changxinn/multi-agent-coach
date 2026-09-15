"""Admin CRUD for the recovery tables shared with the Recovery Agent."""
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import MetaData, Table, Column, BigInteger, Integer, String, Text, DateTime, select, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.db.database import get_db


async def require_admin(user: dict = Depends(get_current_user)):
    if user['role'] != 'admin':
        raise HTTPException(403, 'Administrator access required')
    return user


router = APIRouter(prefix='/recovery', dependencies=[Depends(require_admin)])
metadata = MetaData(schema='systemdb')


def recovery_table(name, *columns):
    return Table(name, metadata, Column('id', BigInteger, primary_key=True),
                 Column('user_id', BigInteger, nullable=False), *columns,
                 Column('created_at', DateTime(timezone=True), server_default=func.now()))


sleep_logs = recovery_table('sleep_logs', Column('duration_minutes', Integer),
                            Column('quality', Integer), Column('notes', Text))
checkins = recovery_table('recovery_checkins', Column('energy', Integer),
                          Column('soreness', Integer), Column('stress', Integer), Column('notes', Text))
assessments = recovery_table('recovery_assessments', Column('status', String(16)),
                             Column('score', Integer), Column('response', JSONB), Column('tool_trace', JSONB))


class RecoveryInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    user_id: int = Field(gt=0)


class SleepInput(RecoveryInput):
    duration_minutes: int = Field(ge=0, le=1440)
    quality: int = Field(ge=1, le=5)
    notes: str | None = Field(default=None, max_length=1000)


class CheckInInput(RecoveryInput):
    energy: int = Field(ge=1, le=10)
    soreness: int = Field(ge=1, le=10)
    stress: int = Field(ge=1, le=10)
    notes: str | None = Field(default=None, max_length=1000)


class AssessmentInput(RecoveryInput):
    status: Literal['green', 'amber', 'red', 'escalate']
    score: int = Field(ge=0)
    response: dict[str, Any]
    tool_trace: list[str]


async def save(db, statement):
    try:
        row = (await db.execute(statement)).mappings().first()
        if row is None:
            raise HTTPException(404, 'Recovery record not found')
        await db.commit()
        return dict(row)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, 'Unable to save record. Check that the user ID exists and values are valid.') from exc


def register_crud(path: str, table: Table, schema: type[BaseModel]):
    # Each route closes over an explicit table; client input never selects SQL identifiers.
    async def listing(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100),
                      user_id: int | None = Query(None, gt=0), db: AsyncSession = Depends(get_db)):
        conditions = [table.c.user_id == user_id] if user_id is not None else []
        total = await db.scalar(select(func.count()).select_from(table).where(*conditions))
        rows = await db.execute(select(table).where(*conditions).order_by(table.c.created_at.desc(), table.c.id.desc())
                                .offset((page - 1) * page_size).limit(page_size))
        return {'items': [dict(row) for row in rows.mappings()], 'total': total}

    async def create(payload: schema, db: AsyncSession = Depends(get_db)):
        return await save(db, table.insert().values(**payload.model_dump()).returning(*table.c))

    async def update(record_id: int, payload: schema, db: AsyncSession = Depends(get_db)):
        return await save(db, table.update().where(table.c.id == record_id)
                          .values(**payload.model_dump()).returning(*table.c))

    async def delete(record_id: int, db: AsyncSession = Depends(get_db)):
        result = await db.execute(table.delete().where(table.c.id == record_id).returning(table.c.id))
        if result.scalar_one_or_none() is None:
            raise HTTPException(404, 'Recovery record not found')
        await db.commit()
        return Response(status_code=204)

    router.add_api_route(path, listing, methods=['GET'], name=f'list_{table.name}')
    router.add_api_route(path, create, methods=['POST'], status_code=201, name=f'create_{table.name}')
    router.add_api_route(path + '/{record_id}', update, methods=['PUT'], name=f'update_{table.name}')
    router.add_api_route(path + '/{record_id}', delete, methods=['DELETE'], status_code=204, name=f'delete_{table.name}')


register_crud('/sleep-logs', sleep_logs, SleepInput)
register_crud('/check-ins', checkins, CheckInInput)
register_crud('/assessments', assessments, AssessmentInput)
