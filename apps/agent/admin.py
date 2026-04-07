from django.contrib import admin

from apps.agent.models import ModelIdentifier, ToolModel


@admin.register(ModelIdentifier)
class ModelIdentifierAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "deployment_type",
        "provider_org",
        "engine",
        "display_scale",
        "precision",
        "display_size_on_disk",
    )
    list_filter = ("deployment_type", "provider_org", "engine")
    search_fields = ("name", "provider_org", "engine")
    ordering = ("name",)

    @admin.display(description="Scale", ordering="scale")
    def display_scale(self, obj: ModelIdentifier) -> str:
        return f"{obj.scale}B" if obj.scale is not None else ""

    @admin.display(description="Size on disk", ordering="size_on_disk")
    def display_size_on_disk(self, obj: ModelIdentifier) -> str:
        return f"{int(obj.size_on_disk)} GB" if obj.size_on_disk is not None else ""


@admin.register(ToolModel)
class ToolModelAdmin(admin.ModelAdmin):
    list_display = ("tool_name", "model")
    list_editable = ("model",)
    list_filter = ("model",)
    list_select_related = ("model",)
    search_fields = ("tool_name", "model__name")
