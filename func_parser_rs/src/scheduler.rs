//! Task scheduler for func_parser_rs.

use std::time::Duration;
use crate::errors::{FuncParserError, Result};

/// Parse a schedule spec and return the initial delay in seconds.
///
/// Supported formats:
/// - `every 5m` / `every 30s` / `every 2h`
/// - `at 12:00`
pub fn parse_spec(spec: &str) -> Result<f64> {
    let s = spec.trim();

    // every <N><unit>
    if let Some(rest) = s.strip_prefix("every ") {
        let rest = rest.trim();
        // split at the transition from digit to alpha
        let split = rest
            .find(|c: char| c.is_alphabetic())
            .ok_or_else(|| FuncParserError::SchedulerError(format!("cannot parse: {:?}", spec)))?;
        let amount: f64 = rest[..split].trim().parse().map_err(|_| {
            FuncParserError::SchedulerError(format!("invalid number in: {:?}", spec))
        })?;
        let unit = rest[split..].trim().to_lowercase();
        let secs = if unit.starts_with('s') {
            amount
        } else if unit.starts_with('m') {
            amount * 60.0
        } else if unit.starts_with('h') {
            amount * 3_600.0
        } else {
            return Err(FuncParserError::SchedulerError(format!("unknown unit in: {:?}", spec)));
        };
        return Ok(secs);
    }

    // at HH:MM
    if let Some(rest) = s.strip_prefix("at ") {
        let rest = rest.trim();
        let parts: Vec<&str> = rest.split(':').collect();
        if parts.len() != 2 {
            return Err(FuncParserError::SchedulerError(format!("invalid time in: {:?}", spec)));
        }
        let hour: u32 = parts[0].trim().parse().map_err(|_| {
            FuncParserError::SchedulerError(format!("invalid hour in: {:?}", spec))
        })?;
        let minute: u32 = parts[1].trim().parse().map_err(|_| {
            FuncParserError::SchedulerError(format!("invalid minute in: {:?}", spec))
        })?;
        if hour > 23 || minute > 59 {
            return Err(FuncParserError::SchedulerError(format!(
                "time out of range in: {:?} (hour 0-23, minute 0-59)", spec
            )));
        }
        // Calculate seconds until next occurrence using wall-clock
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();
        let secs_today = (now % 86_400) as u32; // approximate UTC seconds of day
        let target_secs = hour * 3_600 + minute * 60;
        let delay = if target_secs > secs_today {
            (target_secs - secs_today) as f64
        } else {
            (86_400 - secs_today + target_secs) as f64
        };
        return Ok(delay);
    }

    Err(FuncParserError::SchedulerError(format!("cannot parse schedule spec: {:?}", spec)))
}

/// A running scheduled task handle.
pub struct ScheduledTask {
    pub spec: String,
    pub command: String,
    pub handle: tokio::task::JoinHandle<()>,
}

impl ScheduledTask {
    pub fn abort(&self) {
        self.handle.abort();
    }
}

/// Simple task scheduler.
pub struct Scheduler {
    tasks: Vec<ScheduledTask>,
}

impl Scheduler {
    pub fn new() -> Self {
        Self { tasks: Vec::new() }
    }

    /// Schedule `command` according to `spec`.
    ///
    /// `execute_fn` is called with the command string at the scheduled time.
    pub fn schedule<F, Fut>(
        &mut self,
        spec: impl Into<String>,
        command: impl Into<String>,
        execute_fn: F,
    ) -> Result<()>
    where
        F: Fn(String) -> Fut + Send + 'static,
        Fut: std::future::Future<Output = ()> + Send,
    {
        let spec_str: String = spec.into();
        let cmd: String = command.into();
        let delay = parse_spec(&spec_str)?;

        let is_repeating = spec_str.trim().starts_with("every ");
        let spec_clone = spec_str.clone();
        let cmd_clone = cmd.clone();

        let handle = tokio::spawn(async move {
            if is_repeating {
                loop {
                    let d = parse_spec(&spec_clone).unwrap_or(60.0);
                    tokio::time::sleep(Duration::from_secs_f64(d)).await;
                    execute_fn(cmd_clone.clone()).await;
                }
            } else {
                tokio::time::sleep(Duration::from_secs_f64(delay)).await;
                execute_fn(cmd_clone).await;
            }
        });

        self.tasks.push(ScheduledTask { spec: spec_str, command: cmd, handle });
        Ok(())
    }

    pub fn cancel_all(&mut self) {
        for task in self.tasks.drain(..) {
            task.abort();
        }
    }
}

impl Default for Scheduler {
    fn default() -> Self {
        Self::new()
    }
}
