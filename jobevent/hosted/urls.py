from django.urls import path

from . import views

urlpatterns = [
    path(name, views.mobile_asset, {"name": name}) for name in views.MOBILE_ASSETS
] + [
    path("", views.home),
    path("healthz", views.health),
    path("app", views.studio),
    path("style.css", views.asset, {"name": "style.css"}),
    path("app.js", views.asset, {"name": "app.js"}),
    path("signin", views.account_form, {"signup": False}),
    path("signup", views.account_form, {"signup": True}),
    path("logout", views.signout),
    path("account/delete", views.delete_account),
    path("api/<str:operation>", views.api),
]
