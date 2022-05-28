import argparse
import asyncio

import rich
import rich.table

import wordlinator.sheets
import wordlinator.twitter
import wordlinator.utils


async def get_scores(
    wordle_day: wordlinator.utils.WordleDay = wordlinator.utils.WORDLE_TODAY,
):
    users = wordlinator.sheets.SheetsClient().get_users()

    twitter_client = wordlinator.twitter.TwitterClient()

    scores = {}

    for user in users:
        user_scores = await twitter_client.get_user_wordles(user)
        day_score = [s for s in user_scores if s.wordle_day == wordle_day]
        scores[user] = day_score[0] if day_score else None

    return scores


async def main(wordle_day=None):
    scores = await get_scores(wordle_day)

    table = rich.table.Table(
        rich.table.Column(header="Username", style="green"),
        rich.table.Column("Raw Score"),
        rich.table.Column("Golf Score"),
        rich.table.Column("Score Name"),
        title=f"Wordle Scores Day {wordle_day}",
    )
    for username, score in scores.items():
        args = [username]
        if score:
            raw_score = score.raw_score
            if raw_score < 4:
                color = "green"
            elif raw_score == 4:
                color = "orange3"
            elif raw_score > 6:
                color = "red"
            else:
                color = "yellow"

            score_args = [raw_score, score.score, score.score_name]
            args += [f"[{color}]{arg}" for arg in score_args]
        else:
            args += ["N/A"] * 3
        table.add_row(*args)
    rich.print(table)


def _get_day():
    parser = argparse.ArgumentParser("wordlinator")
    days = parser.add_mutually_exclusive_group()
    days.add_argument(
        "--days-ago", type=int, help="The number of days back to pull a score report."
    )
    days.add_argument(
        "--wordle-day", type=int, help="The wordle day number for the score report."
    )
    args = parser.parse_args()
    wordle_day = wordlinator.utils.WORDLE_TODAY
    if args.wordle_day:
        wordle_day = wordlinator.utils.WordleDay.from_wordle_no(args.wordle_day)
    elif args.days_ago:
        wordle_day = wordlinator.utils.WordleDay.from_wordle_no(
            wordle_day.wordle_no - args.days_ago
        )
    return wordle_day


def sync_main():
    wordle_day = _get_day()
    asyncio.run(main(wordle_day=wordle_day))


if __name__ == "__main__":
    sync_main()
