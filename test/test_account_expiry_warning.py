#!/usr/bin/env python3
import contextlib
import io
import re
import unittest
from datetime import datetime, timedelta
from unittest.mock import _patch, patch

from unity_user_resources_misc.unity_account_expiry_warning import _main

"""
see README.md for instructions on how to run tests
to debug a test, use the `debug` parameter for `configure_test`
"""


def days_from_today(x: int) -> str:
    return datetime.strftime(datetime.today() + timedelta(days=x), "%Y/%m/%d")


class TestCleanupQuotas(unittest.TestCase):
    patches: list[_patch]
    stdout_buffer: io.StringIO | None
    stderr_buffer: io.StringIO | None

    def configure_test(
        self,
        data: dict[str, dict[str, str]],
        current_user: str,
        groups: list[str] | None = None,
        idlelock_thresh=-1,
        idlelock_red_thresh=-1,
        group_thresh=-1,
    ):
        groups = [] if groups is None else groups
        prefix = "unity_user_resources_misc.unity_account_expiry_warning"
        self.patches = [
            patch(f"{prefix}.IDLELOCK_WARNING_THRESHOLD_DAYS", idlelock_thresh),
            patch(f"{prefix}.IDLELOCK_WARNING_RED_THRESHOLD_DAYS", idlelock_red_thresh),
            patch(f"{prefix}.PI_GROUP_OWNER_DISABLE_WARNING_RED_THRESHOLD_DAYS", group_thresh),
            patch(f"{prefix}.get_expiry_data", lambda x: data[x]),
            patch(f"{prefix}.os.getuid", lambda: 1),
            patch(f"{prefix}.pwd.getpwuid", lambda uidnumber: [current_user]),
            patch(f"{prefix}.os.getgroups", lambda: range(len(groups))),
            patch(f"{prefix}.grp.getgrgid", lambda gid: groups[gid]),
        ]
        for p in self.patches:
            p.start()
        self.stdout_buffer = io.StringIO()
        self.stderr_buffer = io.StringIO()

    def run_test(self) -> None:
        with contextlib.redirect_stdout(self.stdout_buffer):
            with contextlib.redirect_stderr(self.stderr_buffer):
                _main()

    def assert_test_results(self, expected_stdout_regex: str, expected_stderr_regex: str):
        assert self.stdout_buffer is not None and self.stderr_buffer is not None
        assert re.fullmatch(expected_stdout_regex, self.stdout_buffer.getvalue().strip())
        assert re.fullmatch(expected_stderr_regex, self.stderr_buffer.getvalue().strip())
        self.stdout_buffer = None
        self.stderr_buffer = None
        for p in self.patches:
            p.stop()

    def test_no_warnings(self):
        self.configure_test(
            {
                "foo": {"idlelock_date": days_from_today(100)},
                "bar": {"disable_date": days_from_today(100)},
            },
            "foo",
            ["pi_bar"],
            idlelock_thresh=2,
            idlelock_red_thresh=1,
            group_thresh=1,
        )
        self.run_test()
        self.assert_test_results(r"", r"")
