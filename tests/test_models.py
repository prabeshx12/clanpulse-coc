"""Tests for app/models.py using a throwaway in-memory SQLite database."""
from collections.abc import Iterator
from datetime import datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import init_db, make_engine, make_session_factory
from app.models import Member, War, WarAttack, WarParticipant

T0 = datetime(2026, 11, 22, 18, 30)
T1 = datetime(2026, 11, 23, 18, 30)
T2 = datetime(2026, 11, 24, 18, 30)


@pytest.fixture
def session() -> Iterator[Session]:
    """A fresh empty database for every test."""
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    with make_session_factory(engine)() as s:
        yield s


def make_member(tag: str = "#AAA", name: str = "alice") -> Member:
    return Member(tag=tag, name=name, town_hall=15, role="member", first_seen=T0, last_seen=T0)


def make_war(opponent_tag: str = "#OPP", start: datetime = T1) -> War:
    return War(
        opponent_tag=opponent_tag, opponent_name="ouwe NL", team_size=10,
        attacks_per_member=2, preparation_start_time=T0, start_time=start,
        end_time=T2, state="warEnded", result="win",
    )


def test_war_with_participants_and_attacks_round_trips(session: Session) -> None:
    alice = make_member()
    war = make_war()
    war.participants.append(
        WarParticipant(member=alice, map_position=1, town_hall=15, attacks_used=1, attacks_allowed=2)
    )
    war.attacks.append(WarAttack(
        attacker_tag="#AAA", defender_tag="#DEF", stars=3, destruction=100, order=5, duration=90,
    ))
    session.add_all([alice, war])
    session.commit()

    loaded = session.scalars(select(War)).one()
    assert loaded.participants[0].member.name == "alice"
    assert loaded.attacks[0].stars == 3
    assert alice.participations[0].war is loaded     # relationship works both ways


def test_missed_attacks() -> None:
    p = WarParticipant(map_position=1, town_hall=15, attacks_used=1, attacks_allowed=2)
    assert p.missed_attacks == 1


def test_same_war_cannot_be_stored_twice(session: Session) -> None:
    session.add(make_war())
    session.commit()

    session.add(make_war())                       # same opponent + start_time
    with pytest.raises(IntegrityError):
        session.commit()


def test_same_attack_order_cannot_repeat_in_a_war(session: Session) -> None:
    session.add(make_member())
    war = make_war()
    for _ in range(2):
        war.attacks.append(WarAttack(
            attacker_tag="#AAA", defender_tag="#DEF", stars=1, destruction=50, order=7, duration=60,
        ))
    session.add(war)
    with pytest.raises(IntegrityError):
        session.commit()


def test_foreign_keys_are_enforced(session: Session) -> None:
    """Proves the SQLite PRAGMA is on: an attack by an unknown member is rejected."""
    war = make_war()
    war.attacks.append(WarAttack(
        attacker_tag="#NOBODY", defender_tag="#DEF", stars=1, destruction=50, order=1, duration=60,
    ))
    session.add(war)
    with pytest.raises(IntegrityError):
        session.commit()


def test_deleting_war_cascades_to_children(session: Session) -> None:
    alice = make_member()
    war = make_war()
    war.participants.append(
        WarParticipant(member=alice, map_position=1, town_hall=15, attacks_allowed=2)
    )
    war.attacks.append(WarAttack(
        attacker_tag="#AAA", defender_tag="#DEF", stars=2, destruction=80, order=1, duration=60,
    ))
    session.add(war)
    session.commit()

    session.delete(war)
    session.commit()

    assert session.scalar(select(func.count()).select_from(WarParticipant)) == 0
    assert session.scalar(select(func.count()).select_from(WarAttack)) == 0
    assert session.get(Member, "#AAA") is not None   # members survive
