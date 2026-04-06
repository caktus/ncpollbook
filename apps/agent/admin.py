from django.contrib import admin

from apps.agent.models import ModelIdentifier, ToolModel


@admin.register(ModelIdentifier)
class ModelIdentifierAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(ToolModel)
class ToolModelAdmin(admin.ModelAdmin):
    list_display = ("tool_name", "model")
    list_select_related = ("model",)
