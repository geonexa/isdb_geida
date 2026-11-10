from django.urls import path

from . import views

urlpatterns = [
    path("csrf/", views.csrf),
    path("me/", views.me),
    path("sign-in/", views.sign_in),
    path("sign-out/", views.sign_out),
    path("register/", views.register),
    path("verify/", views.verify),
    path("verify/resend/", views.verify_resend),
    path("password-reset/", views.password_reset),
    path("password-reset/<str:uidb64>/<str:token>/", views.password_reset_confirm),
]
