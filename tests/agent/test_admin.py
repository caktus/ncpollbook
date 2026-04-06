from django.contrib import admin

from apps.agent.models import ModelIdentifier, ToolModel


class TestModelIdentifierAdmin:
    def test_is_registered(self):
        assert admin.site.is_registered(ModelIdentifier)

    def test_list_display(self):
        ma = admin.site._registry[ModelIdentifier]
        assert "name" in ma.list_display

    def test_search_fields(self):
        ma = admin.site._registry[ModelIdentifier]
        assert "name" in ma.search_fields


class TestToolModelAdmin:
    def test_is_registered(self):
        assert admin.site.is_registered(ToolModel)

    def test_list_display(self):
        ma = admin.site._registry[ToolModel]
        assert "tool_name" in ma.list_display
        assert "model" in ma.list_display
