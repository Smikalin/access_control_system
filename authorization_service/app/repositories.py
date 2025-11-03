from typing import Iterable
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .models import ConflictingGroup


async def has_conflict(session: AsyncSession, group_codes: Iterable[str]) -> bool:
    """
    Проверить, есть ли конфликт между любыми двумя из указанных кодов групп.
    Логика:
    - загружается таблица пар конфликтующих групп
    - пары нормализуются (min(codeA, codeB), max(...))
    - перебираются все уникальные пары из входного списка; если совпадает — конфликт.
    :return: True, если конфликт обнаружен, иначе False
    """
    codes = list(group_codes)
    if len(codes) < 2:
        return False
    stmt = select(ConflictingGroup)
    rows = (await session.execute(stmt)).scalars().all()
    pairs = {
        (min(r.group_code_a, r.group_code_b), max(r.group_code_a, r.group_code_b))
        for r in rows
    }
    for i in range(len(codes)):
        for j in range(i + 1, len(codes)):
            pair = (min(codes[i], codes[j]), max(codes[i], codes[j]))
            if pair in pairs:
                return True
    return False
