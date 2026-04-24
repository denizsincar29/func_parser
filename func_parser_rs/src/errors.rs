//! Error types for func_parser_rs.

use thiserror::Error;

/// All errors produced by func_parser_rs.
#[derive(Debug, Error)]
pub enum FuncParserError {
    #[error("Parse error: {0}")]
    ParseError(String),

    #[error("Command not found: {0:?}")]
    CommandNotFound(String),

    #[error("Missing required argument {arg:?} for command {cmd:?}")]
    MissingArg { arg: String, cmd: String },

    #[error("Invalid argument {arg:?}: {reason}")]
    InvalidArg { arg: String, reason: String },

    #[error("Validation failed for {arg:?}: {message}")]
    ValidationError { arg: String, message: String },

    #[error("Permission denied: {permission:?} for user {user:?}")]
    PermissionDenied { permission: String, user: String },

    #[error("Rate limit exceeded for command: {0:?}")]
    RateLimit(String),

    #[error("Scheduler error: {0}")]
    SchedulerError(String),

    #[error("I/O error: {0}")]
    IoError(#[from] std::io::Error),

    #[error("Other error: {0}")]
    Other(String),
}

pub type Result<T> = std::result::Result<T, FuncParserError>;
