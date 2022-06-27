import argparse
import dataclasses
import datetime
import typing

import wordlinator.db.pg

WORDLE_DAY_ZERO = datetime.date(2021, 6, 19)

WORDLE_GOLF_ROUNDS = wordlinator.db.pg.WordleDb().get_rounds()


def date_from_string(datestr: str):
    try:
        return datetime.date.fromisoformat(datestr)
    except ValueError:
        msg = "Invalid date string, expected format: YYYY-mm-DD"
        raise argparse.ArgumentTypeError(msg)


@dataclasses.dataclass
class GolfHole:
    game_no: int
    hole_no: int

    @classmethod
    def from_date(cls, date: datetime.date):
        for round in WORDLE_GOLF_ROUNDS:
            if round.start_date <= date <= round.end_date:
                hole_no = (date - round.start_date).days + 1
                return cls(game_no=round.game, hole_no=hole_no)
        return None


@dataclasses.dataclass
class WordleDay:
    wordle_no: int
    date: datetime.date
    golf_hole: typing.Optional[GolfHole]

    @classmethod
    def from_wordle_no(cls, wordle_no: int):
        wordle_no = int(wordle_no)
        date = WORDLE_DAY_ZERO + datetime.timedelta(days=wordle_no)
        golf_hole = GolfHole.from_date(date)
        return cls(wordle_no=wordle_no, date=date, golf_hole=golf_hole)

    @classmethod
    def from_date(cls, date: datetime.date):
        wordle_no = (date - WORDLE_DAY_ZERO).days
        golf_hole = GolfHole.from_date(date)
        return cls(wordle_no=wordle_no, date=date, golf_hole=golf_hole)

    def __eq__(self, other):
        return self.wordle_no == other.wordle_no


# Designed so that "today" will be the current date in CST
# Regardless of where the code is run
def get_today_central():
    today = (
        datetime.datetime.now(datetime.timezone.utc)
        .astimezone(datetime.timezone(datetime.timedelta(hours=-5), name="US Central"))
        .date()
    )
    return today


def get_wordle_today():
    return WordleDay.from_date(get_today_central())


WORDLE_TODAY = get_wordle_today()
