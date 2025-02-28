from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from import_export.fields import Field
from import_export.widgets import ForeignKeyWidget, DateWidget

from .models import (
    # Training Models
    TrainingType, Training, TrainingParticipant,
    
    # Leave Models
    LeaveType, LeaveBalance, LeaveRequest, LeaveApprovalLevel,
    
    # Examination Models
    ExaminationType, Examination, ExaminationParticipant,
    
    # Promotion Models
    PromotionCycle, PromotionCriteria, PromotionNomination, PromotionAssessment,
    
    # Transfer Models
    TransferRequest,
    
    # Educational Upgrade Models
    EducationalUpgrade,
    
    # Retirement Models
    RetirementPlan, RetirementChecklistItem
)

from core.models import EmployeeProfile, Department
from django.contrib.auth.models import User


# Resource classes for import/export
class TrainingResource(resources.ModelResource):
    training_type = Field(column_name='training_type', attribute='training_type',
                         widget=ForeignKeyWidget(TrainingType, 'name'))
    created_by = Field(column_name='created_by', attribute='created_by',
                      widget=ForeignKeyWidget(User, 'username'))
    
    class Meta:
        model = Training
        fields = ('id', 'title', 'description', 'training_type', 'start_date', 'end_date',
                 'location', 'capacity', 'organizer', 'status', 'created_by')
        import_id_fields = ['id']


class TrainingParticipantResource(resources.ModelResource):
    training = Field(column_name='training', attribute='training',
                    widget=ForeignKeyWidget(Training, 'title'))
    employee = Field(column_name='employee', attribute='employee',
                    widget=ForeignKeyWidget(EmployeeProfile, 'file_number'))
    
    class Meta:
        model = TrainingParticipant
        fields = ('id', 'training', 'employee', 'status', 'attendance_record',
                 'performance_score', 'certificate_issued', 'comments')
        import_id_fields = ['id']


class LeaveRequestResource(resources.ModelResource):
    employee = Field(column_name='employee', attribute='employee',
                    widget=ForeignKeyWidget(EmployeeProfile, 'file_number'))
    leave_type = Field(column_name='leave_type', attribute='leave_type',
                      widget=ForeignKeyWidget(LeaveType, 'name'))
    
    class Meta:
        model = LeaveRequest
        fields = ('id', 'employee', 'leave_type', 'start_date', 'end_date',
                 'days_requested', 'status', 'reason')
        import_id_fields = ['id']


class ExaminationResource(resources.ModelResource):
    examination_type = Field(column_name='examination_type', attribute='examination_type',
                           widget=ForeignKeyWidget(ExaminationType, 'name'))
    
    class Meta:
        model = Examination
        fields = ('id', 'title', 'examination_type', 'scheduled_date',
                 'registration_deadline', 'venue', 'max_participants', 'status')
        import_id_fields = ['id']


class PromotionCycleResource(resources.ModelResource):
    class Meta:
        model = PromotionCycle
        fields = ('id', 'title', 'year', 'start_date', 'end_date', 'status')
        import_id_fields = ['id']


class TransferRequestResource(resources.ModelResource):
    employee = Field(column_name='employee', attribute='employee',
                    widget=ForeignKeyWidget(EmployeeProfile, 'file_number'))
    current_department = Field(column_name='current_department', attribute='current_department',
                             widget=ForeignKeyWidget(Department, 'name'))
    requested_department = Field(column_name='requested_department', attribute='requested_department',
                               widget=ForeignKeyWidget(Department, 'name'))
    
    class Meta:
        model = TransferRequest
        fields = ('id', 'employee', 'request_type', 'current_department',
                 'requested_department', 'reason', 'status')
        import_id_fields = ['id']


class EducationalUpgradeResource(resources.ModelResource):
    employee = Field(column_name='employee', attribute='employee',
                    widget=ForeignKeyWidget(EmployeeProfile, 'file_number'))
    
    class Meta:
        model = EducationalUpgrade
        fields = ('id', 'employee', 'qualification_type', 'course_of_study',
                 'institution', 'year_of_graduation', 'status')
        import_id_fields = ['id']


class RetirementPlanResource(resources.ModelResource):
    employee = Field(column_name='employee', attribute='employee',
                    widget=ForeignKeyWidget(EmployeeProfile, 'file_number'))
    
    class Meta:
        model = RetirementPlan
        fields = ('id', 'employee', 'expected_retirement_date', 'status')
        import_id_fields = ['id']


# Admin classes
@admin.register(TrainingType)
class TrainingTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.register(Training)
class TrainingAdmin(ImportExportModelAdmin):
    resource_class = TrainingResource
    list_display = ('title', 'training_type', 'start_date', 'end_date', 'location', 'status')
    list_filter = ('status', 'training_type')
    search_fields = ('title', 'description', 'location')
    date_hierarchy = 'start_date'


