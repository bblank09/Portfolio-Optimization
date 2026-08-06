from scripts.sec_build_mvp_universe import select_universe


def make_row(proj_id: str, policy_desc: str) -> dict:
    return {
        "proj_id": proj_id,
        "unique_id": f"U-{proj_id}",
        "fund_class_name": "main",
        "class_abbr_name": "main",
        "display_name": f"Fund {proj_id}",
        "search_term": policy_desc,
        "amc_name_th": "",
        "amc_name_en": "",
        "policy_desc": policy_desc,
    }


def test_select_universe_always_keeps_preferred_funds_first():
    candidates = [
        make_row("EQ1", "ตราสารทุน"),
        make_row("EQ2", "ตราสารทุน"),
        make_row("PREFERRED", "ผสม"),
        make_row("FI1", "ตราสารหนี้"),
    ]

    selected = select_universe(candidates, preferred_proj_ids=["PREFERRED"], max_funds=4)

    assert selected[0]["proj_id"] == "PREFERRED"
    assert {row["proj_id"] for row in selected} == {"PREFERRED", "EQ1", "EQ2", "FI1"}


def test_select_universe_keeps_preferred_funds_even_under_a_tight_budget():
    # A capped universe must never silently drop the funds the frontend's
    # "Load an example portfolio" shortcut and several backend tests depend
    # on existing in data/sec/mvp_fund_universe.csv.
    candidates = [make_row(f"OTHER{i}", "ตราสารทุน") for i in range(20)]
    candidates.append(make_row("PREFERRED_A", "ผสม"))
    candidates.append(make_row("PREFERRED_B", "ตราสารหนี้"))

    selected = select_universe(candidates, preferred_proj_ids=["PREFERRED_A", "PREFERRED_B"], max_funds=2)

    assert {row["proj_id"] for row in selected} == {"PREFERRED_A", "PREFERRED_B"}


def test_select_universe_diversifies_the_remaining_budget_across_categories():
    # A budget-capped universe that just took the first N candidates could
    # end up all-equity if the API happens to page equity funds first --
    # round-robin across policy_desc buckets keeps every asset class
    # represented even when the total universe is much larger than the cap.
    candidates = (
        [make_row(f"EQ{i}", "ตราสารทุน") for i in range(10)]
        + [make_row(f"FI{i}", "ตราสารหนี้") for i in range(10)]
        + [make_row(f"MM{i}", "ตลาดเงิน") for i in range(10)]
    )

    selected = select_universe(candidates, preferred_proj_ids=[], max_funds=9)

    categories = [row["policy_desc"] for row in selected]
    assert categories.count("ตราสารทุน") == 3
    assert categories.count("ตราสารหนี้") == 3
    assert categories.count("ตลาดเงิน") == 3


def test_select_universe_deduplicates_by_proj_id():
    candidates = [make_row("A", "ตราสารทุน"), make_row("A", "ตราสารทุน")]

    selected = select_universe(candidates, preferred_proj_ids=[], max_funds=10)

    assert len(selected) == 1


def test_select_universe_respects_max_funds_even_with_a_larger_candidate_pool():
    candidates = [make_row(f"F{i}", "ตราสารทุน") for i in range(50)]

    selected = select_universe(candidates, preferred_proj_ids=[], max_funds=5)

    assert len(selected) == 5


def test_select_universe_picks_highest_aum_funds_first_within_each_category():
    # Within a category, the popularity-ranked fill must take the
    # highest-AUM candidates first, not whatever order the SEC API paged
    # them in -- see scripts/sec_fetch_fund_aum.py for how aum_by_proj_id
    # is produced.
    candidates = [make_row(f"EQ{i}", "ตราสารทุน") for i in range(5)]
    aum_by_proj_id = {"EQ0": 10, "EQ1": 500, "EQ2": 100, "EQ3": 50, "EQ4": 1}

    selected = select_universe(candidates, preferred_proj_ids=[], max_funds=3, aum_by_proj_id=aum_by_proj_id)

    assert [row["proj_id"] for row in selected] == ["EQ1", "EQ2", "EQ3"]


def test_select_universe_sorts_funds_with_unknown_aum_after_known_aum():
    candidates = [make_row(f"EQ{i}", "ตราสารทุน") for i in range(4)]
    # EQ0 and EQ3 have no resolved AUM -- they must fill in only after every
    # fund with a known AUM, in their original relative order.
    aum_by_proj_id = {"EQ1": 100, "EQ2": 200}

    selected = select_universe(candidates, preferred_proj_ids=[], max_funds=4, aum_by_proj_id=aum_by_proj_id)

    assert [row["proj_id"] for row in selected] == ["EQ2", "EQ1", "EQ0", "EQ3"]
