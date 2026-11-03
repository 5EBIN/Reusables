"""Permission matrix (team screen). Single source of truth for role capabilities."""
ROLES = ("super_admin", "consultant", "client_admin", "analyst", "viewer", "employee")
CAPABILITIES = {
    "survey.write": ("super_admin", "consultant", "client_admin", "analyst"),
    "results.aggregate": ("super_admin", "consultant", "client_admin", "analyst", "viewer"),
    "results.individual": ("super_admin", "consultant", "client_admin", "analyst"),
    "approvals.decide": ("super_admin", "consultant", "client_admin"),
    "content.approve": ("super_admin", "consultant"),
    "billing.manage": ("super_admin", "client_admin"),
    "security.configure": ("super_admin", "client_admin"),
    "own_results.view": ("employee",),
    "impersonate": ("super_admin",),
}
MATRIX = {cap: {r: (r in roles) for r in ROLES} for cap, roles in CAPABILITIES.items()}


def can(role: str, capability: str) -> bool:
    return role in CAPABILITIES.get(capability, ())
