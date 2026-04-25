//! # func_parser_rs
//!
//! A modular, extensible command/function parser — Rust implementation.
//!
//! Mirrors the Python `func_parser` package with the same core concepts:
//! - Command registry with aliases and namespaces
//! - Argument definitions (typed, required/optional, variadic, ranges, regex)
//! - Async execution pipeline
//! - Middleware (before/after hooks)
//! - Permission system
//! - Variable store with `${var}` / `$VAR` expansion
//! - Tokenizer + AST
//! - Output redirection
//! - Scheduler (`every Xm`, `at HH:MM`)

pub mod ast;
pub mod context;
pub mod errors;
pub mod middleware;
pub mod models;
pub mod parser;
pub mod permissions;
pub mod pipeline;
pub mod registry;
pub mod scheduler;
pub mod sync_parser;
pub mod tokenizer;
pub mod validation;
pub mod variables;

pub use context::ExecutionContext;
pub use errors::FuncParserError;
pub use models::{ArgDef, CommandInfo, CommandResult, OutputRedirect};
pub use parser::Parser;
pub use permissions::PermissionChecker;
pub use pipeline::AsyncPipeline;
pub use registry::CommandRegistry;
pub use scheduler::Scheduler;
pub use sync_parser::SyncParser;
pub use tokenizer::Tokenizer;
pub use variables::VariableStore;
