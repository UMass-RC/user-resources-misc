import json
import logging
import os
import pwd
import ssl
import sys
from datetime import date, timedelta
from http.client import HTTPResponse
from urllib import request
from urllib.error import HTTPError

IDLELOCK_WARNING_THRESHOLD_DAYS = 30
IDLELOCK_WARNING_RED_THRESHOLD_DAYS = 7
DISABLE_WARNING_THRESHOLD_DAYS = 90
DISABLE_WARNING_RED_THRESHOLD_DAYS = 30


def fmt_count(word: str, count: int | float, singular_suffix="", plural_suffix="s"):
    # https://docs.djangoproject.com/en/2.2/ref/templates/builtins/#pluralize
    # examples of different suffixes: hour/hours, walrus/walruses, cherry/cherries
    return f"{count} {word}{singular_suffix if count == 1 else plural_suffix}"


def timedelta2str(x: timedelta):
    hours, minutes, seconds = x.seconds // 3600, x.seconds % 3600 // 60, x.seconds % 60
    if x.days >= 1:
        return fmt_count("day", x.days)
    elif hours >= 1:
        return fmt_count("hour", hours)
    elif minutes >= 1:
        return fmt_count("minute", minutes)
    elif seconds >= 1:
        return fmt_count("second", seconds)
    else:
        return f"{(x.microseconds * 1000 * 1000):.2f} seconds"


def fmt_bold(x: str):
    return f"\033[1m{x}\033[0m"


def fmt_red_maybe(x: str, enable: bool):
    return f"\033[0;31m{x}\033[0m" if enable else x


def fmt_link(url: str, text: str):
    # https://gist.github.com/egmontkob/eb114294efbcd5adb1944c9f3cb5feda
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


ACCOUNT_PORTAL = fmt_link("https://account.unityhpc.org", "Unity account portal")
POLICY = fmt_link("https://unityhpc.org/about/account-expiration/", "account expiration policy")


def print_idlelock_warning(time_until_idlelock: timedelta, red=False):
    time_until_idlelock_str = fmt_red_maybe(timedelta2str(time_until_idlelock), red)
    print(
        "\n".join(
            [
                fmt_bold("Account Expiration Warning"),
                f"Your account is scheduled to be idlelocked in {time_until_idlelock_str}",
                "Once idlelocked, you will no longer be able to access UnityHPC Platform services.",
                f"To prevent this, simply log in to the {ACCOUNT_PORTAL}",
                f"For more information, see our {POLICY}",
            ]
        )
    )


def print_disable_warning(time_until_disable, red=False):
    time_until_disable_str = fmt_red_maybe(timedelta2str(time_until_disable), red)
    print(
        "\n".join(
            [
                fmt_bold("Account Expiration Warning"),
                f"Your account is scheduled to be disabled in {time_until_disable_str}",
                "Once disabled, you will no longer be able to access UnityHPC Platform services,",
                "and your home directory will be permanently deleted."
                f"To prevent this, simply log in to the {ACCOUNT_PORTAL}",
                f"For more information, see our {POLICY}",
            ]
        )
    )


def main():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    username = pwd.getpwuid(os.getuid())[0]
    url = f"https://web/lan/api/expiry.php?uid={username}"
    response: HTTPResponse = request.urlopen(url, timeout=1, context=ssl_context)
    message = response.read().decode()
    if response.status != 200:
        raise HTTPError(url, response.status, message, response.headers, None)
    data = json.loads(message)
    time_until_idlelock = date.strptime(data["idlelock_date"], r"%Y/%m/%d") - date.today()
    time_until_disable = date.strptime(data["disable_date"], r"%Y/%m/%d") - date.today()
    if time_until_disable.days <= DISABLE_WARNING_RED_THRESHOLD_DAYS:
        print_disable_warning(time_until_disable, red=True)
    elif time_until_disable.days <= DISABLE_WARNING_THRESHOLD_DAYS:
        print_disable_warning(time_until_disable)
    elif time_until_idlelock.days <= IDLELOCK_WARNING_RED_THRESHOLD_DAYS:
        print_idlelock_warning(time_until_idlelock, red=True)
    elif time_until_idlelock.days <= IDLELOCK_WARNING_THRESHOLD_DAYS:
        print_idlelock_warning(time_until_idlelock)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error("something went wrong", exc_info=e)
        sys.exit(1)
