import pytest
from django.core.management import call_command

from apps.agent.models import AgentTool, DeploymentType, ModelIdentifier, ToolModel


class TestModelIdentifierFields:
    @pytest.mark.django_db
    def test_default_deployment_type(self):
        m = ModelIdentifier.objects.create(name="openai:gpt-4o")
        assert m.deployment_type == DeploymentType.CLOUD_API

    @pytest.mark.django_db
    def test_optional_fields_default_to_blank(self):
        m = ModelIdentifier.objects.create(name="openai:gpt-4o")
        assert m.provider_org == ""
        assert m.engine == ""
        assert m.scale is None
        assert m.precision == ""
        assert m.size_on_disk is None
        assert m.model_uri == ""

    @pytest.mark.django_db
    def test_full_fields(self):
        m = ModelIdentifier.objects.create(
            name="lmstudio:Qwen3-Coder-30B",
            deployment_type=DeploymentType.SELF_HOSTED,
            provider_org="Qwen",
            engine="LM Studio",
            scale=30,
            precision="4bit",
            size_on_disk=18.5,
        )
        assert m.deployment_type == DeploymentType.SELF_HOSTED
        assert m.provider_org == "Qwen"
        assert m.engine == "LM Studio"
        assert m.scale == 30
        assert m.precision == "4bit"
        assert m.size_on_disk == 18.5


class TestAgentModelsFixture:
    @pytest.mark.django_db
    def test_fixture_loads_successfully(self):
        call_command("loaddata", "agent_models", verbosity=0)
        assert ModelIdentifier.objects.count() == 5
        assert ToolModel.objects.count() == 3

    @pytest.mark.django_db
    def test_fixture_tool_models_reference_correct_models(self):
        call_command("loaddata", "agent_models", verbosity=0)
        sql_gen = ToolModel.objects.get(tool_name=AgentTool.SQL_GEN)
        assert "claude-haiku" in sql_gen.model.name
        voter = ToolModel.objects.get(tool_name=AgentTool.VOTER_AGENT)
        assert "gpt-oss" in voter.model.name
