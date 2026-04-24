//! Async execution pipeline for func_parser_rs.

use std::collections::HashMap;
use crate::context::ExecutionContext;
use crate::errors::Result;
use crate::models::{ArgValue, CommandInfo, CommandResult, CommandStatus};

/// Executes command handlers and manages output redirection.
pub struct AsyncPipeline;

impl AsyncPipeline {
    pub fn new() -> Self {
        Self
    }

    pub async fn execute(
        &self,
        cmd_info: &CommandInfo,
        args: HashMap<String, ArgValue>,
        ctx: ExecutionContext,
    ) -> CommandResult {
        if ctx.dry_run {
            return CommandResult {
                name: cmd_info.name.clone(),
                args,
                status: CommandStatus::DryRun,
                output: None,
                error: None,
                redirect: None,
            };
        }

        let handler = match &cmd_info.handler {
            Some(h) => h,
            None => {
                return CommandResult::error(
                    cmd_info.name.clone(),
                    format!("Command {:?} has no handler", cmd_info.name),
                );
            }
        };

        match handler(ctx, args.clone()).await {
            Ok(output) => CommandResult {
                name: cmd_info.name.clone(),
                args,
                status: CommandStatus::Success,
                output: Some(output),
                error: None,
                redirect: None,
            },
            Err(e) => CommandResult {
                name: cmd_info.name.clone(),
                args,
                status: CommandStatus::Error,
                output: None,
                error: Some(e.to_string()),
                redirect: None,
            },
        }
    }

    /// Write result output to a redirect target (file).
    pub async fn redirect_output(&self, result: &CommandResult) -> Result<()> {
        let redirect = match &result.redirect {
            Some(r) => r,
            None => return Ok(()),
        };
        let text = result.output.as_ref().map(|o| o.to_string()).unwrap_or_default();
        if redirect.is_file() {
            if redirect.append {
                use std::io::Write;
                let mut f = std::fs::OpenOptions::new()
                    .append(true)
                    .create(true)
                    .open(&redirect.target)?;
                f.write_all(text.as_bytes())?;
            } else {
                std::fs::write(&redirect.target, &text)?;
            }
        }
        Ok(())
    }
}

impl Default for AsyncPipeline {
    fn default() -> Self {
        Self::new()
    }
}
