from django.db import models
from django.contrib.auth.models import Group, User, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q


class Role(models.Model):
    """Custom roles for the HR system"""
    ROLE_TYPES = [
        ('SYS_ADMIN', 'System Administrator'),
        ('DG', 'Director General'),
        ('DIRECTOR', 'Director'),
        ('ZONAL_DIRECTOR', 'Zonal Director'),
        ('HOD', 'Head of Department'),
        ('UNIT_HEAD', 'Unit Head'),
        ('STATE_COORDINATOR', 'State Coordinator'),
        ('HR_ADMIN', 'HR Administrator'),
        ('HR_OFFICER', 'HR Officer'),
        ('EMPLOYEE', 'Regular Employee'),
    ]
    
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    role_type = models.CharField(max_length=20, choices=ROLE_TYPES)
    
    # Map to Django's built-in Group model
    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='hr_role')
    
    # Hierarchy level (higher number means higher authority)
    hierarchy_level = models.PositiveIntegerField(default=0)
    
    # Permissions specific to the HR system
    can_manage_users = models.BooleanField(default=False)
    can_manage_departments = models.BooleanField(default=False)
    can_manage_roles = models.BooleanField(default=False)
    
    # HR Module permissions
    can_manage_trainings = models.BooleanField(default=False)
    can_approve_trainings = models.BooleanField(default=False)
    can_manage_leaves = models.BooleanField(default=False)
    can_approve_leaves = models.BooleanField(default=False)
    can_manage_examinations = models.BooleanField(default=False)
    can_manage_promotions = models.BooleanField(default=False)
    can_approve_promotions = models.BooleanField(default=False)
    can_manage_transfers = models.BooleanField(default=False)
    can_approve_transfers = models.BooleanField(default=False)
    can_manage_educational_upgrades = models.BooleanField(default=False)
    can_approve_educational_upgrades = models.BooleanField(default=False)
    can_manage_retirements = models.BooleanField(default=False)
    
    # Task management permissions
    can_create_tasks = models.BooleanField(default=False)
    can_assign_tasks = models.BooleanField(default=False)
    can_view_all_tasks = models.BooleanField(default=False)
    can_manage_workflows = models.BooleanField(default=False)
    
    # File management permissions
    can_manage_files = models.BooleanField(default=False)
    can_view_all_files = models.BooleanField(default=False)
    can_manage_file_permissions = models.BooleanField(default=False)
    
    # Report permissions
    can_view_reports = models.BooleanField(default=False)
    can_create_reports = models.BooleanField(default=False)
    can_export_data = models.BooleanField(default=False)
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        """Ensure corresponding Django Group exists and has the right permissions"""
        # Create Group if it doesn't exist
        if not self.group_id:
            self.group, created = Group.objects.get_or_create(name=self.name)
        
        # Map boolean permission fields to Django permissions
        permission_mapping = {
            'can_manage_users': ['add_user', 'change_user', 'view_user', 'delete_user'],
            'can_manage_departments': ['add_department', 'change_department', 'view_department', 'delete_department'],
            # ... add more mappings for other boolean fields
        }
        
        # Clear existing permissions
        self.group.permissions.clear()
        
        # Add permissions based on boolean fields
        for field_name, permission_codenames in permission_mapping.items():
            if getattr(self, field_name):
                for codename in permission_codenames:
                    try:
                        app_label, model = codename.split('_', 1)[1], codename.split('_')[0]
                        ct = ContentType.objects.get(app_label=app_label, model=model)
                        perm = Permission.objects.get(content_type=ct, codename=codename)
                        self.group.permissions.add(perm)
                    except (Permission.DoesNotExist, ContentType.DoesNotExist):
                        continue
        
        super().save(*args, **kwargs)


