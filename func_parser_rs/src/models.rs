//! Data models for func_parser_rs.

use std::collections::HashMap;
use std::sync::Arc;

/// Argument kind.
#[derive(Debug, Clone, PartialEq)]
pub enum ArgKind {
    Positional,
    Keyword,
    Variadic,
}

/// Definition of a single command argument.
#[derive(Debug, Clone)]
pub struct ArgDef {
    pub name: String,
    pub required: bool,
    pub default: Option<String>,
    pub help: String,
    pub variadic: bool,
    pub choices: Option<Vec<String>>,
    pub min: Option<f64>,
    pub max: Option<f64>,
    pub regex: Option<String>,
    pub preset: Option<String>,
    pub secret: bool,
    pub kind: ArgKind,
}

impl ArgDef {
    pub fn new(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            required: true,
            default: None,
            help: String::new(),
            variadic: false,
            choices: None,
            min: None,
            max: None,
            regex: None,
            preset: None,
            secret: false,
            kind: ArgKind::Positional,
        }
    }

    pub fn optional(mut self, default: impl Into<String>) -> Self {
        self.required = false;
        self.default = Some(default.into());
        self
    }

    pub fn variadic(mut self) -> Self {
        self.variadic = true;
        self.kind = ArgKind::Variadic;
        self
    }

    pub fn min(mut self, min: f64) -> Self {
        self.min = Some(min);
        self
    }

    pub fn max(mut self, max: f64) -> Self {
        self.max = Some(max);
        self
    }

    pub fn regex(mut self, pattern: impl Into<String>) -> Self {
        self.regex = Some(pattern.into());
        self
    }

    pub fn preset(mut self, name: impl Into<String>) -> Self {
        self.preset = Some(name.into());
        self
    }

    pub fn choices(mut self, choices: Vec<String>) -> Self {
        self.choices = Some(choices);
        self
    }
}

/// Async handler function type.
pub type AsyncHandler = Arc<
    dyn Fn(
            crate::context::ExecutionContext,
            HashMap<String, ArgValue>,
        ) -> std::pin::Pin<Box<dyn std::future::Future<Output = crate::errors::Result<ArgValue>> + Send>>
        + Send
        + Sync,
>;

/// A typed argument value.
#[derive(Debug, Clone)]
pub enum ArgValue {
    String(String),
    Int(i64),
    Float(f64),
    Bool(bool),
    List(Vec<ArgValue>),
    None,
}

impl ArgValue {
    pub fn as_str(&self) -> Option<&str> {
        match self {
            ArgValue::String(s) => Some(s),
            _ => None,
        }
    }

    pub fn as_int(&self) -> Option<i64> {
        match self {
            ArgValue::Int(n) => Some(*n),
            _ => None,
        }
    }
}

impl std::fmt::Display for ArgValue {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ArgValue::String(s) => write!(f, "{}", s),
            ArgValue::Int(n) => write!(f, "{}", n),
            ArgValue::Float(n) => write!(f, "{}", n),
            ArgValue::Bool(b) => write!(f, "{}", b),
            ArgValue::List(v) => {
                let parts: Vec<String> = v.iter().map(|x| x.to_string()).collect();
                write!(f, "[{}]", parts.join(", "))
            }
            ArgValue::None => write!(f, ""),
        }
    }
}

/// Metadata about a registered command.
#[derive(Clone)]
pub struct CommandInfo {
    pub name: String,
    pub handler: Option<AsyncHandler>,
    pub args: Vec<ArgDef>,
    pub aliases: Vec<String>,
    pub permissions: Vec<String>,
    pub help: String,
    pub is_event: bool,
    pub rate_limit: Option<f64>,
    pub hidden: bool,
}

impl std::fmt::Debug for CommandInfo {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("CommandInfo")
            .field("name", &self.name)
            .field("aliases", &self.aliases)
            .field("permissions", &self.permissions)
            .field("help", &self.help)
            .finish()
    }
}

impl CommandInfo {
    pub fn new(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            handler: None,
            args: Vec::new(),
            aliases: Vec::new(),
            permissions: Vec::new(),
            help: String::new(),
            is_event: false,
            rate_limit: None,
            hidden: false,
        }
    }

    pub fn with_handler(mut self, handler: AsyncHandler) -> Self {
        self.handler = Some(handler);
        self
    }

    pub fn with_alias(mut self, alias: impl Into<String>) -> Self {
        self.aliases.push(alias.into());
        self
    }

    pub fn with_arg(mut self, arg: ArgDef) -> Self {
        self.args.push(arg);
        self
    }

    pub fn with_permission(mut self, perm: impl Into<String>) -> Self {
        self.permissions.push(perm.into());
        self
    }

    pub fn with_help(mut self, help: impl Into<String>) -> Self {
        self.help = help.into();
        self
    }
}

/// Result of executing a command.
#[derive(Debug, Clone)]
pub struct CommandResult {
    pub name: String,
    pub args: HashMap<String, ArgValue>,
    pub status: CommandStatus,
    pub output: Option<ArgValue>,
    pub error: Option<String>,
    pub redirect: Option<OutputRedirect>,
}

/// Status of a command execution.
#[derive(Debug, Clone, PartialEq)]
pub enum CommandStatus {
    Success,
    Error,
    Unknown,
    PermissionDenied,
    MissingArgs,
    InvalidArgs,
    DryRun,
}

impl CommandResult {
    pub fn success(name: impl Into<String>, output: ArgValue) -> Self {
        Self {
            name: name.into(),
            args: HashMap::new(),
            status: CommandStatus::Success,
            output: Some(output),
            error: None,
            redirect: None,
        }
    }

    pub fn error(name: impl Into<String>, err: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            args: HashMap::new(),
            status: CommandStatus::Error,
            output: None,
            error: Some(err.into()),
            redirect: None,
        }
    }

    pub fn ok(&self) -> bool {
        self.status == CommandStatus::Success
    }
}

/// Describes where command output should be redirected.
#[derive(Debug, Clone)]
pub struct OutputRedirect {
    pub target: String,
    pub append: bool,
}

impl OutputRedirect {
    pub fn is_clipboard(&self) -> bool {
        self.target == "clipboard"
    }

    pub fn is_file(&self) -> bool {
        self.target != "clipboard" && self.target != "stdout"
    }
}
