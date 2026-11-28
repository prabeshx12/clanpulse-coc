"""Database tables for the war tracker.

All datetimes are stored as naive UTC (SQLite has no timezone type).
"""
from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Member(Base):
    """A clan member, kept even after they leave (in_clan=False) so history stays linked."""

    __tablename__ = "members"

    tag: Mapped[str] = mapped_column(String(15), primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    town_hall: Mapped[int]
    role: Mapped[str] = mapped_column(String(20))        # API values: member/admin/coLeader/leader
    first_seen: Mapped[datetime]
    last_seen: Mapped[datetime]
    in_clan: Mapped[bool] = mapped_column(default=True)

    participations: Mapped[list["WarParticipant"]] = relationship(back_populates="member")

    def __repr__(self) -> str:
        return f"Member({self.tag} {self.name!r} TH{self.town_hall})"


class War(Base):
    """One war (regular or CWL). The API has no war ID, so (opponent_tag, start_time) is unique."""

    __tablename__ = "wars"
    __table_args__ = (UniqueConstraint("opponent_tag", "start_time", name="uq_war_opponent_start"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    opponent_tag: Mapped[str] = mapped_column(String(15))
    opponent_name: Mapped[str] = mapped_column(String(50))
    team_size: Mapped[int]
    attacks_per_member: Mapped[int]                      # 2 regular, 1 CWL
    preparation_start_time: Mapped[datetime]
    start_time: Mapped[datetime]
    end_time: Mapped[datetime]
    state: Mapped[str] = mapped_column(String(20))       # preparation/inWar/warEnded
    result: Mapped[str | None] = mapped_column(String(10))  # win/lose/tie, set at warEnded
    is_cwl: Mapped[bool] = mapped_column(default=False)

    clan_stars: Mapped[int] = mapped_column(default=0)
    clan_destruction: Mapped[float] = mapped_column(default=0.0)
    opponent_stars: Mapped[int] = mapped_column(default=0)
    opponent_destruction: Mapped[float] = mapped_column(default=0.0)

    # cascade: deleting a War also deletes its participants and attacks
    participants: Mapped[list["WarParticipant"]] = relationship(
        back_populates="war", cascade="all, delete-orphan"
    )
    attacks: Mapped[list["WarAttack"]] = relationship(
        back_populates="war", cascade="all, delete-orphan", order_by="WarAttack.order"
    )

    def __repr__(self) -> str:
        return f"War({self.id} vs {self.opponent_name!r} {self.state} {self.result})"


class WarParticipant(Base):
    """One of OUR members in a war's lineup. Tracks attacks used vs allowed."""

    __tablename__ = "war_participants"

    war_id: Mapped[int] = mapped_column(ForeignKey("wars.id"), primary_key=True)
    member_tag: Mapped[str] = mapped_column(ForeignKey("members.tag"), primary_key=True)
    map_position: Mapped[int]
    town_hall: Mapped[int]                               # TH at the time of this war
    attacks_used: Mapped[int] = mapped_column(default=0)
    attacks_allowed: Mapped[int]

    war: Mapped[War] = relationship(back_populates="participants")
    member: Mapped[Member] = relationship(back_populates="participations")

    @property
    def missed_attacks(self) -> int:
        """Attacks not used. Only meaningful once the war has ended."""
        return max(self.attacks_allowed - self.attacks_used, 0)

    def __repr__(self) -> str:
        return f"WarParticipant(war={self.war_id} {self.member_tag} #{self.map_position})"


class WarAttack(Base):
    """One attack by OUR member. `order` is the attack's sequence number within the war."""

    __tablename__ = "war_attacks"
    __table_args__ = (UniqueConstraint("war_id", "order", name="uq_attack_war_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    war_id: Mapped[int] = mapped_column(ForeignKey("wars.id"))
    attacker_tag: Mapped[str] = mapped_column(ForeignKey("members.tag"))
    defender_tag: Mapped[str] = mapped_column(String(15))  # opponent's tag, not in members
    stars: Mapped[int]
    destruction: Mapped[float]
    order: Mapped[int]
    duration: Mapped[int]                                # seconds

    war: Mapped[War] = relationship(back_populates="attacks")

    def __repr__(self) -> str:
        return f"WarAttack(war={self.war_id} #{self.order} {self.stars}★ {self.destruction}%)"
