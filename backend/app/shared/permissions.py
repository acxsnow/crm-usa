"""Permission catalog and default role -> permission matrix (spec 5.2, 5.3)."""

PERMISSION_CATALOG: list[tuple[str, str]] = [
    ("organization.manage", "Manage organization settings"),
    ("users.manage", "Manage users"),
    ("roles.manage", "Manage roles"),
    ("customers.create", "Create customers"),
    ("customers.read", "Read customers"),
    ("customers.update", "Update customers"),
    ("customers.delete", "Delete customers"),
    ("contacts.manage", "Manage customer contacts"),
    ("leads.manage", "Manage leads"),
    ("opportunities.manage", "Manage opportunities"),
    ("quotes.manage", "Manage quotes"),
    ("activities.manage", "Manage CRM activities"),
    ("projects.create", "Create projects"),
    ("projects.read_all", "Read all projects"),
    ("projects.read_assigned", "Read assigned projects"),
    ("projects.update", "Update projects"),
    ("projects.assign", "Assign users to projects"),
    ("projects.close", "Close projects"),
    ("tasks.manage", "Manage tasks"),
    ("checklists.manage", "Manage checklists"),
    ("checklists.approve", "Approve checklists"),
    ("evidence.create", "Upload evidence"),
    ("evidence.read_all", "Read all evidence"),
    ("evidence.read_assigned", "Read assigned-project evidence"),
    ("evidence.delete", "Delete evidence"),
    ("reports.generate", "Generate reports"),
    ("reports.export", "Export reports"),
    ("invoices.create", "Create invoices"),
    ("invoices.read", "Read invoices"),
    ("invoices.update", "Update invoices"),
    ("invoices.record_payment", "Record invoice payments"),
    ("invoices.export", "Export invoices"),
    ("dashboards.commercial", "View commercial dashboard"),
    ("dashboards.operations", "View operations dashboard"),
    ("dashboards.finance", "View finance dashboard"),
    ("audit.read", "Read audit log"),
    ("settings.manage", "Manage organization settings"),
]

# Default system roles and the permission codes they carry (spec 5.3 matrix, translated to codes).
DEFAULT_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "platform_super_admin": [code for code, _ in PERMISSION_CATALOG],  # implicit superuser; kept explicit for audit
    "organization_admin": [code for code, _ in PERMISSION_CATALOG],
    "commercial_manager": [
        "customers.create", "customers.read", "customers.update",
        "contacts.manage", "leads.manage", "opportunities.manage",
        "quotes.manage", "activities.manage",
        "projects.read_all", "invoices.read",
        "dashboards.commercial",
    ],
    "project_manager": [
        "customers.read", "contacts.manage",
        "opportunities.manage", "quotes.manage",
        "projects.create", "projects.read_all", "projects.update", "projects.assign", "projects.close",
        "tasks.manage", "checklists.manage",
        "evidence.create", "evidence.read_all",
        "reports.generate", "reports.export",
        "invoices.read",
        "dashboards.operations",
    ],
    "supervisor": [
        "customers.read", "projects.read_assigned", "tasks.manage",
        "checklists.manage", "checklists.approve",
        "evidence.create", "evidence.read_assigned",
        "reports.generate",
        "invoices.read",
        "dashboards.operations",
    ],
    "field_technician": [
        "customers.read", "projects.read_assigned", "tasks.manage",
        "evidence.create", "evidence.read_assigned",
    ],
    "finance_user": [
        "customers.read", "invoices.create", "invoices.read", "invoices.update",
        "invoices.record_payment", "invoices.export",
        "dashboards.finance",
    ],
    "read_only": [],  # granted per-resource read permissions individually by an org admin
}

ROLE_LABELS: dict[str, str] = {
    "platform_super_admin": "Platform Super Admin",
    "organization_admin": "Organization Admin",
    "commercial_manager": "Commercial Manager",
    "project_manager": "Project Manager",
    "supervisor": "Supervisor",
    "field_technician": "Field Technician",
    "finance_user": "Finance User",
    "read_only": "Read Only",
}
