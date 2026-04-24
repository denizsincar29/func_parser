//! Command registry for func_parser_rs.

use std::collections::HashMap;
use crate::models::CommandInfo;

/// Registry that maps command names and aliases to `CommandInfo`.
#[derive(Default)]
pub struct CommandRegistry {
    commands: HashMap<String, CommandInfo>,
    aliases: HashMap<String, String>,
    default_handler: Option<crate::models::AsyncHandler>,
}

impl CommandRegistry {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn register(&mut self, info: CommandInfo) {
        for alias in &info.aliases {
            self.aliases.insert(alias.clone(), info.name.clone());
        }
        self.commands.insert(info.name.clone(), info);
    }

    pub fn get(&self, name: &str) -> Option<&CommandInfo> {
        if let Some(info) = self.commands.get(name) {
            return Some(info);
        }
        if let Some(canonical) = self.aliases.get(name) {
            return self.commands.get(canonical);
        }
        None
    }

    pub fn all_commands(&self) -> Vec<&CommandInfo> {
        self.commands.values().collect()
    }

    pub fn set_default(&mut self, handler: crate::models::AsyncHandler) {
        self.default_handler = Some(handler);
    }

    pub fn default_handler(&self) -> Option<&crate::models::AsyncHandler> {
        self.default_handler.as_ref()
    }

    pub fn contains(&self, name: &str) -> bool {
        self.commands.contains_key(name) || self.aliases.contains_key(name)
    }

    /// Returns all command names in the namespace `ns` (prefix `ns.`).
    pub fn namespace(&self, ns: &str) -> Vec<&CommandInfo> {
        let prefix = format!("{}.", ns);
        self.commands.values().filter(|c| c.name.starts_with(&prefix)).collect()
    }
}

impl std::fmt::Debug for CommandRegistry {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("CommandRegistry")
            .field("commands", &self.commands.keys().collect::<Vec<_>>())
            .finish()
    }
}
