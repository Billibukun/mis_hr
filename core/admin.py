from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.utils.crypto import get_random_string
from django.core.mail import send_mail
from django.conf import settings
from django.db import IntegrityError, transaction
from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import ForeignKeyWidget, DateWidget, CharWidget, BooleanWidget
from import_export.results import RowResult  # Import RowResult
from .models import Department, Newsletter, Unit, Zone, State, LGA, Bank, PFA, Designation, EmployeeProfile, EmployeeDetail


import logging

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

# Create a handler for writing log messages to the console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)  # Set the handler's logging level

# Create a formatter and add it to the handler
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(console_handler)

# --- Helper Functions (could be in core/utils.py) ---
def generate_temp_password():
    return get_random_string(12)

def send_password_email(user, password):
    subject = "Your Account Credentials"
    message = f"""
    Your account has been created.
    Username: {user.username}
    Temporary Password: {password}
    Please login and complete your profile.
    """
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
    except Exception as e:
        logger.error(f"Failed to send email to {user.email}: {e}")

# --- Resource Definitions for django-import-export ---
class UserResource(resources.ModelResource):
    password = fields.Field(widget=CharWidget())
    is_active = fields.Field(attribute='is_active', widget=BooleanWidget())
    is_staff = fields.Field(attribute='is_staff', widget=BooleanWidget())
    is_superuser = fields.Field(attribute='is_superuser', widget=BooleanWidget())

    class Meta:
        model = User
        fields = ('id', 'username', 'password', 'first_name', 'last_name', 'email', 'is_active', 'is_staff', 'is_superuser', 'last_login', 'date_joined')
        import_id_fields = ['username']
        skip_unchanged = True
        report_skipped = True
        export_order = ('id', 'username', 'first_name', 'last_name', 'email', 'is_active', 'is_staff', 'is_superuser', 'last_login', 'date_joined')

    def before_import_row(self, row, **kwargs):
        """Handles password, username, and existing user checks."""
        password = row.get('password')
        if not password:
            password = generate_temp_password()
        row['password'] = password  # Keep for emailing.

        username = row.get('username')
        if not username:
            row['username'] = "user_" + get_random_string(6)

        # Check for existing user
        try:
            existing_user = User.objects.get(username=row['username'])
            row['id'] = existing_user.id  # For updates
        except User.DoesNotExist:
            pass

    def import_row(self, row, instance_loader, **kwargs):
        """Hashes the password before saving the row."""
        # Call the parent class's import_row *first* to get the result
        import_result = super().import_row(row, instance_loader, **kwargs)

        # *Now* hash the password and save the user
        password = row.get('password')
        if password:
            user = User.objects.get(username=row.get('username')) # Fetch the user object
            user.set_password(password)  # Hash the password
            user.save() # save the changes

        return import_result


    def after_import_row(self, row, row_result, **kwargs):
        """Sends email and creates/updates EmployeeProfile."""
        username = row.get('username')
        password = row.get('password')  # Retrieve the *plain text* password
        file_number = row.get('file_number')

        if row_result.import_type in (RowResult.IMPORT_TYPE_NEW, RowResult.IMPORT_TYPE_UPDATE):
            try:
                user = User.objects.get(username=username)
                if row_result.import_type == RowResult.IMPORT_TYPE_NEW:
                    if user and password:
                        send_password_email(user, password)  # Send the *plain text* password

                if file_number:
                    try:
                        with transaction.atomic():
                            profile, created = EmployeeProfile.objects.get_or_create(
                                user=user, defaults={'file_number': file_number}
                            )
                            if not created:
                                profile.file_number = file_number
                                profile.save()
                    except IntegrityError:
                        logger.error(f"IntegrityError: Duplicate file_number {file_number} for user {username}.")
                        row_result.errors.append(
                            RowResult.Error(
                                "IntegrityError",
                                f"Duplicate file_number {file_number} for user {username}."
                            )
                        )
            except User.DoesNotExist:
                logger.error(f"User {username} not found after import.")
                return

# --- Inline Admin Models ---
class EmployeeProfileInline(admin.StackedInline):
    model = EmployeeProfile
    can_delete = False
    verbose_name_plural = 'Employee Profile'
    fk_name = 'user'

class EmployeeDetailInline(admin.StackedInline):
    model = EmployeeDetail
    can_delete = False
    verbose_name_plural = 'Employee Details'
    fk_name = 'employee_profile'

# --- Custom User Admin ---
class UserAdmin(ImportExportModelAdmin, BaseUserAdmin):
    resource_class = UserResource
    inlines = (EmployeeProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'get_file_number')
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    actions = ['mark_needs_correction', 'activate_users']

    def get_file_number(self, obj):
        if hasattr(obj, 'employee_profile'):
            return obj.employee_profile.file_number
        return None
    get_file_number.short_description = 'File Number'
    get_file_number.admin_order_field = 'employee_profile__file_number'

    def get_inline_instances(self, request, obj=None):
        if not obj:
            return list()
        return super().get_inline_instances(request, obj)

    def mark_needs_correction(self, request, queryset):
        for user in queryset:
            messages.warning(request, f"User {user.username} needs profile correction.")
    mark_needs_correction.short_description = "Mark selected users as needing correction"

    def activate_users(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, "Selected users have been activated.")
    activate_users.short_description = "Activate selected users"

