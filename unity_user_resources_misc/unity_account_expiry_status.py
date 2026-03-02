import os
import pwd

from unity_user_resources_misc.unity_account_expiry_warning import (
    IDLELOCK_WARNING_THRESHOLD_DAYS,
    get_expiry_data,
    print_idlelock_warning,
    time_until,
)


def main():
    username = pwd.getpwuid(os.getuid())[0]
    data = get_expiry_data(username)
    time_until_idlelock = time_until(data["idlelock_date"])
    if time_until_idlelock.days < IDLELOCK_WARNING_THRESHOLD_DAYS:
        print_idlelock_warning(time_until_idlelock)
    else:
        print("Your account is not considered idle, and is not scheduled to be locked.")
