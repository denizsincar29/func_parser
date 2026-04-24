//! Main parser / executor for func_parser_rs.

use std::collections::HashMap;
use std::sync::Arc;

use crate::ast::{AstNode, CommandNode, PipelineNode, SetVarNode, TextNode, VarScope};
use crate::context::ExecutionContext;
use crate::errors::{FuncParserError, Result};
use crate::middleware::MiddlewareChain;
use crate::models::{ArgValue, CommandResult, CommandStatus, OutputRedirect};
use crate::permissions::PermissionChecker;
use crate::pipeline::AsyncPipeline;
use crate::registry::CommandRegistry;
use crate::tokenizer::{Token, TokenType, Tokenizer};
use crate::variables::VariableStore;

/// Main parser: converts input strings into AST nodes and executes them.
pub struct Parser {
    registry: Arc<std::sync::RwLock<CommandRegistry>>,
    vars: VariableStore,
    permissions: PermissionChecker,
    middleware: MiddlewareChain,
    pipeline: AsyncPipeline,
    pub debug: bool,
}

impl Parser {
    pub fn new(
        registry: Arc<std::sync::RwLock<CommandRegistry>>,
        vars: VariableStore,
        permissions: PermissionChecker,
        middleware: MiddlewareChain,
        pipeline: AsyncPipeline,
    ) -> Self {
        Self {
            registry,
            vars,
            permissions,
            middleware,
            pipeline,
            debug: false,
        }
    }

    // -----------------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------------

    /// Parse `input` and return an AST node.
    pub fn parse(&self, input: &str) -> AstNode {
        let expanded = self.vars.expand(input);
        let tokenizer = Tokenizer::new();
        let tokens = tokenizer.tokenize(&expanded);
        self.parse_tokens(&tokens, &expanded)
    }

    /// Parse and execute `input` in `ctx`.
    pub async fn execute(&mut self, input: &str, ctx: ExecutionContext) -> CommandResult {
        let node = self.parse(input);
        self.execute_node(node, ctx).await
    }

    /// Execute an AST node.
    pub async fn execute_node(&mut self, node: AstNode, ctx: ExecutionContext) -> CommandResult {
        match node {
            AstNode::Text(n) => self.execute_text(n, ctx).await,
            AstNode::Command(n) => self.execute_command(n, ctx).await,
            AstNode::Pipeline(n) => self.execute_pipeline(n, ctx).await,
            AstNode::And(n) => {
                let left = self.execute_node(n.left, ctx.clone()).await;
                if !left.ok() { return left; }
                self.execute_node(n.right, ctx).await
            }
            AstNode::Or(n) => {
                let left = self.execute_node(n.left, ctx.clone()).await;
                if left.ok() { return left; }
                self.execute_node(n.right, ctx).await
            }
            AstNode::SetVar(n) => self.execute_set_var(n),
            AstNode::ExecuteScript(n) => self.execute_script(&n.path, ctx).await,
            AstNode::If(n) => {
                let cond_val = self.vars.get_owned(&n.condition).unwrap_or_default();
                let truthy = !matches!(cond_val.to_lowercase().as_str(), "" | "0" | "false" | "no" | "none");
                if truthy {
                    self.execute_node(n.body, ctx).await
                } else if let Some(else_body) = n.else_body {
                    self.execute_node(else_body, ctx).await
                } else {
                    CommandResult::success("if", ArgValue::None)
                }
            }
            AstNode::While(n) => {
                let mut last = CommandResult::success("while", ArgValue::None);
                for _ in 0..n.max_iterations {
                    let cond_val = self.vars.get_owned(&n.condition).unwrap_or_default();
                    let truthy = !matches!(cond_val.to_lowercase().as_str(), "" | "0" | "false" | "no" | "none");
                    if !truthy { break; }
                    last = self.execute_node(n.body.clone(), ctx.clone()).await;
                    if last.status == CommandStatus::Error { break; }
                }
                last
            }
        }
    }

    // -----------------------------------------------------------------------
    // Token → AST
    // -----------------------------------------------------------------------

    fn parse_tokens(&self, tokens: &[Token], raw: &str) -> AstNode {
        let meaningful: Vec<&Token> = tokens
            .iter()
            .filter(|t| !matches!(t.kind, TokenType::Eof | TokenType::Comment))
            .collect();

        if meaningful.is_empty() {
            return AstNode::Text(TextNode { content: raw.to_string() });
        }
        self.parse_logical(&meaningful, raw)
    }

