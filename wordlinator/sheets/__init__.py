import os

import googleapiclient.discovery
import rich
import rich.table

SPREADSHEET_ID = "1POoklzvD643pvdMAleFxrecN50IMv2NdQBs9h43Hw8E"
SHEET_NAME = "Round 1"
USER_RANGE = "A2:A1000"


class SheetsClient:
    def __init__(
        self, sheet_id=SPREADSHEET_ID, sheet_name=SHEET_NAME, user_range=USER_RANGE
    ):
        creds = {"developerKey": os.getenv("SHEET_API_KEY")}
        self.client = googleapiclient.discovery.build("sheets", "v4", **creds)
        self.sheet_id = sheet_id
        self.sheet_name = sheet_name
        self.user_range = user_range

    def _get_sheet_values(self, range):
        sheets = self.client.spreadsheets()
        result = sheets.values().get(spreadsheetId=self.sheet_id, range=range).execute()
        return result.get("values", [])

    def get_users(self):
        rows = self._get_sheet_values(f"{self.sheet_name}!{self.user_range}")
        return list(filter(None, [row[0] for row in rows]))


def main():
    users = SheetsClient().get_users()
    table = rich.table.Table("Username", title="WordleGolf Players")
    for user in users:
        table.add_row(user)
    rich.print(table)


if __name__ == "__main__":
    main()