class UserRole(models.Model):
    """Mapping between users and roles"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='user_roles')
    
    # Scope of the role (e.g., department, unit, zone, state)
    scope_type = models.CharField(max_length=50, blank=True, null=True)
    scope_id = models.PositiveIntegerField(blank=True, null=True)
    
    # For time-limited roles
    is_primary = models.BooleanField(default=False)
    start_date = models.DateField(auto_now_add=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assigned_roles')
    assigned_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        scope_info = f" ({self.scope_type}: {self.scope_id})" if self.scope_type else ""
        return f"{self.user.username} - {self.role.name}{scope_info}"
    
    def save(self, *args, **kwargs):
        """Ensure user is added to the corresponding Django Group"""
        super().save(*args, **kwargs)
        if self.is_active:
            self.user.groups.add(self.role.group)
        else:
            # Check if user has any other active roles with this group
            if not UserRole.objects.filter(
                user=self.user,
                role__group=self.role.group,
                is_active=True
            ).exclude(id=self.id).exists():
                self.user.groups.remove(self.role.group)
    
    class Meta:
        unique_together = ('user', 'role', 'scope_type', 'scope_id')


class AttributeBasedPermission(models.Model):
    """
    Fine-grained permissions based on attributes
    Example: HR officers can only view employee profiles in their department
    """
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='attribute_permissions')
    
    # The model and field this permission applies to
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    model_name = models.CharField(max_length=100)  # Redundant with content_type, but for easier queries
    field_name = models.CharField(max_length=100)
    
    # The condition type
    CONDITION_TYPES = [
        ('EQUALS', 'Equals'),
        ('NOT_EQUALS', 'Not Equals'),
        ('IN', 'In List'),
        ('NOT_IN', 'Not In List'),
        ('GREATER_THAN', 'Greater Than'),
        ('LESS_THAN', 'Less Than'),
        ('CONTAINS', 'Contains'),
        ('STARTS_WITH', 'Starts With'),
        ('ENDS_WITH', 'Ends With'),
    ]
    condition_type = models.CharField(max_length=15, choices=CONDITION_TYPES)
    
    # The condition value (can be static or dynamic)
    # For dynamic values, use placeholders like {user.department_id}
    condition_value = models.TextField() 
    
    # The permission action
    PERMISSION_ACTIONS = [
        ('VIEW', 'Can View'),
        ('CHANGE', 'Can Change'),
        ('ADD', 'Can Add'),
        ('DELETE', 'Can Delete'),
    ]
    permission_action = models.CharField(max_length=10, choices=PERMISSION_ACTIONS)
    
    def __str__(self):
        return f"{self.role.name} - {self.model_name}.{self.field_name} - {self.permission_action}"
    
    def get_q_object(self, user):
        """
        Convert this permission to a Django Q object for filtering
        Handles dynamic values by replacing placeholders with actual user attributes
        """
        value = self.condition_value
        
        # Handle dynamic values
        if '{' in value and '}' in value:
            # Extract the placeholder
            placeholder = value[value.find('{')+1:value.find('}')]
            
            # Get the actual value from the user object
            parts = placeholder.split('.')
            obj = user
            for part in parts:
                if hasattr(obj, part):
                    obj = getattr(obj, part)
                else:
                    # If attribute doesn't exist, return an impossible condition
                    return Q(pk=-1)
            
            value = obj
        
        # Build the appropriate Q object based on condition type
        if self.condition_type == 'EQUALS':
            return Q(**{self.field_name: value})
        elif self.condition_type == 'NOT_EQUALS':
            return ~Q(**{self.field_name: value})
        elif self.condition_type == 'IN':
            # Assume value is a comma-separated list
            values = [v.strip() for v in value.split(',')]
            return Q(**{f"{self.field_name}__in": values})
        elif self.condition_type == 'NOT_IN':
            values = [v.strip() for v in value.split(',')]
            return ~Q(**{f"{self.field_name}__in": values})
        elif self.condition_type == 'GREATER_THAN':
            return Q(**{f"{self.field_name}__gt": value})
        elif self.condition_type == 'LESS_THAN':
            return Q(**{f"{self.field_name}__lt": value})
        elif self.condition_type == 'CONTAINS':
            return Q(**{f"{self.field_name}__contains": value})
        elif self.condition_type == 'STARTS_WITH':
            return Q(**{f"{self.field_name}__startswith": value})
        elif self.condition_type == 'ENDS_WITH':
            return Q(**{f"{self.field_name}__endswith": value})
        
        # Default fallback - impossible condition
        return Q(pk=-1)


# Helper functions for permission checking
def get_user_permissions(user):
    """Get all permissions for a user, including role-based and attribute-based"""
    user_roles = UserRole.objects.filter(user=user, is_active=True)
    permissions = {}
    
    for user_role in user_roles:
        role = user_role.role
        
        # Add boolean permission fields
        for field in role._meta.fields:
            if isinstance(field, models.BooleanField) and field.name.startswith('can_'):
                if getattr(role, field.name):
                    permissions[field.name] = True
        
        # Add scope information if available
        if user_role.scope_type and user_role.scope_id:
            scope_key = f"{role.name}_{user_role.scope_type}_scope"
            if scope_key not in permissions:
                permissions[scope_key] = []
            permissions[scope_key].append(user_role.scope_id)
    
    return permissions


def can_access_object(user, obj, action='VIEW'):
    """
    Check if a user can access a specific object based on ABAC rules
    
    Parameters:
    - user: The user trying to access the object
    - obj: The object to check access for
    - action: The action being performed (VIEW, CHANGE, ADD, DELETE)
    
    Returns:
    - True if the user can access the object, False otherwise
    """
    # Get all active roles for the user
    user_roles = UserRole.objects.filter(user=user, is_active=True)
    role_ids = user_roles.values_list('role_id', flat=True)
    
    # Get the model name
    model_name = obj.__class__.__name__.lower()
    content_type = ContentType.objects.get_for_model(obj.__class__)
    
    # Check attribute-based permissions
    attribute_permissions = AttributeBasedPermission.objects.filter(
        role_id__in=role_ids,
        content_type=content_type,
        permission_action=action
    )
    
    # If no specific permissions exist, check if user has a role with blanket permission
    if not attribute_permissions.exists():
        # Check for blanket permissions like can_manage_users, can_view_all_files, etc.
        blanket_perm_name = f"can_{'manage' if action in ('CHANGE', 'ADD', 'DELETE') else 'view_all'}_{model_name}s"
        
        for role_id in role_ids:
            try:
                role = Role.objects.get(id=role_id)
                if hasattr(role, blanket_perm_name) and getattr(role, blanket_perm_name):
                    return True
            except (Role.DoesNotExist, AttributeError):
                continue
        
        # If we're here, there are no blanket permissions either
        # Default to False for most objects
        return False
    
    # Check each permission rule
    for permission in attribute_permissions:
        # Convert permission to Q object and check if the object matches
        q_obj = permission.get_q_object(user)
        
        # Get model class and check if object matches the condition
        model_class = obj.__class__
        query = model_class.objects.filter(q_obj, pk=obj.pk)
        
        if query.exists():
            return True
    
    return False


def filter_queryset_by_permissions(user, queryset, action='VIEW'):
    """
    Filter a queryset based on user's ABAC permissions
    
    Parameters:
    - user: The user requesting the objects
    - queryset: The initial queryset to filter
    - action: The action being performed (VIEW, CHANGE, ADD, DELETE)
    
    Returns:
    - Filtered queryset with only objects the user can access
    """
    # Get all active roles for the user
    user_roles = UserRole.objects.filter(user=user, is_active=True)
    role_ids = user_roles.values_list('role_id', flat=True)
    
    # Get the model name
    model = queryset.model
    model_name = model.__name__.lower()
    content_type = ContentType.objects.get_for_model(model)
    
    # Check if user has blanket permission
    blanket_perm_name = f"can_{'manage' if action in ('CHANGE', 'ADD', 'DELETE') else 'view_all'}_{model_name}s"
    
    for role_id in role_ids:
        try:
            role = Role.objects.get(id=role_id)
            if hasattr(role, blanket_perm_name) and getattr(role, blanket_perm_name):
                return queryset  # User can access all objects
        except (Role.DoesNotExist, AttributeError):
            continue
    
    # Get attribute-based permissions
    attribute_permissions = AttributeBasedPermission.objects.filter(
        role_id__in=role_ids,
        content_type=content_type,
        permission_action=action
    )
    
    # If no permissions, return empty queryset
    if not attribute_permissions.exists():
        return queryset.none()
    
    # Combine all permission Q objects with OR
    combined_q = Q(pk=-1)  # Start with an impossible condition
    
    for permission in attribute_permissions:
        combined_q |= permission.get_q_object(user)
    
    # Apply the combined filter
    return queryset.filter(combined_q)