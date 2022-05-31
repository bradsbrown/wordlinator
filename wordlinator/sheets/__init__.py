import itertools
import os
import pathlib

import google.oauth2.credentials
import google.oauth2.service_account
import googleapiclient.discovery
import rich
import rich.table

import wordlinator.utils

SPREADSHEET_ID = "1POoklzvD643pvdMAleFxrecN50IMv2NdQBs9h43Hw8E"
SHEET_NAME = os.getenv("SHEET_NAME", None)
USER_RANGE = "A2:A1000"
SCORE_RANGE = "C2:T1000"


class SheetsClient:
    FILLER_VALUE = "7"

    def __init__(
        self,
        wordle_day: wordlinator.utils.WordleDay = wordlinator.utils.WORDLE_TODAY,
        sheet_id=SPREADSHEET_ID,
        sheet_name=SHEET_NAME,
        user_range=USER_RANGE,
        score_range=SCORE_RANGE,
    ):
        creds = {"developerKey": os.getenv("SHEET_API_KEY")}
        env_path = os.getenv("SHEET_TOKEN_FILE_PATH")
        if env_path:
            token_file = pathlib.Path(env_path)
        else:
            token_file = pathlib.Path.cwd() / "token.json"
        if token_file.exists():
            cred_obj = google.oauth2.service_account.Credentials
            creds = {"credentials": cred_obj.from_service_account_file(str(token_file))}
        self.client = googleapiclient.discovery.build("sheets", "v4", **creds)
        self.sheet_id = sheet_id
        self.sheet_name = sheet_name
        self.user_range = user_range
        self.score_range = score_range
        if not wordle_day.golf_hole:
            self.game_round = None
        else:
            self.game_round = wordle_day.golf_hole.hole_no
            if not self.sheet_name:
                self.sheet_name = f"Round {wordle_day.golf_hole.game_no}"

    def _get_sheet_values(self, range):
        sheets = self.client.spreadsheets()
        result = sheets.values().get(spreadsheetId=self.sheet_id, range=range).execute()
        return result.get("values", [])

    def get_users(self):
        rows = self._get_sheet_values(f"{self.sheet_name}!{self.user_range}")
        return list(filter(None, [row[0] for row in rows]))

    def _normalize_scores(self, scores_value, completed_only=True):
        if not self.game_round:
            # Can't normalize if we're not in a game.
            return scores_value
        scores = []
        for score in scores_value or []:
            scores.append(score or self.FILLER_VALUE)
        expected_len = self.game_round
        if completed_only:
            expected_len = expected_len - 1
        current_len = len(scores)
        if current_len < expected_len:
            filler = [self.FILLER_VALUE] * (expected_len - current_len)
            scores = scores + filler
        return scores

    def score_dict(self, names, scores, completed_only=True):
        score_data = dict(itertools.zip_longest(names, scores))
        for name in score_data:
            score_data[name] = self._normalize_scores(
                score_data[name], completed_only=completed_only
            )
        return score_data

    def get_scores(self, completed_only=True):
        sheets = self.client.spreadsheets()
        result = (
            sheets.values()
            .batchGet(
                spreadsheetId=self.sheet_id,
                ranges=[
                    f"{self.sheet_name}!{self.user_range}",
                    f"{self.sheet_name}!{self.score_range}",
                ],
            )
            .execute()
        )
        ranges = result.get("valueRanges", [])
        names = [row[0] for row in ranges[0].get("values", [])]
        scores = ranges[1].get("values", [])
        return self.score_dict(names, scores, completed_only=completed_only)

    def write_scores(self, score_dict):
        body = {"values": list(score_dict.values())}
        sheets = self.client.spreadsheets()
        result = (
            sheets.values()
            .update(
                spreadsheetId=self.sheet_id,
                range=f"{self.sheet_name}!{self.score_range}",
                body=body,
                valueInputOption="USER_ENTERED",
            )
            .execute()
        )
        return result

    def update_scores(self, day_scores_dict):
        if self.game_round is None:
            raise ValueError("Cannot update scores if not in a game round")
        current_scores = self.get_scores()
        for name, score in day_scores_dict.items():
            current_row = current_scores[name]
            row_len = len(current_row)
            score_val = str(score.raw_score) if score else ""
            if row_len == (self.game_round - 1):
                # If the row doesn't include today yet, add it.
                current_row.append(score_val)
            elif row_len >= self.game_round:
                # If there's already an entry for today's game,
                # only update if the value is empty.
                day_idx = self.game_round - 1
                if current_row[day_idx] == "":
                    current_row[day_idx] = score_val
            current_scores[name] = current_row
        self.write_scores(current_scores)


def main():
    scores = SheetsClient().get_scores()
    score_cols = [rich.table.Column(f"{i}") for i in range(1, 19)]
    table = rich.table.Table(
        rich.table.Column("Username", min_width=20),
        *score_cols,
        title="WordleGolf Players",
    )
    for name, score_list in scores.items():
        table.add_row(name, *score_list)
    rich.print(table)


if __name__ == "__main__":
    main()
