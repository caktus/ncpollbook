from django.urls import path

from apps.agent.views import chat_completions, models_list

app_name = "agent"

urlpatterns = [
    path("chat/completions", chat_completions, name="chat_completions"),
    path("models", models_list, name="models_list"),
]
