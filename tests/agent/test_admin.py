from django.contrib import admin

from apps.agent.models import ModelIdentifier, ToolModel


class TestModelIdentifierAdmin:
    def test_is_registered(self):
        assert admin.site.is_registered(ModelIdentifier)

    def test_list_display(self):
        ma = admin.site._registry[ModelIdentifier]
        for field in (
            "name",
            "deployment_type",
            "provider_org",
            "engine",
            "display_scale",
            "precision",
            "display_size_on_disk",
        ):
            assert field in ma.list_display

    def test_search_fields(self):
        ma = admin.site._registry[ModelIdentifier]
        assert "name" in ma.search_fields

    def test_display_scale_formats_as_billions(self):
        ma = admin.site._registry[ModelIdentifier]
        obj = ModelIdentifier(scale=30)
        assert ma.display_scale(obj) == "30B"

    def test_display_scale_none_returns_empty(self):
        ma = admin.site._registry[ModelIdentifier]
        obj = ModelIdentifier(scale=None)
        assert ma.display_scale(obj) == ""

    def test_display_size_on_disk_shows_integer_gb(self):
        ma = admin.site._registry[ModelIdentifier]
        obj = ModelIdentifier(size_on_disk=30.2)
        assert ma.display_size_on_disk(obj) == "30 GB"

    def test_display_size_on_disk_none_returns_empty(self):
        ma = admin.site._registry[ModelIdentifier]
        obj = ModelIdentifier(size_on_disk=None)
        assert ma.display_size_on_disk(obj) == ""


class TestToolModelAdmin:
    def test_is_registered(self):
        assert admin.site.is_registered(ToolModel)

    def test_list_display(self):
        ma = admin.site._registry[ToolModel]
        assert "tool_name" in ma.list_display
        assert "model" in ma.list_display

    def test_list_editable(self):
        ma = admin.site._registry[ToolModel]
        assert "model" in ma.list_editable
