from __future__ import annotations

from types import SimpleNamespace

from scripts import prompt_versions


class FakePromptStore:
    """Mô phỏng quy tắc của Langfuse: mỗi label chỉ nằm trên một version."""

    def __init__(self) -> None:
        self.versions: list[dict] = []

    def create_prompt(self, *, name: str, prompt: str, labels: list[str], **_: object) -> None:
        self._take(labels)
        self.versions.append({"version": len(self.versions) + 1, "prompt": prompt, "labels": set(labels)})

    def update_prompt(self, *, name: str, version: int, new_labels: list[str]) -> None:
        self._take(new_labels)
        self.versions[version - 1]["labels"] |= set(new_labels)

    def get_prompt(self, name: str, *, label: str, **_: object):
        for item in self.versions:
            if label in item["labels"]:
                return SimpleNamespace(version=item["version"], is_fallback=False)
        raise LookupError(label)

    def _take(self, labels: list[str]) -> None:
        for item in self.versions:
            item["labels"] -= set(labels)


def test_bootstrap_creates_v1_and_v2_with_lab_labels_once() -> None:
    store = FakePromptStore()

    prompt_versions.bootstrap(store, "day13-chat")
    second_run = prompt_versions.bootstrap(store, "day13-chat")

    assert prompt_versions.label_versions(store, "day13-chat") == {
        "baseline": 1, "candidate": 2, "production": 1,
    }
    assert len(store.versions) == 2
    assert all(var in store.versions[1]["prompt"] for var in ("{{feature}}", "{{docs}}", "{{message}}"))
    assert "nothing to create" in second_run[0]


def test_promote_then_rollback_moves_only_production_label() -> None:
    store = FakePromptStore()
    prompt_versions.bootstrap(store, "day13-chat")

    prompt_versions.promote(store, "day13-chat", 2)
    assert prompt_versions.label_versions(store, "day13-chat") == {
        "baseline": 1, "candidate": 2, "production": 2,
    }

    prompt_versions.promote(store, "day13-chat", 1)
    assert prompt_versions.label_versions(store, "day13-chat") == {
        "baseline": 1, "candidate": 2, "production": 1,
    }
