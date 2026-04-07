from click.testing import CliRunner
from django.core.management import get_commands, load_command_class


def _invoke(args: list[str]) -> str:
    """Run the agent management command and return stdout."""
    cmd = load_command_class("apps.agent", "agent")
    runner = CliRunner()
    result = runner.invoke(cmd, args)
    assert result.exit_code == 0, result.output
    return result.output


class TestAgentPromptsCommand:
    def test_command_is_registered(self):
        assert "agent" in get_commands()

    def test_all_prompts_includes_both_sections(self):
        output = _invoke(["prompts"])
        assert "sql_gen_agent system prompt" in output
        assert "voter_agent instructions" in output

    def test_sql_gen_prompt_contains_schema_keywords(self):
        output = _invoke(["prompts", "--name", "sql_gen"])
        assert "SELECT" in output
        assert "ncid" in output
        assert "voter_agent" not in output

    def test_voter_prompt_contains_instructions(self):
        output = _invoke(["prompts", "--name", "voter"])
        assert "voter data analyst" in output
        assert "sql_gen_agent" not in output


class TestAgentCliCommand:
    def test_cli_help(self):
        output = _invoke(["cli", "--help"])
        assert "question" in output
