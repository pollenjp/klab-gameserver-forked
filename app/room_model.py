# Standard Library
from enum import IntEnum
from logging import getLogger
from typing import Iterator
from typing import List
from typing import Optional

# Third Party Library
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import CursorResult  # type: ignore

# Local Library
from .db import engine

logger = getLogger(__name__)

max_user_count: int = 4


class RoomDBTableName:
    """table column names"""

    table_name: str = "room"
    room_id: str = "room_id"  # bigint NOT NULL AUTO_INCREMENT
    live_id: str = "live_id"  # bigint NOT NULL
    joined_user_count: str = "joined_user_count"  # bigint NOT NULL
    status: str = "status"  # NOT NULL DEFAULT 1


class LiveDifficulty(IntEnum):
    normal: int = 1
    hard: int = 2


class JoinRoomResult(IntEnum):
    Ok: int = 1
    RoomFull: int = 2
    Disbanded: int = 3
    OhterError: int = 4


class WaitRoomStatus(IntEnum):
    Waiting = 1  # ホストがライブ開始ボタン押すのを待っている
    LiveStart = 2  # ライブ画面遷移OK
    Dissolution = 3  # 解散された


class RoomStatus(BaseModel):
    room_id: int
    status: WaitRoomStatus

    class Config:
        orm_mode = True


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int = max_user_count

    class Config:
        orm_mode = True


class RoomUser(BaseModel):
    room_id: int
    user_id: int
    live_difficulty: int
    is_me: bool = False
    is_host: bool

    class Config:
        orm_mode = True


class RoomUserDBTableName:
    """table column names"""

    table_name: str = "room_user"

    room_id: str = "room_id"  # primary key
    user_id: str = "user_id"  # primary key
    live_difficulty: str = "live_difficulty"
    is_host: str = "is_host"
    judge_count_perfect: str = "judge_count_perfect"
    judge_count_great: str = "judge_count_great"
    judge_count_good: str = "judge_count_good"
    judge_count_bad: str = "judge_count_bad"
    judge_count_miss: str = "judge_count_miss"


class RoomUserResult(BaseModel):
    room_id: int
    user_id: str
    judge_count_perfect: int
    judge_count_great: int
    judge_count_good: int
    judge_count_bad: int
    judge_count_miss: int

    class Config:
        orm_mode = True


def create_room(live_id: int) -> int:
    with engine.begin() as conn:
        query: str = " ".join(
            [
                f"INSERT INTO `{ RoomDBTableName.table_name }`",
                f"SET `{ RoomDBTableName.live_id }`=:live_id,"
                f"`{ RoomDBTableName.joined_user_count }`=:joined_user_count",
            ]
        )
        result: CursorResult = conn.execute(text(query), dict(live_id=live_id, joined_user_count=0))
        logger.info(f"{result=}")
        logger.info(f"{result.lastrowid=}")
        room_id: int = result.lastrowid
        return room_id


def _update_room_user_count(conn, room_id: int, offset: int):
    query: str
    query = " ".join(
        [
            f"SELECT { RoomDBTableName.joined_user_count }",
            f"FROM `{ RoomDBTableName.table_name }`",
            f"WHERE `{ RoomDBTableName.room_id }`=:room_id",
        ]
    )
    result_select: CursorResult = conn.execute(text(query), dict(room_id=room_id))
    joined_user_count: int = result_select.one().joined_user_count
    joined_user_count += offset
    query = " ".join(
        [
            f"UPDATE `{ RoomDBTableName.table_name }`",
            f"SET `{ RoomDBTableName.joined_user_count }`=:joined_user_count",
            f"WHERE `{ RoomDBTableName.room_id }`=:room_id",
        ]
    )
    result_update: CursorResult = conn.execute(
        text(query),
        dict(
            joined_user_count=joined_user_count,
            room_id=room_id,
        ),
    )
    logger.info(f"{result_update=}")
    return


def _create_room_user(conn, room_id: int, user_id: int, live_difficulty: LiveDifficulty, is_host: bool):
    query: str = " ".join(
        [
            f"INSERT INTO `{ RoomUserDBTableName.table_name }`",
            "SET",
            f"`{ RoomUserDBTableName.room_id }`=:room_id,",
            f"`{ RoomUserDBTableName.user_id }`=:user_id,",
            f"`{ RoomUserDBTableName.live_difficulty }`=:live_difficulty,",
            f"`{ RoomUserDBTableName.is_host }`=:is_host",
        ]
    )
    result: CursorResult = conn.execute(
        text(query),
        dict(
            room_id=room_id,
            user_id=user_id,
            live_difficulty=int(live_difficulty),
            is_host=is_host,
        ),
    )
    logger.info(f"{result=}")


