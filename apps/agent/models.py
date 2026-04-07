from django.db import models


class DeploymentType(models.TextChoices):
    CLOUD_API = "cloud-api", "Cloud API"
    CLOUD_MANAGED = "cloud-managed", "Cloud Managed"
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
    scale = models.SmallIntegerField(
        null=True, blank=True, help_text="Billions of parameters, e.g. 7 for 7B, 30 for 30B"
    )
    precision = models.CharField(max_length=20, blank=True, help_text="e.g. 4bit, fp16")
    size_on_disk = models.FloatField(null=True, blank=True, help_text="Size on disk in GB")
    model_uri = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="Model URI",
        help_text="Reference link for the model, e.g. Hugging Face page or model card URL",
    )

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
