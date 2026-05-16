"""Knowledge behavior for Gong-style leave-one-out evaluation."""

from app.knowledge.loader import compute_neighbor_density, format_for_prompt, load_library


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
    assert "<cases count=\"12\">" in prompt_xml


def test_compact_prompt_keeps_rules_but_retrieves_cases() -> None:
    library = load_library()
    holdout = "DJGS-25-8-B001-0358-四方T帽-106S-过模图"
    record = next(r for r in library.cases if r.case_id == holdout)

    full_xml = format_for_prompt(
        library,
        prefer_category=record.product_category,
        part_features=record.part_features,
        exclude_case_ids=[holdout],
    )
    compact_xml = format_for_prompt(
        library,
        prefer_category=record.product_category,
        part_features=record.part_features,
        exclude_case_ids=[holdout],
        compact=True,
    )

    assert holdout not in compact_xml
    assert "<relevant_subprocesses>" in compact_xml
    assert "<rules>" in compact_xml
    assert "<textbook_knowledge>" in compact_xml
    assert "mode=\"compact\"" in compact_xml
    assert "<cases count=\"10\">" not in compact_xml
    assert "<textbook_cases count=\"27\">" not in compact_xml
    assert len(compact_xml) < len(full_xml) * 0.65


def test_loader_includes_local_visual_m14_standard_case() -> None:
    library = load_library()
    record = next(
        r for r in library.standards
        if r.case_id == "STD-DIN912-M14-P2.0-40-60L"
    )

    prompt_xml = format_for_prompt(
        library,
        prefer_category=record.product_category,
        part_features=record.part_features,
        compact=True,
    )

    assert len(library.standards) == 5
    assert record.part_features.thread.spec == "M14×2.0"
    assert "local_visual_read_from_png" in record.part_features.notes
    assert "D_socket_outer" in prompt_xml


def test_compact_prompt_marks_manual_textbook_gt() -> None:
    library = load_library()
    prompt_xml = format_for_prompt(
        library,
        part_features={
            "description": "不锈钢厨卫螺母，球面头部，内孔",
            "overall_length": 18.2,
            "shank": {"diameter": 6.2},
            "notes": ["302HQ", "空心螺母", "SR6.8"],
        },
        compact=True,
        max_textbook_cases=10,
    )

    assert "stainless_kitchen_sanitary_nut_8_26" in prompt_xml
    assert "manual_visual_reviewed" in prompt_xml
    assert "SR6.8" in prompt_xml


def test_neighbor_density_excludes_holdout_case_from_confidence_signal() -> None:
    library = load_library()
    holdout = "DJGS-25-8-B001-0358-四方T帽-106S-过模图"
    record = next(r for r in library.cases if r.case_id == holdout)

    signal = compute_neighbor_density(
        library,
        record.part_features,
        exclude_case_ids=[holdout],
    )

    serialized = str(signal)
    assert holdout not in serialized
