from app.deid.rules import (
    HIGH_SEVERITY_TAGS,
    MEDIUM_SEVERITY_TAGS,
    Severity,
    TagName,
    load_rules,
    severity_for,
    tag_name_for,
)


def test_load_rules_returns_two_lists():
    rules = load_rules()
    assert "version" in rules
    assert len(rules["high_severity_tags"]) == 10
    assert len(rules["medium_severity_tags"]) == 15


def test_high_severity_tags_contains_patient_name():
    assert "0010,0010" in HIGH_SEVERITY_TAGS
    assert HIGH_SEVERITY_TAGS["0010,0010"] == "PatientName"


def test_medium_severity_tags_contains_institution_name():
    assert "0008,0080" in MEDIUM_SEVERITY_TAGS
    assert MEDIUM_SEVERITY_TAGS["0008,0080"] == "InstitutionName"


def test_severity_for_high_tag():
    assert severity_for("0010,0010") == "high"


def test_severity_for_medium_tag():
    assert severity_for("0008,0080") == "medium"


def test_severity_for_unknown_tag_returns_none():
    assert severity_for("ffff,ffff") is None


def test_tag_name_for_known_tag():
    assert tag_name_for("0010,0010") == "PatientName"


def test_tag_name_for_unknown_tag_returns_none():
    assert tag_name_for("ffff,ffff") is None


def test_severity_type_alias_is_str():
    s: Severity = "high"
    assert s == "high"
    t: TagName = "PatientName"
    assert t == "PatientName"
