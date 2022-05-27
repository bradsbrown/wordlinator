import os

import googleapiclient.discovery
import rich
import rich.table

WORDLEGOLF_SPREADSHEET_ID = "1POoklzvD643pvdMAleFxrecN50IMv2NdQBs9h43Hw8E"
WORDLEGOLF_RANGE_NAME = "Round 1!A2:A100"


def _get_sheets_client():
    return googleapiclient.discovery.build(
        "sheets", "v4", developerKey=os.getenv("SHEET_API_KEY")
    )


def _get_sheet_values(client, range):
    sheet = client.spreadsheets()
    result = (
        sheet.values()
        .get(spreadsheetId=WORDLEGOLF_SPREADSHEET_ID, range=range)
        .execute()
    )
    return result.get("values", [])


def get_wordlegolf_users():
    client = _get_sheets_client()
    res = _get_sheet_values(client, WORDLEGOLF_RANGE_NAME)
    return [row[0] for row in res]


def main():
    users = get_wordlegolf_users()
    table = rich.table.Table("Username", title="WordleGolf Players")
    for user in users:
        table.add_row(user)
    rich.print(table)


if __name__ == "__main__":
    main()
