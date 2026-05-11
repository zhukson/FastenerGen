"""Knowledge prompt behavior for Gong-style leave-one-out evaluation."""

from app.knowledge.loader import format_for_prompt, load_library


def test_format_for_prompt_excludes_holdout_case_everywhere() -> None:
    library = load_library()
    holdout = "DJGS-25-8-B001-0358-四方T帽-106S-过模图"
    record = next(r for r in library.cases if r.case_id == holdout)

    prompt_xml = format_for_prompt(
        library,
        prefer_category=record.product_category,
        part_features=record.part_features,
        exclude_case_ids=[holdout],
    )

    assert holdout not in prompt_xml
    assert "<relevant_subprocesses>" in prompt_xml
    assert "<cases count=\"10\">" in prompt_xml