def _get_room_info_by_id(conn, room_id: int) -> Optional[RoomInfo]:
    query: str = " ".join(
        [
            f"SELECT `{ RoomDBTableName.room_id }`, `{ RoomDBTableName.live_id }`, `{ RoomDBTableName.joined_user_count }`",
            f"FROM `{ RoomDBTableName.table_name }`",
            f"WHERE `{ RoomDBTableName.room_id }`=:room_id",
        ]
    )
    result = conn.execute(text(query), dict(room_id=room_id))
    row = result.one()
    if row is None:
        return row
    return RoomInfo.from_orm(row)


def join_room(user_id: int, room_id: int, live_difficulty: LiveDifficulty, is_host: bool = False) -> JoinRoomResult:
    with engine.begin() as conn:
        try:
            room_info: Optional[RoomInfo] = _get_room_info_by_id(conn, room_id=room_id)
            if room_info is None:
                return JoinRoomResult.Disbanded
            if room_info.joined_user_count >= room_info.max_user_count:
                return JoinRoomResult.RoomFull
            _create_room_user(conn, room_id, user_id, live_difficulty, is_host)
            _update_room_user_count(conn=conn, room_id=room_id, offset=1)
            return JoinRoomResult.Ok
        except Exception as e:
            # Standard Library
            import traceback

            logger.info(f"{traceback.format_exc()}")
            logger.info(f"{e=}")
            return JoinRoomResult.OhterError


def _get_rooms_by_live_id(conn, live_id: int):
    """
    to list rooms
    """
    query: str = " ".join(
        [
            f"SELECT `{ RoomDBTableName.room_id }`, `{ RoomDBTableName.live_id }`, `{ RoomDBTableName.joined_user_count }`",
            f"FROM `{ RoomDBTableName.table_name }`",
            f"WHERE `{ RoomDBTableName.live_id }`=:live_id",
        ]
    )
    result = conn.execute(text(query), dict(live_id=live_id))
    for row in result.all():
        yield RoomInfo.from_orm(row)


def get_rooms_by_live_id(live_id: int) -> List[RoomInfo]:
    with engine.begin() as conn:
        return list(_get_rooms_by_live_id(conn, live_id))


def _get_room_status(conn, room_id: int) -> RoomStatus:
    query: str = " ".join(
        [
            f"SELECT `{ RoomDBTableName.room_id }`, `{ RoomDBTableName.status }`",
            f"FROM `{ RoomDBTableName.table_name }`",
            f"WHERE `{ RoomDBTableName.room_id }`=:room_id",
        ]
    )
    result = conn.execute(text(query), dict(room_id=room_id))
    return RoomStatus.from_orm(result.one())


def get_room_status(room_id: int) -> RoomStatus:
    with engine.begin() as conn:
        return _get_room_status(conn, room_id)


def _get_room_users(conn, room_id: int, user_id_req: int) -> Iterator[RoomUser]:
    query: str = " ".join(
        [
            "SELECT",
            f"`{ RoomUserDBTableName.room_id }`,",
            f"`{ RoomUserDBTableName.user_id }`,",
            f"`{ RoomUserDBTableName.live_difficulty }`,",
            f"`{ RoomUserDBTableName.is_host }`",
            f"FROM `{ RoomUserDBTableName.table_name }`",
            f"WHERE `{ RoomUserDBTableName.room_id }`=:room_id",
        ]
    )
    result = conn.execute(text(query), dict(room_id=room_id))
    for row in result.all():
        room_user: RoomUser = RoomUser.from_orm(row)
        logger.info(f"{room_user}")
        if room_user.user_id == user_id_req:
            room_user.is_me = True
        yield room_user


def get_room_users(room_id: int, user_id_req: int) -> List[RoomUser]:
    with engine.begin() as conn:
        users: List[RoomUser] = list(_get_room_users(conn, room_id, user_id_req=user_id_req))
    return users


def start_room(room_id: int) -> None:
    """update room's status to LiveStart

    Args:
        room_id (int): [description]

    Returns:
        [type]: [description]
    """
    with engine.begin() as conn:
        query: str = " ".join(
            [
                f"UPDATE `{ RoomDBTableName.table_name }`",
                f"SET `{ RoomDBTableName.status }`=:status",
                f"WHERE `{ RoomDBTableName.room_id }`=:room_id",
            ]
        )
        result = conn.execute(
            text(query),
            dict(
                status=int(WaitRoomStatus.LiveStart),
                room_id=room_id,
            ),
        )
        logger.info(f"{result=}")
        return
