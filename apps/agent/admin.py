from django.contrib import admin

from apps.agent.models import ModelIdentifier, ToolModel


@admin.register(ModelIdentifier)
class ModelIdentifierAdmin(admin.ModelAdmin):
    list_display = ("name", "deployment_type", "provider_org", "engine", "scale", "precision")
    list_filter = ("deployment_type", "provider_org", "engine")
    search_fields = ("name", "provider_org", "engine")


@admin.register(ToolModel)
class ToolModelAdmin(admin.ModelAdmin):
    list_display = ("tool_name", "model")
    list_select_related = ("model",)
