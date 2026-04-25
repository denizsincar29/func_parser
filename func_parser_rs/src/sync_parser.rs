//! Synchronous wrapper around [`Parser`] for use outside of async runtimes.
//!
//! # Example
//!
//! ```rust,no_run
//! use func_parser_rs::sync_parser::SyncParser;
//! use func_parser_rs::context::ExecutionContext;
//!
//! let mut sp = SyncParser::default();
//! // register commands …
//! let result = sp.execute("/greet Alice", ExecutionContext::new());
//! println!("{:?}", result.output);
//! ```

use std::sync::Arc;

use tokio::runtime::{Builder as RuntimeBuilder, Runtime};

use crate::context::ExecutionContext;
use crate::middleware::MiddlewareChain;
use crate::models::{AsyncHandler, CommandInfo, CommandResult};
use crate::parser::Parser;
use crate::permissions::PermissionChecker;
use crate::pipeline::AsyncPipeline;
use crate::registry::CommandRegistry;
use crate::variables::VariableStore;

/// A synchronous facade over [`Parser`].
///
/// Holds a single-threaded Tokio runtime so that callers never need to
/// `block_on` / `tokio::runtime::Handle` themselves.
pub struct SyncParser {
    parser: Parser,
    runtime: Runtime,
}

impl SyncParser {
    /// Build a `SyncParser` with a freshly created single-threaded runtime.
    pub fn new(
        registry: Arc<std::sync::RwLock<CommandRegistry>>,
        vars: VariableStore,
        permissions: PermissionChecker,
        middleware: MiddlewareChain,
        pipeline: AsyncPipeline,
    ) -> Self {
        let runtime = RuntimeBuilder::new_current_thread()
            .enable_all()
            .build()
            .expect("failed to create Tokio runtime");
        Self {
            parser: Parser::new(registry, vars, permissions, middleware, pipeline),
            runtime,
        }
    }

    // -----------------------------------------------------------------------
    // Sync execution
    // -----------------------------------------------------------------------

    /// Execute `input` synchronously, blocking until the result is ready.
    pub fn execute(&mut self, input: &str, ctx: ExecutionContext) -> CommandResult {
        self.runtime.block_on(self.parser.execute(input, ctx))
    }

    /// Execute a script file synchronously.
    pub fn execute_script(&mut self, path: &str, ctx: ExecutionContext) -> Vec<CommandResult> {
        let content = match std::fs::read_to_string(path) {
            Ok(c) => c,
            Err(e) => return vec![CommandResult::error("execute", e.to_string())],
        };
        content
            .lines()
            .filter(|l| !l.trim().is_empty() && !l.trim().starts_with('#'))
            .map(|line| self.execute(line.trim(), ctx.clone()))
            .collect()
    }

    /// Simple interactive REPL that reads from `stdin`.
    ///
    /// Prints each result's output to `stdout`.  Ends on EOF or `Ctrl-C`.
    pub fn repl(&mut self, prompt: &str, ctx: ExecutionContext) {
        use std::io::{self, BufRead, Write};
        let stdin = io::stdin();
        loop {
            print!("{}", prompt);
            io::stdout().flush().ok();
            let mut line = String::new();
            match stdin.lock().read_line(&mut line) {
                Ok(0) => break, // EOF
                Ok(_) => {
                    let trimmed = line.trim();
                    if trimmed.is_empty() {
                        continue;
                    }
                    let result = self.execute(trimmed, ctx.clone());
                    if let Some(output) = &result.output {
                        println!("{}", output);
                    }
                    if let Some(err) = &result.error {
                        eprintln!("Error: {}", err);
                    }
                }
                Err(e) => {
                    eprintln!("Read error: {}", e);
                    break;
                }
            }
        }
    }

    // -----------------------------------------------------------------------
    // Async access (escape hatch)
    // -----------------------------------------------------------------------

    /// Run an arbitrary future on the internal runtime.
    pub fn block_on<F, T>(&self, fut: F) -> T
    where
        F: std::future::Future<Output = T>,
    {
        self.runtime.block_on(fut)
    }

    /// Borrow the underlying async [`Parser`].
    pub fn parser(&mut self) -> &mut Parser {
        &mut self.parser
    }

    // -----------------------------------------------------------------------
    // Registry helpers (mirrors CommandParser builder API)
    // -----------------------------------------------------------------------

    /// Register a command directly.
    pub fn register(&mut self, info: CommandInfo) {
        self.parser
            .registry
            .write()
            .unwrap()
            .register(info);
    }

    /// Set the default text handler.
    pub fn set_default(&mut self, handler: AsyncHandler) {
        self.parser
            .registry
            .write()
            .unwrap()
            .set_default(handler);
    }

    /// Generate a simple help string from the registry.
    pub fn help(&self) -> String {
        let registry = self.parser.registry.read().unwrap();
        let mut lines = vec!["Available commands:".to_string()];
        let mut cmds: Vec<_> = registry.all_commands().into_iter().collect();
        cmds.sort_by_key(|c| c.name.as_str());
        for cmd in cmds {
            if !cmd.hidden {
                lines.push(format!("  /{:<20} {}", cmd.name, cmd.help));
            }
        }
        lines.join("\n")
    }
}

impl Default for SyncParser {
    fn default() -> Self {
        Self::new(
            Arc::new(std::sync::RwLock::new(CommandRegistry::new())),
            VariableStore::new(),
            PermissionChecker::new(),
            MiddlewareChain::new(),
            AsyncPipeline::new(),
        )
    }
}
