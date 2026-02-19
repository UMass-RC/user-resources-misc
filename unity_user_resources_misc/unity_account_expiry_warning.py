import grp
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

from unity_user_resources_misc import fmt_bold, fmt_link, fmt_red, fmt_table

"""
queries the account portal's expiry API to determine when the current user is scheduled to expire
if it's soon, print a warning message
also make the same check for the owners of any PI groups the current user is a member of
"""

IDLELOCK_WARNING_THRESHOLD_DAYS = 5 * 7
IDLELOCK_WARNING_RED_THRESHOLD_DAYS = 7
DISABLE_WARNING_THRESHOLD_DAYS = 9 * 7
DISABLE_WARNING_RED_THRESHOLD_DAYS = 7
PI_GROUP_OWNER_DISABLE_WARNING_RED_THRESHOLD_DAYS = 9 * 7


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


def fmt_red_maybe(x: str, enable: bool):
    if enable:
        return fmt_red(x)
    else:
        return x


ACCOUNT_PORTAL = fmt_link("https://account.unityhpc.org", "Unity account portal")
POLICY = fmt_link("https://unityhpc.org/about/account-expiration/", "account expiration policy")


def print_idlelock_warning(time_until_idlelock: timedelta, red=False):
    time_until_idlelock_str = fmt_red_maybe(timedelta2str(time_until_idlelock), red)
    print(
        "\n".join(
            [
                fmt_red_maybe(fmt_bold("Account Expiration Warning"), red),
                f"Your account is scheduled to be idlelocked in {time_until_idlelock_str}.",
                "Once idlelocked, you will no longer be able to access UnityHPC Platform services.",
                f"To prevent this, simply log in to the {ACCOUNT_PORTAL}.",
                f"For more information, see our {POLICY}.",
                "",
            ]
        )
    )


def print_disable_warning(time_until_disable, owned_pi_group_name: str | None, red=False):
    time_until_disable_str = fmt_red_maybe(timedelta2str(time_until_disable), red)
    print(
        "\n".join(
            [
                fmt_red_maybe(fmt_bold("Account Expiration Warning"), red),
                f"Your account is scheduled to be disabled in {time_until_disable_str}.",
                "Once disabled, you will no longer be able to access UnityHPC Platform services,",
                "and your home directory will be permanently deleted."
                f"To prevent this, simply log in to the {ACCOUNT_PORTAL}.",
            ]
        )
    )
    if owned_pi_group_name is not None:
        print(
            "\n".join(
                [
                    f"If your account is disabled, your PI group '{owned_pi_group_name}' will also be disabled,",
                    "the group's directories will be deleted,"
                    "and all the group's members will lose access to UnityHPC Platform services"
                    "unless they are a member of some other group.",
                ]
            )
        )
    print(f"For more information, see our {POLICY}.")
    print()


def print_pi_group_owner_disable_warning(group_data: list[tuple]):
    if len(group_data) == 0:
        return
    # format all the timedeltas
    group_data = [(x, y, fmt_red(timedelta2str(z))) for x, y, z in group_data]
    print(fmt_red(fmt_bold("PI Group Owner Expiration Warning")))
    if len(group_data) == 1:
        group_name, owner_username, remaining = group_data[0]
        print(
            "\n".join(
                [
                    f"The owner of PI group '{group_name}' is scheduled to be disabled in {remaining}."
                    f"To prevent this, the group owner '{owner_username}' must simply log in to the {ACCOUNT_PORTAL}."
                ]
            )
        )
    else:
        print("The owners of the following PI groups are scheduled to be disabled:")
        table = [["Group Name", "Owner Username", "Time until Disable"]] + group_data
        print("\n".join(fmt_table(table)))
    print(
        "\n".join(
            [
                "You are encouraged to contact the group owner and remind them to log in.",
                "If your PI group owner is disabled, your PI group will also be disabled.",
                "If at any time you are not a member (or owner) of at least one enabled PI group,"
                "You will lose access to UnityHPC Platform services.",
                f"For more information, see our {POLICY},",
                "",
            ]
        )
    )


def get_expiry_data(username: str, timeout_seconds=1) -> dict:
    # normal entrypoint, testable
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    url = f"https://web/lan/api/expiry.php?uid={username}"
    response: HTTPResponse = request.urlopen(url, timeout=timeout_seconds, context=ssl_context)
    message = response.read().decode()
    if response.status != 200:
        raise HTTPError(url, response.status, message, response.headers, None)
    return json.loads(message)


def time_until(_date: str) -> timedelta:
    return date.strptime(_date, r"%Y/%m/%d") - date.today()


def main():
    username = pwd.getpwuid(os.getuid())[0]
    data = get_expiry_data(username)
    time_until_idlelock = time_until(data["idlelock_date"])
    time_until_disable = time_until(data["disable_date"])
    owned_pi_group_name = None
    pi_group_warnings = []
    for gidnumber in os.getgroups():
        group_name = grp.getgrgid(gidnumber)[0]
        if not group_name.startswith("pi_"):
            continue
        owner_username = group_name[3:]
        if owner_username == username:
            owned_pi_group_name = group_name
            continue
        owner_data = get_expiry_data(owner_username)
        remaining = time_until(owner_data["disable_date"])
        if remaining.days <= PI_GROUP_OWNER_DISABLE_WARNING_RED_THRESHOLD_DAYS:
            pi_group_warnings.append((group_name, owner_username, remaining))
    if time_until_disable.days <= DISABLE_WARNING_RED_THRESHOLD_DAYS:
        print_disable_warning(time_until_disable, owned_pi_group_name, red=True)
    elif time_until_disable.days <= DISABLE_WARNING_THRESHOLD_DAYS:
        print_disable_warning(time_until_disable, owned_pi_group_name)
    elif time_until_idlelock.days <= IDLELOCK_WARNING_RED_THRESHOLD_DAYS:
        print_idlelock_warning(time_until_idlelock, red=True)
    elif time_until_idlelock.days <= IDLELOCK_WARNING_THRESHOLD_DAYS:
        print_idlelock_warning(time_until_idlelock)
    print_pi_group_owner_disable_warning(pi_group_warnings)


def main_fail_quietly():
    # entrypoint for production
    try:
        main()
    except Exception as e:
        logging.error("something went wrong", exc_info=e)
        sys.exit(1)