@admin.register(TrainingParticipant)
class TrainingParticipantAdmin(ImportExportModelAdmin):
    resource_class = TrainingParticipantResource
    list_display = ('employee', 'training', 'status', 'attendance_record', 'certificate_issued')
    list_filter = ('status', 'certificate_issued', 'training')
    search_fields = ('employee__user__first_name', 'employee__user__last_name', 'employee__file_number', 'training__title')


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'max_days', 'is_paid', 'requires_approval')
    list_filter = ('is_paid', 'requires_approval')
    search_fields = ('name', 'description')


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'leave_type', 'year', 'initial_balance', 'used_days', 'remaining_balance')
    list_filter = ('year', 'leave_type')
    search_fields = ('employee__user__first_name', 'employee__user__last_name', 'employee__file_number')


@admin.register(LeaveRequest)
class LeaveRequestAdmin(ImportExportModelAdmin):
    resource_class = LeaveRequestResource
    list_display = ('employee', 'leave_type', 'start_date', 'end_date', 'days_requested', 'status')
    list_filter = ('status', 'leave_type')
    search_fields = ('employee__user__first_name', 'employee__user__last_name', 'employee__file_number', 'reason')
    date_hierarchy = 'start_date'


@admin.register(LeaveApprovalLevel)
class LeaveApprovalLevelAdmin(admin.ModelAdmin):
    list_display = ('department', 'leave_type', 'level')
    list_filter = ('level', 'department', 'leave_type')


@admin.register(ExaminationType)
class ExaminationTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name', 'description')


@admin.register(Examination)
class ExaminationAdmin(ImportExportModelAdmin):
    resource_class = ExaminationResource
    list_display = ('title', 'examination_type', 'scheduled_date', 'venue', 'status')
    list_filter = ('status', 'examination_type')
    search_fields = ('title', 'venue')
    date_hierarchy = 'scheduled_date'


@admin.register(ExaminationParticipant)
class ExaminationParticipantAdmin(admin.ModelAdmin):
    list_display = ('employee', 'examination', 'status', 'score', 'position')
    list_filter = ('status', 'examination')
    search_fields = ('employee__user__first_name', 'employee__user__last_name', 'employee__file_number', 'examination__title')


@admin.register(PromotionCycle)
class PromotionCycleAdmin(ImportExportModelAdmin):
    resource_class = PromotionCycleResource
    list_display = ('title', 'year', 'start_date', 'end_date', 'status')
    list_filter = ('status', 'year')
    search_fields = ('title',)
    date_hierarchy = 'start_date'


@admin.register(PromotionCriteria)
class PromotionCriteriaAdmin(admin.ModelAdmin):
    list_display = ('promotion_cycle', 'name', 'weight')
    list_filter = ('promotion_cycle',)
    search_fields = ('name', 'description')


class PromotionAssessmentInline(admin.TabularInline):
    model = PromotionAssessment
    extra = 0
    fields = ('criteria', 'score', 'comments', 'assessed_by')


@admin.register(PromotionNomination)
class PromotionNominationAdmin(admin.ModelAdmin):
    list_display = ('employee', 'promotion_cycle', 'current_level', 'proposed_level', 'status')
    list_filter = ('status', 'promotion_cycle', 'current_level', 'proposed_level')
    search_fields = ('employee__user__first_name', 'employee__user__last_name', 'employee__file_number')
    inlines = [PromotionAssessmentInline]


@admin.register(TransferRequest)
class TransferRequestAdmin(ImportExportModelAdmin):
    resource_class = TransferRequestResource
    list_display = ('employee', 'request_type', 'current_department', 'requested_department', 'status')
    list_filter = ('status', 'request_type')
    search_fields = ('employee__user__first_name', 'employee__user__last_name', 'employee__file_number', 'reason')
    date_hierarchy = 'request_date'


@admin.register(EducationalUpgrade)
class EducationalUpgradeAdmin(ImportExportModelAdmin):
    resource_class = EducationalUpgradeResource
    list_display = ('employee', 'qualification_type', 'course_of_study', 'institution', 'year_of_graduation', 'status')
    list_filter = ('status', 'qualification_type', 'year_of_graduation')
    search_fields = ('employee__user__first_name', 'employee__user__last_name', 'employee__file_number', 'course_of_study', 'institution')


class RetirementChecklistItemInline(admin.TabularInline):
    model = RetirementChecklistItem
    extra = 1
    fields = ('item_name', 'is_completed', 'completed_date', 'completed_by', 'comments')


@admin.register(RetirementPlan)
class RetirementPlanAdmin(ImportExportModelAdmin):
    resource_class = RetirementPlanResource
    list_display = ('employee', 'expected_retirement_date', 'status', 'notification_date', 'clearance_completed', 'pension_processed')
    list_filter = ('status', 'clearance_completed', 'pension_processed')
    search_fields = ('employee__user__first_name', 'employee__user__last_name', 'employee__file_number')
    date_hierarchy = 'expected_retirement_date'
    inlines = [RetirementChecklistItemInline]


@admin.register(RetirementChecklistItem)
class RetirementChecklistItemAdmin(admin.ModelAdmin):
    list_display = ('retirement_plan', 'item_name', 'is_completed', 'completed_date', 'completed_by')
    list_filter = ('is_completed',)
    search_fields = ('retirement_plan__employee__user__first_name', 'retirement_plan__employee__user__last_name', 'item_name')