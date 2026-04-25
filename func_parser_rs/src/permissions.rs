//! Permission checker for func_parser_rs.

use std::collections::{HashMap, HashSet};
use crate::errors::{FuncParserError, Result};

/// Checks user permissions for commands.
#[derive(Debug, Clone)]
pub struct PermissionChecker {
    role_permissions: HashMap<String, HashSet<String>>,
    user_permissions: HashMap<String, HashSet<String>>,
}

impl PermissionChecker {
    pub fn new() -> Self {
        let mut role_permissions = HashMap::new();
        role_permissions.insert("admin".to_string(), {
            let mut s = HashSet::new();
            s.insert("*".to_string());
            s
        });
        role_permissions.insert("user".to_string(), HashSet::new());
        role_permissions.insert("moderator".to_string(), {
            let mut s = HashSet::new();
            s.insert("moderate".to_string());
            s
        });
        Self {
            role_permissions,
            user_permissions: HashMap::new(),
        }
    }

    pub fn add_role(&mut self, role: impl Into<String>, permissions: Vec<String>) {
        self.role_permissions
            .entry(role.into())
            .or_default()
            .extend(permissions);
    }

    pub fn grant(&mut self, user_id: impl Into<String>, permission: impl Into<String>) {
        self.user_permissions
            .entry(user_id.into())
            .or_default()
            .insert(permission.into());
    }

    pub fn revoke(&mut self, user_id: &str, permission: &str) {
        if let Some(perms) = self.user_permissions.get_mut(user_id) {
            perms.remove(permission);
        }
    }

    pub fn check(&self, user_roles: &[String], required: &[String], user_id: &str) -> bool {
        if required.is_empty() {
            return true;
        }
        // Admin shortcut
        for role in user_roles {
            if let Some(perms) = self.role_permissions.get(role) {
                if perms.contains("*") {
                    return true;
                }
            }
        }
        // Collect all permissions for user
        let mut user_perms: HashSet<&str> = HashSet::new();
        for role in user_roles {
            if let Some(perms) = self.role_permissions.get(role) {
                user_perms.extend(perms.iter().map(|s| s.as_str()));
            }
        }
        if let Some(extra) = self.user_permissions.get(user_id) {
            user_perms.extend(extra.iter().map(|s| s.as_str()));
        }
        required.iter().all(|p| user_perms.contains(p.as_str()))
    }

    pub fn require(&self, user_roles: &[String], required: &[String], user_id: &str) -> Result<()> {
        for perm in required {
            if !self.check(user_roles, &[perm.clone()], user_id) {
                return Err(FuncParserError::PermissionDenied {
                    permission: perm.clone(),
                    user: user_id.to_string(),
                });
            }
        }
        Ok(())
    }
}

impl Default for PermissionChecker {
    fn default() -> Self {
        Self::new()
    }
}