    fn parse_logical(&self, tokens: &[&Token], raw: &str) -> AstNode {
        for i in (0..tokens.len()).rev() {
            if tokens[i].kind == TokenType::And {
                let left = self.parse_pipeline(&tokens[..i], raw);
                let right = self.parse_logical(&tokens[i + 1..], raw);
                return AstNode::And(Box::new(crate::ast::AndNode { left, right }));
            }
            if tokens[i].kind == TokenType::Or {
                let left = self.parse_pipeline(&tokens[..i], raw);
                let right = self.parse_logical(&tokens[i + 1..], raw);
                return AstNode::Or(Box::new(crate::ast::OrNode { left, right }));
            }
        }
        self.parse_pipeline(tokens, raw)
    }

    fn parse_pipeline(&self, tokens: &[&Token], raw: &str) -> AstNode {
        let mut segments: Vec<Vec<&Token>> = Vec::new();
        let mut current: Vec<&Token> = Vec::new();
        for tok in tokens {
            if tok.kind == TokenType::Pipe {
                segments.push(current);
                current = Vec::new();
            } else {
                current.push(tok);
            }
        }
        segments.push(current);

        if segments.len() == 1 {
            return self.parse_single(&segments[0], raw);
        }

        let mut commands = Vec::new();
        for seg in &segments {
            if let AstNode::Command(c) = self.parse_single(seg, raw) {
                commands.push(c);
            }
        }
        AstNode::Pipeline(PipelineNode { commands })
    }

    fn parse_single(&self, tokens: &[&Token], raw: &str) -> AstNode {
        if tokens.is_empty() {
            return AstNode::Text(TextNode { content: String::new() });
        }
        let first = tokens[0];
        match first.kind {
            TokenType::SetVar => {
                let directive = first.value.to_lowercase();
                let scope = if directive == "//setenv" { VarScope::Env } else { VarScope::Local };
                let assignment = tokens.get(1).map(|t| t.value.as_str()).unwrap_or("");
                let (name, value) = if let Some(eq) = assignment.find('=') {
                    (assignment[..eq].trim().to_string(), assignment[eq + 1..].trim().to_string())
                } else {
                    (assignment.trim().to_string(), String::new())
                };
                AstNode::SetVar(SetVarNode { name, value, scope })
            }
            TokenType::Execute => {
                let path = tokens.get(1).map(|t| t.value.clone()).unwrap_or_default();
                AstNode::ExecuteScript(crate::ast::ExecuteScriptNode { path })
            }
            TokenType::Command => {
                let name = first.value.trim_start_matches('/').to_string();
                let mut args = Vec::new();
                let mut kwargs = HashMap::new();
                let mut redirect: Option<OutputRedirect> = None;
                let mut i = 1;
                while i < tokens.len() {
                    let tok = tokens[i];
                    match tok.kind {
                        TokenType::RedirectOut => {
                            i += 1;
                            let target = tokens.get(i).map(|t| t.value.clone()).unwrap_or("stdout".to_string());
                            redirect = Some(OutputRedirect { target, append: false });
                        }
                        TokenType::RedirectAppend => {
                            i += 1;
                            let target = tokens.get(i).map(|t| t.value.clone()).unwrap_or("stdout".to_string());
                            redirect = Some(OutputRedirect { target, append: true });
                        }
                        TokenType::RedirectClipboard => {
                            let append = tok.value.starts_with(">>");
                            redirect = Some(OutputRedirect { target: "clipboard".to_string(), append });
                        }
                        TokenType::Arg => {
                            let val = &tok.value;
                            if val.contains('=') && !val.starts_with('{') {
                                let eq = val.find('=').unwrap();
                                kwargs.insert(val[..eq].to_string(), val[eq + 1..].to_string());
                            } else {
                                args.push(val.clone());
                            }
                        }
                        _ => {}
                    }
                    i += 1;
                }
                AstNode::Command(CommandNode { name, args, kwargs, redirect })
            }
            _ => AstNode::Text(TextNode { content: raw.to_string() }),
        }
    }

    // -----------------------------------------------------------------------
    // Execution helpers
    // -----------------------------------------------------------------------

