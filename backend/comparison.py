import re
import difflib


def normalize_text(text: str) -> str:
    """Normalize extracted PDF text for reliable comparison."""

    text = text.replace("\x00", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def extract_dates(text: str) -> list[str]:
    """Extract dates from document text."""

    return re.findall(
        r"\b\d{1,2}\s+"
        r"(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)"
        r"\s+\d{4}\b",
        text,
        re.IGNORECASE
    )


def compare_versions(original_text: str, modified_text: str) -> dict:
    """
    Compare two document versions and identify meaningful changes.
    """

    original = normalize_text(original_text)
    modified = normalize_text(modified_text)

    changes = []

    # --------------------------------------------------
    # Detect date changes
    # --------------------------------------------------

    original_dates = extract_dates(original)
    modified_dates = extract_dates(modified)

    if original_dates != modified_dates:
        changes.append({
            "type": "date_change",
            "field": "Document / Incident Date",
            "original": original_dates,
            "modified": modified_dates
        })

    # --------------------------------------------------
    # Word-level comparison
    # --------------------------------------------------

    original_words = original.split()
    modified_words = modified.split()

    matcher = difflib.SequenceMatcher(
        None,
        original_words,
        modified_words,
        autojunk=False
    )

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():

        if tag == "equal":
            continue

        original_block = " ".join(
            original_words[i1:i2]
        ).strip()

        modified_block = " ".join(
            modified_words[j1:j2]
        ).strip()

        # Ignore giant blocks caused by PDF formatting differences.
        if (
            len(original_block) > 300
            and len(modified_block) > 300
        ):
            continue

        changes.append({
            "type": tag,
            "original": original_block,
            "modified": modified_block
        })

    # --------------------------------------------------
    # Remove duplicate changes safely
    # --------------------------------------------------

    unique_changes = []
    seen = set()

    for change in changes:

        original_value = str(change.get("original", ""))
        modified_value = str(change.get("modified", ""))

        key = (
            change.get("type", ""),
            change.get("field", ""),
            original_value,
            modified_value
        )

        if key in seen:
            continue

        seen.add(key)
        unique_changes.append(change)

    return {
        "changed": len(unique_changes) > 0,
        "change_count": len(unique_changes),
        "changes": unique_changes
    }