# --- Resource Definitions for django-import-export ---
class EmployeeProfileResource(resources.ModelResource):
    # Use ForeignKeyWidget for related fields.
    current_department = fields.Field(column_name='department_code', attribute='current_department', widget=ForeignKeyWidget(Department, 'code'))
    current_unit = fields.Field(column_name='unit_name', attribute='current_unit', widget=ForeignKeyWidget(Unit, 'name'))
    current_zone = fields.Field(column_name='zone_code', attribute='current_zone', widget=ForeignKeyWidget(Zone, 'code'))
    current_state = fields.Field(column_name='state_code', attribute='current_state', widget=ForeignKeyWidget(State, 'code'))
    current_designation = fields.Field(column_name='designation_code', attribute='current_designation', widget=ForeignKeyWidget(Designation, 'code'))
    lga_of_origin = fields.Field(column_name='lga_origin_code', attribute='lga_of_origin', widget=ForeignKeyWidget(LGA, 'code'))
    state_of_origin = fields.Field(column_name='state_origin_code', attribute='state_of_origin', widget=ForeignKeyWidget(State, 'code'))
    lga_of_residence = fields.Field(column_name='lga_residence_code', attribute='lga_of_residence', widget=ForeignKeyWidget(LGA, 'code'))
    state_of_residence = fields.Field(column_name='state_residence_code', attribute='state_of_residence', widget=ForeignKeyWidget(State, 'code'))
    date_of_birth = fields.Field(column_name='date_of_birth', attribute='date_of_birth', widget=DateWidget('%Y-%m-%d'))
    date_of_appointment = fields.Field(column_name='date_of_appointment', attribute='date_of_appointment', widget=DateWidget('%Y-%m-%d'))
    date_of_assumption = fields.Field(column_name='date_of_assumption', attribute='date_of_assumption', widget=DateWidget('%Y-%m-%d'))
    date_of_documentation = fields.Field(column_name='date_of_documentation', attribute='date_of_documentation', widget=DateWidget('%Y-%m-%d'))
    date_of_confirmation = fields.Field(column_name='date_of_confirmation', attribute='date_of_confirmation', widget=DateWidget('%Y-%m-%d'))
    date_of_retirement = fields.Field(column_name='date_of_retirement', attribute='date_of_retirement', widget=DateWidget('%Y-%m-%d'))
    last_promotion_date = fields.Field(column_name='last_promotion_date', attribute='last_promotion_date', widget=DateWidget('%Y-%m-%d'))
    last_examination_date = fields.Field(column_name='last_examination_date', attribute='last_examination_date', widget=DateWidget('%Y-%m-%d'))

    # Directly map simple fields.
    user = fields.Field(column_name='username', attribute='user', widget=ForeignKeyWidget(User, 'username'))

    class Meta:
        model = EmployeeProfile
        # List *all* fields you want to import/export.
        fields = ('id', 'user', 'file_number', 'ippis_number', 'current_employee_type', 'middle_name', 'sex',
                  'marital_status', 'date_of_birth', 'phone_number', 'contact_address', 'lga_of_residence',
                  'state_of_residence', 'lga_of_origin', 'state_of_origin', 'nin', 'brn', 'date_of_appointment',
                  'date_of_documentation', 'date_of_assumption', 'date_of_confirmation', 'date_of_retirement',
                  'current_department', 'current_unit', 'current_zone', 'current_state', 'current_grade_level',
                  'current_step', 'current_designation', 'current_cadre', 'last_promotion_date',
                  'last_examination_date')
        import_id_fields = ['file_number']
        skip_unchanged = True
        report_skipped = True

class EmployeeDetailResource(resources.ModelResource):
    employee_profile = fields.Field(column_name='file_number', attribute='employee_profile', widget=ForeignKeyWidget(EmployeeProfile, 'file_number'))
    bank = fields.Field(column_name='bank_code', attribute='bank', widget=ForeignKeyWidget(Bank, 'code'))
    pfa = fields.Field(column_name='pfa_code', attribute='pfa', widget=ForeignKeyWidget(PFA, 'code'))

    class Meta:
        model = EmployeeDetail
        fields = ('id', 'employee_profile', 'highest_formal_eduation', 'course_of_study', 'area_of_study',
                  'year_of_graduation', 'bank', 'account_number', 'account_type', 'pfa', 'pfa_number', 'leave_status',
                  'nok1_name', 'nok1_phone_number', 'nok1_email', 'nok1_relationship', 'nok1_address', 'nok2_name',
                  'nok2_phone_number', 'nok2_email', 'nok2_relationship', 'nok2_address')
        import_id_fields = ['employee_profile']
        skip_unchanged = True
        report_skipped = True