    async fn execute_text(&self, node: TextNode, ctx: ExecutionContext) -> CommandResult {
        let registry = self.registry.read().unwrap();
        let handler = match registry.default_handler() {
            Some(h) => h.clone(),
            None => {
                return CommandResult {
                    name: "default".to_string(),
                    args: HashMap::new(),
                    status: CommandStatus::Success,
                    output: Some(ArgValue::None),
                    error: None,
                    redirect: None,
                };
            }
        };
        drop(registry);

        let mut args = HashMap::new();
        args.insert("content".to_string(), ArgValue::String(node.content));
        match handler(ctx, args.clone()).await {
            Ok(output) => CommandResult {
                name: "default".to_string(),
                args,
                status: CommandStatus::Success,
                output: Some(output),
                error: None,
                redirect: None,
            },
            Err(e) => CommandResult::error("default", e.to_string()),
        }
    }

    async fn execute_command(&mut self, node: CommandNode, ctx: ExecutionContext) -> CommandResult {
        let cmd_info = {
            let registry = self.registry.read().unwrap();
            registry.get(&node.name).cloned()
        };

        let cmd_info = match cmd_info {
            Some(c) => c,
            None => {
                return CommandResult {
                    name: node.name.clone(),
                    args: HashMap::new(),
                    status: CommandStatus::Unknown,
                    output: None,
                    error: Some(format!("Command not found: {:?}", node.name)),
                    redirect: None,
                };
            }
        };

        // Permission check
        if let Err(e) = self.permissions.require(&ctx.user.roles, &cmd_info.permissions, &ctx.user.id) {
            return CommandResult {
                name: node.name.clone(),
                args: HashMap::new(),
                status: CommandStatus::PermissionDenied,
                output: None,
                error: Some(e.to_string()),
                redirect: None,
            };
        }

        // Rate limit
        if let Err(e) = self.middleware.check_rate_limit(&node.name) {
            return CommandResult {
                name: node.name.clone(),
                args: HashMap::new(),
                status: CommandStatus::Error,
                output: None,
                error: Some(e.to_string()),
                redirect: None,
            };
        }

        // Build args
        let parsed_args = self.build_args(&node, &cmd_info);

        // Execute
        let mut result = self.pipeline.execute(&cmd_info, parsed_args, ctx).await;
        result.redirect = node.redirect;

        // Handle redirect
        if result.redirect.is_some() {
            let _ = self.pipeline.redirect_output(&result).await;
        }

        if self.debug {
            eprintln!("[DEBUG] {:?}", result);
        }
        result
    }

    async fn execute_pipeline(&mut self, node: PipelineNode, ctx: ExecutionContext) -> CommandResult {
        let mut last: Option<CommandResult> = None;
        let mut injected: Option<String> = None;

        for mut cmd_node in node.commands {
            if let Some(ref prev) = injected {
                cmd_node.args.insert(0, prev.clone());
            }
            let result = self.execute_command(cmd_node, ctx.clone()).await;
            injected = result.output.as_ref().map(|o| o.to_string());
            last = Some(result);
        }
        last.unwrap_or_else(|| CommandResult::success("pipeline", ArgValue::None))
    }

    fn execute_set_var(&mut self, node: SetVarNode) -> CommandResult {
        match node.scope {
            VarScope::Env => self.vars.set_env(&node.name, &node.value),
            VarScope::Local => self.vars.set(&node.name, &node.value),
        }
        CommandResult::success("set_var", ArgValue::None)
    }

    async fn execute_script(&mut self, path: &str, ctx: ExecutionContext) -> CommandResult {
        let content = match std::fs::read_to_string(path) {
            Ok(c) => c,
            Err(e) => return CommandResult::error("execute", e.to_string()),
        };
        let mut last = CommandResult::success("execute", ArgValue::None);
        for line in content.lines() {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            last = self.execute(line, ctx.clone()).await;
        }
        last
    }

    fn build_args(
        &self,
        node: &CommandNode,
        cmd_info: &crate::models::CommandInfo,
    ) -> HashMap<String, ArgValue> {
        let mut result = HashMap::new();
        let mut pos_iter = node.args.iter();

        for arg_def in &cmd_info.args {
            if let Some(raw) = node.kwargs.get(&arg_def.name) {
                result.insert(arg_def.name.clone(), ArgValue::String(raw.clone()));
            } else if arg_def.variadic {
                let remaining: Vec<ArgValue> = pos_iter
                    .by_ref()
                    .map(|v| ArgValue::String(v.clone()))
                    .collect();
                result.insert(arg_def.name.clone(), ArgValue::List(remaining));
            } else if let Some(raw) = pos_iter.next() {
                result.insert(arg_def.name.clone(), ArgValue::String(raw.clone()));
            } else if let Some(default) = &arg_def.default {
                result.insert(arg_def.name.clone(), ArgValue::String(default.clone()));
            }
            // Missing required args are silently skipped here; handlers receive None
        }
        result
    }
}
