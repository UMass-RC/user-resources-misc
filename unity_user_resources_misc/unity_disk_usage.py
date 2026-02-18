import grp
import os
import shutil

from unity_user_resources_misc import fmt_table, human_readable_size, red

"""
basically a wrapper around `df`
"""

USAGE_PERCENT_RED_THRESHOLD = 75


def main():
    usage = []

    # if timed out, print whatever usage has been collected so far
    # this was removed since bad NFS requires sigkill
    # signal.signal(signal.SIGTERM, lambda foo, bar: print_usage_and_exit())

    dirs_to_check = [os.path.expanduser("~")]  # home directory
    for gid in os.getgroups():
        gr_name = grp.getgrgid(gid).gr_name
        if not gr_name.startswith("pi_"):
            continue
        for prefix in "/project", "/work":
            dir_path = os.path.join(prefix, gr_name)
            if os.path.isdir(dir_path):
                dirs_to_check.append(dir_path)

    for dir_path in dirs_to_check:
        total, used, _ = shutil.disk_usage(dir_path)
        pcent_used = (used / total) * 100
        if pcent_used >= USAGE_PERCENT_RED_THRESHOLD:
            usage.append(
                [
                    dir_path,
                    red(human_readable_size(used)),
                    red("/"),
                    red(human_readable_size(total)),
                    red("="),
                    red(f"{(pcent_used):.0f}%"),
                ]
            )
        else:
            usage.append(
                [
                    dir_path,
                    human_readable_size(used),
                    "/",
                    human_readable_size(total),
                    "=",
                    f"{(pcent_used):.0f}%",
                ]
            )
    if usage != []:
        for line in fmt_table(usage):
            print(line)


if __name__ == "__main__":
    main()
