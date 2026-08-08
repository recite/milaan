"""A backend command may name a location the case cannot know."""

import os

from milaan.runner import expand


class TestExpand:
    def test_a_variable_is_resolved(self, monkeypatch):
        monkeypatch.setenv("KASAUTI_RLIBS", "/var/lib/kasauti")
        assert expand("${KASAUTI_RLIBS}/sandwich_2.4-0") == (
            "/var/lib/kasauti/sandwich_2.4-0"
        )

    def test_an_undefined_variable_is_left_alone(self, monkeypatch):
        # Blanking it would leave "/sandwich_2.4-0", an absolute path that could
        # plausibly exist. Leaving it written means the failure names its cause.
        monkeypatch.delenv("KASAUTI_RLIBS", raising=False)
        assert expand("${KASAUTI_RLIBS}/sandwich_2.4-0") == (
            "${KASAUTI_RLIBS}/sandwich_2.4-0"
        )

    def test_a_leading_tilde_is_resolved(self):
        assert expand("~/rlibs").startswith(os.path.expanduser("~"))

    def test_an_ordinary_argument_is_untouched(self):
        assert expand("--vanilla") == "--vanilla"
        assert expand("run_r.R") == "run_r.R"
