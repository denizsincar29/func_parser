//! AST node types for func_parser_rs.

use crate::models::OutputRedirect;

/// Abstract AST node.
#[derive(Debug, Clone)]
pub enum AstNode {
    /// Plain text → default handler.
    Text(TextNode),
    /// A single command invocation.
    Command(CommandNode),
    /// A pipeline of commands connected by `|`.
    Pipeline(PipelineNode),
    /// `left && right` — run right only if left succeeds.
    And(Box<AndNode>),
    /// `left || right` — run right only if left fails.
    Or(Box<OrNode>),
    /// `//set` / `//setenv` variable assignment.
    SetVar(SetVarNode),
    /// `/execute <path>` — run a script file.
    ExecuteScript(ExecuteScriptNode),
    /// `if` conditional.
    If(Box<IfNode>),
    /// `while` loop.
    While(Box<WhileNode>),
}

#[derive(Debug, Clone)]
pub struct TextNode {
    pub content: String,
}

#[derive(Debug, Clone)]
pub struct CommandNode {
    pub name: String,
    pub args: Vec<String>,
    pub kwargs: std::collections::HashMap<String, String>,
    pub redirect: Option<OutputRedirect>,
}

#[derive(Debug, Clone)]
pub struct PipelineNode {
    pub commands: Vec<CommandNode>,
}

#[derive(Debug, Clone)]
pub struct AndNode {
    pub left: AstNode,
    pub right: AstNode,
}

#[derive(Debug, Clone)]
pub struct OrNode {
    pub left: AstNode,
    pub right: AstNode,
}

#[derive(Debug, Clone)]
pub struct SetVarNode {
    pub name: String,
    pub value: String,
    pub scope: VarScope,
}

#[derive(Debug, Clone, PartialEq)]
pub enum VarScope {
    Local,
    Env,
}

#[derive(Debug, Clone)]
pub struct ExecuteScriptNode {
    pub path: String,
}

#[derive(Debug, Clone)]
pub struct IfNode {
    pub condition: String,
    pub body: AstNode,
    pub else_body: Option<AstNode>,
}

#[derive(Debug, Clone)]
pub struct WhileNode {
    pub condition: String,
    pub body: AstNode,
    /// Guard against infinite loops.
    pub max_iterations: usize,
}
