//! Variable store for func_parser_rs.

use std::collections::HashMap;
use regex::Regex;

/// Scoped variable store supporting `//set`, `${var}`, `$VAR` expansion.
#[derive(Debug, Clone, Default)]
pub struct VariableStore {
    local: HashMap<String, String>,
    env: HashMap<String, String>,
}

impl VariableStore {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn set(&mut self, name: impl Into<String>, value: impl Into<String>) {
        self.local.insert(name.into(), value.into());
    }

    pub fn set_env(&mut self, name: impl Into<String>, value: impl Into<String>) {
        let k = name.into();
        let v = value.into();
        std::env::set_var(&k, &v);
        self.env.insert(k, v);
    }

    pub fn get(&self, name: &str) -> Option<&String> {
        self.local.get(name)
            .or_else(|| self.env.get(name))
            .or_else(|| {
                // can't return reference to temp; handled below
                None
            })
    }

    pub fn get_owned(&self, name: &str) -> Option<String> {
        if let Some(v) = self.local.get(name) {
            return Some(v.clone());
        }
        if let Some(v) = self.env.get(name) {
            return Some(v.clone());
        }
        std::env::var(name).ok()
    }

    /// Expand `${var}` and `$VAR` placeholders in `text`.
    pub fn expand(&self, text: &str) -> String {
        // ${var}
        let re_braces = Regex::new(r"\$\{([^}]+)\}").unwrap();
        let expanded = re_braces.replace_all(text, |caps: &regex::Captures| {
            let key = &caps[1];
            self.get_owned(key).unwrap_or_else(|| caps[0].to_string())
        });

        // $VAR (uppercase / mixed)
        let re_bare = Regex::new(r"\$([A-Za-z_][A-Za-z0-9_]*)").unwrap();
        re_bare.replace_all(&expanded, |caps: &regex::Captures| {
            let key = &caps[1];
            self.get_owned(key).unwrap_or_else(|| caps[0].to_string())
        }).to_string()
    }

    pub fn all_vars(&self) -> HashMap<String, String> {
        let mut result = self.env.clone();
        result.extend(self.local.clone());
        result
    }
}
