from django.db import models


class DeploymentType(models.TextChoices):
    CLOUD_API = "cloud-api", "Cloud API (e.g. OpenAI direct)"
    CLOUD_MANAGED = "cloud-managed", "Cloud Managed (e.g. AWS Bedrock)"
    SELF_HOSTED = "self-hosted", "Self-Hosted"


class ModelIdentifier(models.Model):
    """Stores an LLM model identifier string, e.g. 'bedrock:us.anthropic.claude-sonnet-4-6'."""

    name = models.CharField(max_length=255, unique=True)
    deployment_type = models.CharField(
        max_length=20,
        choices=DeploymentType,
        default=DeploymentType.CLOUD_API,
    )
    provider_org = models.CharField(max_length=100, blank=True)
    engine = models.CharField(max_length=100, blank=True, help_text="e.g. Ollama, LM Studio")
    scale = models.CharField(max_length=20, blank=True, help_text="e.g. 7B, 30B, 70B")
    precision = models.CharField(max_length=20, blank=True, help_text="e.g. 4bit, fp16")

    def __str__(self) -> str:
        return self.name


class AgentTool(models.TextChoices):
    SQL_GEN = "sql_gen", "SQL Generation (internal)"
    VOTER_AGENT = "voter_agent", "Voter Agent (web/CLI)"


class ToolModel(models.Model):
    """Maps an agent tool to a specific LLM model.

    tool_name=NULL acts as the default model for any tool not explicitly configured.
    """

    tool_name = models.CharField(
        max_length=50,
        choices=AgentTool,
        null=True,
        blank=True,
        unique=True,
        help_text="Tool this model applies to; NULL = default for all other tools",
    )
    model = models.ForeignKey(ModelIdentifier, on_delete=models.PROTECT)

    def __str__(self) -> str:
        return f"{self.tool_name or 'default'} → {self.model.name}"
