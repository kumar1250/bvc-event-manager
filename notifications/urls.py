from django.urls import path
from . import views

urlpatterns = [
    path("", views.NotificationListView.as_view()),
    path("<int:pk>/read/", views.MarkNotificationReadView.as_view()),
    path("read-all/", views.MarkAllNotificationsReadView.as_view()),
]
