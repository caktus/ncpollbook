from click.testing import CliRunner

from apps.agent.cli import _fmt_elapsed, main


class TestFmtElapsed:
    def test_sub_second(self):
        assert _fmt_elapsed(0.5) == "0.50s"

    def test_whole_seconds(self):
        assert _fmt_elapsed(10.0) == "10.00s"

    def test_zero(self):
        assert _fmt_elapsed(0.0) == "0.00s"


class TestCliMain:
    def test_help(self):
        result = CliRunner().invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "question" in result.output.lower()

    def test_unknown_option_fails(self):
        result = CliRunner().invoke(main, ["--not-a-flag"])
        assert result.exit_code != 0
