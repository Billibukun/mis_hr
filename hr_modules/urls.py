from django.urls import path
from . views import *
from .views_educational import *
from .views_examination import *
from .views_leave import *
from .views_training import *
from .views_promotion import *
from .views_transfer import *
from .views_retirement import *


app_name = 'hr_modules'

urlpatterns = [
    # Training Management
    path('training/', training_list, name='training_list'),
    path('training/<int:pk>/', training_detail, name='training_detail'),
    path('training/create/', training_create, name='training_create'),
    path('training/<int:pk>/update/', training_update, name='training_update'),
    path('training/<int:pk>/delete/', training_delete, name='training_delete'),
    path('training/<int:pk>/nominate/', training_nominate, name='training_nominate'),
    path('training/<int:pk>/register/', training_register, name='training_register'),
    path('training/<int:pk>/cancel-registration/', training_cancel_registration, name='training_cancel_registration'),
    path('training/<int:pk>/update-status/<int:participant_id>/', training_update_status, name='training_update_status'),
    path('training/<int:pk>/export-participants/', training_export_participants, name='training_export_participants'),
    
    # Leave Management
    path('leave/', leave_list, name='leave_list'),
    path('leave/<int:pk>/', leave_detail, name='leave_detail'),
    path('leave/create/', leave_create, name='leave_create'),
    path('leave/<int:pk>/cancel/', leave_cancel, name='leave_cancel'),
    path('leave/<int:pk>/approve/', leave_approve, name='leave_approve'),
    path('leave/<int:pk>/reject/', leave_reject, name='leave_reject'),
    path('leave/balance-admin/', leave_balance_admin, name='leave_balance_admin'),
    path('leave/balance-update/<int:employee_id>/', leave_balance_update, name='leave_balance_update'),
    path('leave/export/', leave_export, name='leave_export'),
    path('leave/summary-report/', leave_summary_report, name='leave_summary_report'),
    
    # Examination Management
    path('examination/', examination_list, name='examination_list'),
    path('examination/<int:pk>/', examination_detail, name='examination_detail'),
    path('examination/create/', examination_create, name='examination_create'),
    path('examination/<int:pk>/update/', examination_update, name='examination_update'),
    path('examination/<int:pk>/delete/', examination_delete, name='examination_delete'),
    path('examination/<int:pk>/register/', examination_register, name='examination_register'),
    path('examination/<int:pk>/cancel-registration/', examination_cancel_registration, name='examination_cancel_registration'),
    path('examination/<int:pk>/update-participants/', examination_update_participants, name='examination_update_participants'),
    path('examination/<int:pk>/export-results/', examination_export_results, name='examination_export_results'),
    path('examination/types/', examination_type_list, name='examination_type_list'),
    path('examination/types/create/', examination_type_create, name='examination_type_create'),
    path('examination/types/<int:pk>/update/', examination_type_update, name='examination_type_update'),
    path('examination/types/<int:pk>/delete/', examination_type_delete, name='examination_type_delete'),
    path('examination/summary-report/', examination_summary_report, name='examination_summary_report'),
    
    # Promotion Management
    path('promotion/', promotion_list, name='promotion_list'),
    path('promotion/cycle/<int:pk>/', promotion_cycle_detail, name='promotion_cycle_detail'),
    path('promotion/cycle/create/', promotion_cycle_create, name='promotion_cycle_create'),
    path('promotion/cycle/<int:pk>/update/', promotion_cycle_update, name='promotion_cycle_update'),
    path('promotion/cycle/<int:cycle_pk>/criteria/', promotion_criteria_manage, name='promotion_criteria_manage'),
    path('promotion/cycle/<int:cycle_pk>/nominate/', promotion_nominate, name='promotion_nominate'),
    path('promotion/nomination/<int:pk>/', promotion_nomination_detail, name='promotion_nomination_detail'),
    path('promotion/nomination/<int:nomination_pk>/assess/', promotion_assessment, name='promotion_assessment'),
    path('promotion/nomination/<int:nomination_pk>/approve/', promotion_approve, name='promotion_approve'),
    path('promotion/nomination/<int:nomination_pk>/reject/', promotion_reject, name='promotion_reject'),
    path('promotion/export/<int:cycle_pk>/', promotion_export, name='promotion_export'),
    path('promotion/summary-report/', promotion_summary_report, name='promotion_summary_report'),
    
    # Transfer Management
    path('transfer/', transfer_list, name='transfer_list'),
    path('transfer/<int:pk>/', transfer_detail, name='transfer_detail'),
    path('transfer/create/', transfer_create, name='transfer_create'),
    path('transfer/<int:pk>/edit/', transfer_edit, name='transfer_edit'),
    path('transfer/<int:pk>/submit/', transfer_submit, name='transfer_submit'),
    path('transfer/<int:pk>/cancel/', transfer_cancel, name='transfer_cancel'),
    path('transfer/<int:pk>/review/', transfer_review, name='transfer_review'),
    path('transfer/<int:pk>/approve/', transfer_approve, name='transfer_approve'),
    path('transfer/<int:pk>/reject/', transfer_reject, name='transfer_reject'),
    path('transfer/<int:pk>/complete/', transfer_complete, name='transfer_complete'),
    path('transfer/export/', transfer_export, name='transfer_export'),
    path('transfer/summary-report/', transfer_summary_report, name='transfer_summary_report'),
    path('transfer/get-units/', get_units_for_department, name='get_units_for_department'),
    
    # Educational Upgrade Management
    path('educational/', educational_upgrade_list, name='educational_upgrade_list'),
    path('educational/<int:pk>/', educational_upgrade_detail, name='educational_upgrade_detail'),
    path('educational/create/', educational_upgrade_create, name='educational_upgrade_create'),
    path('educational/<int:pk>/review/', educational_upgrade_review, name='educational_upgrade_review'),
    path('educational/<int:pk>/approve/', educational_upgrade_approve, name='educational_upgrade_approve'),
    path('educational/<int:pk>/complete/', educational_upgrade_complete, name='educational_upgrade_complete'),
    path('educational/export/', educational_upgrade_export, name='educational_upgrade_export'),
    path('educational/summary-report/', educational_upgrade_summary_report, name='educational_upgrade_summary_report'),
    
    # Retirement Management
    path('retirement/', retirement_list, name='retirement_list'),
    path('retirement/<int:pk>/', retirement_detail, name='retirement_detail'),
    path('retirement/create/', retirement_create, name='retirement_create'),
    path('retirement/<int:pk>/update/', retirement_update, name='retirement_update'),
    path('retirement/<int:plan_pk>/checklist/', retirement_checklist_manage, name='retirement_checklist_manage'),
    path('retirement/checklist-item/<int:item_pk>/delete/', retirement_checklist_item_delete, name='retirement_checklist_item_delete'),
    path('retirement/<int:pk>/exit-interview/', retirement_exit_interview, name='retirement_exit_interview'),
    path('retirement/export/', retirement_export, name='retirement_export'),
    path('retirement/forecast/', retirement_forecast, name='retirement_forecast'),
    path('retirement/identify-upcoming/', identify_upcoming_retirements, name='identify_upcoming_retirements'),
]