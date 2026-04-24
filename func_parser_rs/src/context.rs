//! Execution context for func_parser_rs.

use std::collections::HashMap;

/// Represents the entity executing commands.
#[derive(Debug, Clone)]
pub struct User {
    pub id: String,
    pub name: String,
    pub roles: Vec<String>,
}

impl User {
    pub fn new(id: impl Into<String>, name: impl Into<String>) -> Self {
        Self {
            id: id.into(),
            name: name.into(),
            roles: vec!["user".to_string()],
        }
    }

    pub fn with_role(mut self, role: impl Into<String>) -> Self {
        self.roles.push(role.into());
        self
    }

    pub fn has_role(&self, role: &str) -> bool {
        self.roles.contains(&role.to_string()) || self.roles.contains(&"admin".to_string())
    }
}

impl Default for User {
    fn default() -> Self {
        Self::new("anonymous", "anonymous")
    }
}

/// Context passed to every command handler.
#[derive(Debug, Clone)]
pub struct ExecutionContext {
    pub user: User,
    pub vars: HashMap<String, String>,
    pub env: HashMap<String, String>,
    pub dry_run: bool,
    pub debug: bool,
}

impl ExecutionContext {
    pub fn new() -> Self {
        let env: HashMap<String, String> = std::env::vars().collect();
        Self {
            user: User::default(),
            vars: HashMap::new(),
            env,
            dry_run: false,
            debug: false,
        }
    }

    pub fn with_user(mut self, user: User) -> Self {
        self.user = user;
        self
    }

    pub fn with_dry_run(mut self, dry_run: bool) -> Self {
        self.dry_run = dry_run;
        self
    }

    pub fn set_var(&mut self, name: impl Into<String>, value: impl Into<String>) {
        self.vars.insert(name.into(), value.into());
    }

    pub fn get_var(&self, name: &str) -> Option<&String> {
        self.vars.get(name).or_else(|| self.env.get(name))
    }
}

impl Default for ExecutionContext {
    fn default() -> Self {
        Self::new()
    }
}