class DepartmentResource(resources.ModelResource):
    parent = fields.Field(column_name='parent_code', attribute='parent', widget=ForeignKeyWidget(Department, 'code'))

    class Meta:
        model = Department
        fields = ('id', 'name', 'description', 'code', 'type', 'parent')
        import_id_fields = ['code']
        skip_unchanged = True
        report_skipped = True
        defer_foreign_keys = True

class UnitResource(resources.ModelResource):
    department = fields.Field(column_name='department_code', attribute='department', widget=ForeignKeyWidget(Department, 'code'))
    class Meta:
        model = Unit
        fields = ('id','name', 'code', 'description', 'department')
        import_id_fields = ['name']

class ZoneResource(resources.ModelResource):
    class Meta:
        model = Zone
        fields = ('id', 'code', 'name')
        import_id_fields = ['code']

class StateResource(resources.ModelResource):
    zone = fields.Field(column_name='zone_code', attribute='zone', widget=ForeignKeyWidget(Zone, 'code'))
    class Meta:
        model = State
        fields = ('id','code', 'name', 'zone')
        import_id_fields = ['code']

class LGAResource(resources.ModelResource):
    state = fields.Field(column_name='state_code', attribute='state', widget=ForeignKeyWidget(State, 'code'))
    class Meta:
        model = LGA
        fields = ('id','code', 'name', 'state')
        import_id_fields = ['code']

class BankResource(resources.ModelResource):
    class Meta:
        model = Bank
        fields = ('id','code', 'name')
        import_id_fields = ['code']

class PFAResource(resources.ModelResource):
    class Meta:
        model = PFA
        fields = ('id','code', 'name')
        import_id_fields = ['code']

class DesignationResource(resources.ModelResource):
    department = fields.Field(column_name='department_code', attribute='department', widget=ForeignKeyWidget(Department, 'code'))
    class Meta:
        model = Designation
        fields = ('id','code', 'grade_level', 'name', 'department')
        import_id_fields = ['code']

# --- Regular Admin Models ---

@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(ImportExportModelAdmin):
    resource_class = EmployeeProfileResource
    list_display = ('file_number', 'user', 'current_employee_type', 'current_department', 'get_user_active')
    list_filter = ('current_employee_type', 'current_department', 'current_zone', 'current_state')
    search_fields = ('file_number', 'user__username', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'modified_at', 'created_by', 'modified_by')

    def get_user_active(self, obj):
        return obj.user.is_active
    get_user_active.short_description = 'User Active'
    get_user_active.boolean = True

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.modified_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(EmployeeDetail)
class EmployeeDetailAdmin(ImportExportModelAdmin):
    resource_class = EmployeeDetailResource
    list_display = ('employee_profile', 'highest_formal_eduation', 'bank', 'account_number')
    search_fields = ('employee_profile__file_number', 'employee_profile__user__username')


@admin.register(Department)
class DepartmentAdmin(ImportExportModelAdmin):
    resource_class = DepartmentResource
    list_display = ('name', 'code', 'type')
    search_fields = ('name', 'code')
    list_filter = ('type', 'parent') 

@admin.register(Unit)
class UnitAdmin(ImportExportModelAdmin):
    resource_class = UnitResource
    list_display = ('name', 'code', 'department')
    list_filter = ('department',)
    search_fields = ('name', 'department__name')

@admin.register(Zone)
class ZoneAdmin(ImportExportModelAdmin):
    resource_class = ZoneResource
    list_display = ('name', 'code')
    search_fields = ('name', 'code')

@admin.register(State)
class StateAdmin(ImportExportModelAdmin):
    resource_class = StateResource
    list_display = ('name', 'code', 'zone')
    list_filter = ('zone',)
    search_fields = ('name', 'code')

@admin.register(LGA)
class LGAAdmin(ImportExportModelAdmin):
    resource_class = LGAResource
    list_display = ('code', 'name', 'state')
    list_filter = ('state',)
    search_fields = ('name', 'code')

@admin.register(Bank)
class BankAdmin(ImportExportModelAdmin):
    resource_class = BankResource
    list_display = ('name', 'code')
    search_fields = ('name', 'code')

@admin.register(PFA)
class PFAAdmin(ImportExportModelAdmin):
    resource_class = PFAResource
    list_display = ('name', 'code')
    search_fields = ('name', 'code')

@admin.register(Designation)
class DesignationAdmin(ImportExportModelAdmin):
    resource_class = DesignationResource
    list_display = ('name', 'code', 'grade_level', 'department')
    list_filter = ('department', 'grade_level')
    search_fields = ('name', 'code')

admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(Newsletter)