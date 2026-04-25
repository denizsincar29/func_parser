//! Middleware chain for func_parser_rs.

use std::collections::HashMap;
use std::time::Instant;
use crate::errors::{FuncParserError, Result};

/// Tracks call timestamps for sliding-window rate limiting.
struct RateLimitEntry {
    max_calls: usize,
    window_secs: f64,
    timestamps: Vec<Instant>,
}

/// Manages per-command rate limiting.
#[derive(Default)]
pub struct MiddlewareChain {
    rate_limits: HashMap<String, RateLimitEntry>,
}

impl MiddlewareChain {
    pub fn new() -> Self {
        Self::default()
    }

    /// Configure a sliding-window rate limit for `cmd_name`.
    pub fn set_rate_limit(&mut self, cmd_name: impl Into<String>, max_calls: usize, window_secs: f64) {
        self.rate_limits.insert(cmd_name.into(), RateLimitEntry {
            max_calls,
            window_secs,
            timestamps: Vec::new(),
        });
    }

    /// Returns `Err(RateLimit)` if the rate limit for `cmd_name` is exceeded.
    pub fn check_rate_limit(&mut self, cmd_name: &str) -> Result<()> {
        if let Some(entry) = self.rate_limits.get_mut(cmd_name) {
            let now = Instant::now();
            entry.timestamps.retain(|t| now.duration_since(*t).as_secs_f64() < entry.window_secs);
            if entry.timestamps.len() >= entry.max_calls {
                return Err(FuncParserError::RateLimit(cmd_name.to_string()));
            }
            entry.timestamps.push(now);
        }
        Ok(())
    }
}

impl std::fmt::Debug for MiddlewareChain {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("MiddlewareChain")
            .field("rate_limits", &self.rate_limits.keys().collect::<Vec<_>>())
            .finish()
    }
}
