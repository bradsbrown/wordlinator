import dataclasses
import datetime
import typing

WORDLE_DAY_ZERO = datetime.date(2021, 6, 19)

WORDLE_GOLF_ROUND_DATES = [datetime.date(2022, 5, 9), datetime.date(2022, 5, 31)]


@dataclasses.dataclass
class GolfHole:
    game_no: int
    hole_no: int

    @classmethod
    def from_date(cls, date: datetime.date):
        for game_no, start_date in enumerate(WORDLE_GOLF_ROUND_DATES, start=1):
            hole_value = (date - start_date).days + 1
            if 1 <= hole_value <= 18:
                return cls(game_no=game_no, hole_no=hole_value)
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
def get_wordle_today():
    today = (
        datetime.datetime.now(datetime.timezone.utc)
        .astimezone(datetime.timezone(datetime.timedelta(hours=-5), name="US Central"))
        .date()
    )
    return WordleDay.from_date(today)


WORDLE_TODAY = get_wordle_today()
