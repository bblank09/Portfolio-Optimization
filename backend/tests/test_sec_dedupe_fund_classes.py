import pandas as pd

from scripts.sec_dedupe_fund_classes import resolve_class_to_keep


def test_resolve_class_to_keep_prefers_the_expected_class_when_present():
    classes = pd.Series(["main", "HIDIV-D", "HIDIV-AR", "HIDIV-AR"])

    resolved = resolve_class_to_keep(classes, expected_class="HIDIV-AR")

    assert resolved == "HIDIV-AR"


def test_resolve_class_to_keep_falls_back_to_the_most_common_class_when_expected_is_absent():
    # SEC's fund-profiles endpoint and its daily-info/nav endpoint
    # occasionally disagree on the class-name string for what is
    # presumably the same underlying series (e.g. "K-SELECT-A(A)" vs.
    # "K-SELECT-A(D)"/"main"). Dropping 100% of that fund's data would
    # leave a zero-data ghost entry in the universe; picking the class
    # with the most history is the closest available approximation.
    classes = pd.Series(["main"] * 5 + ["K-SELECT-A(D)"] * 2)

    resolved = resolve_class_to_keep(classes, expected_class="K-SELECT-A(A)")

    assert resolved == "main"


def test_resolve_class_to_keep_handles_a_missing_expected_class_value():
    classes = pd.Series(["only-class", "only-class"])

    resolved = resolve_class_to_keep(classes, expected_class=float("nan"))

    assert resolved == "only-class"
