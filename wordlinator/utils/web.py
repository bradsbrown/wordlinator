from dash import dcc

###############
# Date Helper #
###############


def _date_range(game):
    return f"{game.start_date} to {game.end_date}"


def get_date_dropdown(dates):
    options = [
        {"label": f"Round {d.game} ({_date_range(d)})", "value": d.game_id}
        for d in dates
    ]

    return dcc.Dropdown(
        id="round-selector-dropdown",
        options=options,
        value=dates[-1].game_id,
        clearable=False,
    )


######################
# Formatting Helpers #
######################


def format_string(col, condition):
    return "{" + col["id"] + "}" + f" {condition}"


def column_formats(col, pct):
    return [
        {
            "if": {"column_id": col["id"]},
            "maxWidth": f"{pct}%",
            "width": f"{pct}%",
            "minWidth": f"{pct}%",
        },
        # Plain and markdown over-par
        {
            "if": {
                "column_id": col["id"],
                "filter_query": format_string(col, "> 4"),
            },
            "backgroundColor": "red",
        },
        {
            "if": {
                "column_id": col["id"],
                "filter_query": format_string(col, 'contains "[5]"'),
            },
            "backgroundColor": "red",
        },
        {
            "if": {
                "column_id": col["id"],
                "filter_query": format_string(col, 'contains "[6]"'),
            },
            "backgroundColor": "red",
        },
        {
            "if": {
                "column_id": col["id"],
                "filter_query": format_string(col, 'contains "[7]"'),
            },
            "backgroundColor": "red",
        },
        # Plain and Markdown par
        {
            "if": {
                "column_id": col["id"],
                "filter_query": format_string(col, "= 4"),
            },
            "backgroundColor": "orange",
        },
        {
            "if": {
                "column_id": col["id"],
                "filter_query": format_string(col, 'contains "[4]"'),
            },
            "backgroundColor": "orange",
        },
        # Plain and markdown under par
        {
            "if": {
                "column_id": col["id"],
                "filter_query": format_string(col, "< 4"),
            },
            "backgroundColor": "green",
        },
        {
            "if": {
                "column_id": col["id"],
                "filter_query": format_string(col, 'contains "[3]"'),
            },
            "backgroundColor": "green",
        },
        {
            "if": {
                "column_id": col["id"],
                "filter_query": format_string(col, 'contains "[2]"'),
            },
            "backgroundColor": "green",
        },
        {
            "if": {
                "column_id": col["id"],
                "filter_query": format_string(col, 'contains "[1]"'),
            },
            "backgroundColor": "green",
        },
        # Plain no score
        {
            "if": {
                "column_id": col["id"],
                "filter_query": format_string(col, "is nil"),
            },
            "backgroundColor": "white",
        },
        {
            "if": {
                "column_id": col["id"],
                "filter_query": format_string(col, "= ''"),
            },
            "backgroundColor": "white",
        },
    ]


def column_formatting(hole_columns):
    pct = round((100 - (10 + 5)) / len(hole_columns), 2)
    return [
        entry
        for format_list in [column_formats(hole, pct) for hole in hole_columns]
        for entry in format_list
    ]
