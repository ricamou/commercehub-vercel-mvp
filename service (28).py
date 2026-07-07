ROLES = {
    "owner": ["*"],
    "admin": ["dashboard:read", "products:write", "orders:write", "finance:read", "marketplaces:write"],
    "operator": ["dashboard:read", "products:write", "orders:write"],
    "viewer": ["dashboard:read", "products:read", "orders:read", "finance:read"],
}

USERS = [
    {"id": "owner", "name": "Ricardo Moura", "email": "owner@commercehub.local", "role": "owner", "status": "active"}
]

def users():
    return USERS

def roles():
    return ROLES
