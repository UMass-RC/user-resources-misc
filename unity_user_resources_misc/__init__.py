import re


def printable_length(x: str) -> int:
    assert "\n" not in x and "\t" not in x, "no newlines or tabs allowed!"
    # https://stackoverflow.com/q/14693701/12035739
    ansi_be_gone = re.compile(r"(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]")
    return len(ansi_be_gone.sub("", x))


def fmt_table(table: list[list]) -> list[str]:
    """
    I would use tabulate but I don't want nonstandard imports
    no table headers
    allows ANSI formatted elements
    """
    output_lines = []
    assert all(len(row) == len(table[0]) for row in table), "all rows must have the same length"
    column_widths = [0] * len(table[0])
    for row in table:
        for i, element in enumerate(row):
            if printable_length(str(element)) > column_widths[i]:
                column_widths[i] = printable_length(str(element))
    column_widths = [x + 1 for x in column_widths]  # add one space in between
    for row in table:
        line = ""
        for i, value in enumerate(row):
            padding_size = column_widths[i] - printable_length(value)
            line += value + " " * padding_size
        output_lines.append(line)
    return output_lines


def red(x) -> str:
    return f"\033[0;31m{x}\033[0m"


def human_readable_size(size_in_bytes: int) -> str:
    current_size = size_in_bytes
    current_unit = "bytes"
    for new_unit in ["KB", "MB", "GB", "TB", "PB"]:
        new_size = current_size / 1000
        if new_size < 1:
            break
        else:
            current_size = new_size
            current_unit = new_unit
    if current_unit == "bytes":
        return f"{current_size} bytes"  # no decimals
    else:
        return f"{current_size:.2f} {current_unit}"


def human_readable_count(count: int) -> str:
    current_count = count
    current_unit = ""
    for new_unit in ["thousand", "million", "billion", "trillion", "quadrillion"]:
        new_count = current_count / 1000
        if new_count < 1:
            break
        else:
            current_count = new_count
            current_unit = new_unit
    if current_unit == "":
        return str(current_count)  # no decimals
    else:
        return f"{current_count:.2f} {current_unit}"
