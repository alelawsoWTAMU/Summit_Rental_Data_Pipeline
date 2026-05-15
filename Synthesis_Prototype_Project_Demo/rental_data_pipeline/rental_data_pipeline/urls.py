"""
URL configuration for rental_data_pipeline project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView
from rentals.views import (
    analytics_dashboard,
    analytics_export_report,
    analytics_rows,
    portal_login,
    portal_logout,
    verify_otp,
    vendor_dashboard,
    vendor_edit_row,
    vendor_declare_no_change,
    vendor_no_change_ajax,
    vendor_validate_staging,
    vendor_change_check,
    vendor_csv_upload,
    vendor_inline_save,
    vendor_delete_row,
    vendor_add_row,
    weekly_review,
    publish_week,
    reviewer_change_check,
    reviewer_inline_save,
    reviewer_delete_row,
    reviewer_handle_delinquent,
    reviewer_validate_staging,
)

urlpatterns = [
    path('', RedirectView.as_view(url='/login/', permanent=False)),
    path('login/', portal_login, name='portal_login'),
    path('login/verify/', verify_otp, name='verify_otp'),
    path('admin/', admin.site.urls),
    path('logout/', portal_logout, name='portal_logout'),
    path('analytics/', analytics_dashboard, name='analytics_dashboard'),
    path('analytics/rows/', analytics_rows, name='analytics_rows'),
    path('analytics/export-report/', analytics_export_report, name='analytics_export_report'),
    path('vendor/', vendor_dashboard, name='vendor_dashboard'),
    path('vendor/edit/<int:pk>/', vendor_edit_row, name='vendor_edit_row'),
    path('vendor/no-change/', vendor_declare_no_change, name='vendor_declare_no_change'),
    path('vendor/no-change-ajax/', vendor_no_change_ajax, name='vendor_no_change_ajax'),
    path('vendor/validate/', vendor_validate_staging, name='vendor_validate_staging'),
    path('vendor/change-check/', vendor_change_check, name='vendor_change_check'),
    path('vendor/csv-upload/', vendor_csv_upload, name='vendor_csv_upload'),
    path('vendor/inline-save/<int:pk>/', vendor_inline_save, name='vendor_inline_save'),
    path('vendor/delete/<int:pk>/', vendor_delete_row, name='vendor_delete_row'),
    path('vendor/add-row/', vendor_add_row, name='vendor_add_row'),
    path('review/', weekly_review, name='weekly_review'),
    path('review/publish/', publish_week, name='publish_week'),
    path('review/change-check/', reviewer_change_check, name='reviewer_change_check'),
    path('review/validate/', reviewer_validate_staging, name='reviewer_validate_staging'),
    path('review/handle-delinquent/', reviewer_handle_delinquent, name='reviewer_handle_delinquent'),
    path('review/inline-save/<int:pk>/', reviewer_inline_save, name='reviewer_inline_save'),
    path('review/delete/<int:pk>/', reviewer_delete_row, name='reviewer_delete_row'),
]
