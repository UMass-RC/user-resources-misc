# in theory 99% of the time spent in IO wait so it doesn't matter that python is a slow language?
# edit: it does matter. this is twice as slow as `du`.
import itertools
import os
import pwd
import sys

# import signal
# import atexit
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from unity_user_resources_misc import fmt_table, human_readable_count, human_readable_size

"""
multithreaded `du` command that displays the total bytes owned by ecah user
if possible, uses `statvfs` to determine the total number inodes in the directory,
and displays a progress bar based on the number of inodes processed at a given time
"""

NUM_THREADS = 4


@lru_cache(maxsize=None)
def uid2username(uid: int) -> str:
    return pwd.getpwuid(uid).pw_name


def get_total_inodes_used_statvfs(path) -> int | None:
    """
    assumption: when `statvfs` produces different results for `path` and `dirname(path)`,
    the results for `path` are accurate.
    """
    cwd_statvfs = os.statvfs(path)
    parent_statvfs = os.statvfs(os.path.dirname(path))
    if cwd_statvfs == parent_statvfs:
        return None
    return cwd_statvfs.f_files - cwd_statvfs.f_ffree


# def enable_alternate_screen_mode():
#     print("\033[?1049h\033[H")

# def disable_alternate_screen_mode():
#     print("\033[?1049l")

# def sigint_handler(x, y):
#     disable_alternate_screen_mode()
#     sys.exit(1)


class UnityDiskUsagePerUser:
    def __init__(self):
        self.counting_lock = threading.Lock()
        self.done_counting = threading.Event()
        self.uid2bytes_owned = {}
        self.uid2paths_and_sizes = {}
        self.total_inodes_counted = 0
        self.total_inodes_used = None
        self.total_bytes_used = 0

    def add_file_to_totals(self, path: str):
        stat = os.stat(path)
        with self.counting_lock:
            self.uid2bytes_owned[stat.st_uid] = (
                self.uid2bytes_owned.get(stat.st_uid, 0) + stat.st_size
            )
            self.uid2paths_and_sizes.setdefault(stat.st_uid, []).append([path, stat.st_size])
            self.total_inodes_counted += 1
            self.total_bytes_used += stat.st_size

    def print_current_totals(self):
        if self.total_inodes_used is None:
            print(f"inodes counted: {human_readable_count(self.total_inodes_counted)}")
        else:
            progress_percent = (self.total_inodes_counted / self.total_inodes_used) * 100
            print(
                f"inodes counted: {self.total_inodes_counted} / {self.total_inodes_used} = {progress_percent:.1f}%"
            )
        if len(self.uid2bytes_owned) == 0:
            return
        sorted_uid2bytes_owned = {
            k: v for k, v in sorted(self.uid2bytes_owned.items(), key=lambda x: x[1], reverse=True)
        }
        usage_table = []
        for uid, bytes_owned in sorted_uid2bytes_owned.items():
            pcent = (bytes_owned / self.total_bytes_used) * 100
            usage_table.append(
                [uid2username(uid), human_readable_size(bytes_owned), f"{pcent:.1f}%"]
            )
        for line in fmt_table(usage_table):
            print(line)
        print()

    def loop_print_current_totals(self, sleep_seconds=1):
        while not self.done_counting.is_set():
            self.print_current_totals()
            time.sleep(sleep_seconds)

    def main(self):
        # enable_alternate_screen_mode()
        # atexit.register(disable_alternate_screen_mode)
        # signal.signal(signal.SIGINT, sigint_handler)
        self.total_inodes_used = get_total_inodes_used_statvfs(os.path.realpath(os.getcwd()))
        if self.total_inodes_used == None:
            print(
                "this directory does not have a unique statvfs, so inode counting progress cannot be determined.",
                file=sys.stderr,
            )
        print_current_totals_thread = threading.Thread(
            target=self.loop_print_current_totals, daemon=True
        )
        print_current_totals_thread.start()
        with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
            walk_gen = os.walk(".")
            walk_path_gen = itertools.chain.from_iterable(
                (os.path.join(root, basename) for basename in files + dirs)
                for root, dirs, files in walk_gen
            )
            executor.map(self.add_file_to_totals, walk_path_gen)
        self.print_current_totals()
        # self.done_counting.set()
        # print_current_totals_thread.join()


def main():
    x = UnityDiskUsagePerUser()
    x.main()
