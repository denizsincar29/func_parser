//! Integration tests for func_parser_rs — tokenizer, registry, variables, permissions.

use func_parser_rs::{
    CommandRegistry,
    tokenizer::{TokenType, Tokenizer},
    variables::VariableStore,
    permissions::PermissionChecker,
    models::{ArgDef, CommandInfo},
};

// ───────────────────────────────────────────────────────────────────────────────
// Tokenizer
// ───────────────────────────────────────────────────────────────────────────────

fn types(text: &str) -> Vec<TokenType> {
    Tokenizer::new()
        .tokenize(text)
        .into_iter()
        .filter(|t| t.kind != TokenType::Eof)
        .map(|t| t.kind)
        .collect()
}

fn values(text: &str) -> Vec<String> {
    Tokenizer::new()
        .tokenize(text)
        .into_iter()
        .filter(|t| t.kind != TokenType::Eof)
        .map(|t| t.value)
        .collect()
}

#[test]
fn tokenizer_command() {
    assert_eq!(types("/greet"), vec![TokenType::Command]);
    assert_eq!(values("/greet"), vec!["/greet"]);
}

#[test]
fn tokenizer_command_with_args() {
    let t = types("/greet Alice 42");
    assert_eq!(t, vec![TokenType::Command, TokenType::Arg, TokenType::Arg]);
    let v = values("/greet Alice 42");
    assert_eq!(v, vec!["/greet", "Alice", "42"]);
}

#[test]
fn tokenizer_plain_text_not_command() {
    let t = types("hello world");
    assert!(!t.contains(&TokenType::Command));
}

#[test]
fn tokenizer_pipe() {
    let t = types("/a | /b");
    assert!(t.contains(&TokenType::Pipe));
}

#[test]
fn tokenizer_and() {
    let t = types("/a && /b");
    assert!(t.contains(&TokenType::And));
}

#[test]
fn tokenizer_or() {
    let t = types("/a || /b");
    assert!(t.contains(&TokenType::Or));
}

#[test]
fn tokenizer_redirect_out() {
    let t = types("/cmd > file.txt");
    assert!(t.contains(&TokenType::RedirectOut));
}

#[test]
fn tokenizer_redirect_append() {
    let t = types("/cmd >> file.txt");
    assert!(t.contains(&TokenType::RedirectAppend));
}

#[test]
fn tokenizer_redirect_clipboard() {
    let t = types("/cmd >clipboard");
    assert!(t.contains(&TokenType::RedirectClipboard));
}

#[test]
fn tokenizer_redirect_clipboard_append() {
    let t = types("/cmd >>clipboard");
    assert!(t.contains(&TokenType::RedirectClipboard));
}

#[test]
fn tokenizer_set_var() {
    let t = types("//set x=5");
    assert_eq!(t[0], TokenType::SetVar);
}

#[test]
fn tokenizer_setenv() {
    let t = types("//setenv HOME=/tmp");
    assert_eq!(t[0], TokenType::SetVar);
}

#[test]
fn tokenizer_execute() {
    let t = types("/execute script.txt");
    assert_eq!(t[0], TokenType::Execute);
}

#[test]
fn tokenizer_comment() {
    let t = types("# this is ignored");
    assert_eq!(t[0], TokenType::Comment);
}

#[test]
fn tokenizer_quoted_arg() {
    let v = values(r#"/say "hello world""#);
    assert_eq!(v, vec!["/say", "hello world"]);
}

#[test]
fn tokenizer_kwarg() {
    let v = values("/cmd name=Alice");
    assert!(v.iter().any(|s| s == "name=Alice"));
}

#[test]
fn tokenizer_file_injection() {
    let v = values("/cmd {file.txt}");
    assert!(v.iter().any(|s| s == "{file.txt}"));
}

#[test]
fn tokenizer_command_after_pipe() {
    let t = types("/a | /b");
    // After PIPE the next word should be COMMAND
    let has_second_cmd = t.windows(2).any(|w| w[0] == TokenType::Pipe && w[1] == TokenType::Command);
    assert!(has_second_cmd);
}

#[test]
fn tokenizer_empty_string() {
    let toks = Tokenizer::new().tokenize("");
    assert_eq!(toks.len(), 1);
    assert_eq!(toks[0].kind, TokenType::Eof);
}

// ───────────────────────────────────────────────────────────────────────────────
// CommandRegistry
// ───────────────────────────────────────────────────────────────────────────────

#[test]
fn registry_register_and_get() {
    let mut reg = CommandRegistry::new();
    reg.register(CommandInfo::new("greet").with_help("Greet someone"));
    assert!(reg.get("greet").is_some());
    assert_eq!(reg.get("greet").unwrap().name, "greet");
}

#[test]
fn registry_alias_lookup() {
    let mut reg = CommandRegistry::new();
    reg.register(CommandInfo::new("greet").with_alias("g"));
    assert!(reg.get("g").is_some());
    assert_eq!(reg.get("g").unwrap().name, "greet");
}

#[test]
fn registry_missing_returns_none() {
    let reg = CommandRegistry::new();
    assert!(reg.get("nonexistent").is_none());
}

#[test]
fn registry_contains() {
    let mut reg = CommandRegistry::new();
    reg.register(CommandInfo::new("cmd").with_alias("c"));
    assert!(reg.contains("cmd"));
    assert!(reg.contains("c"));
    assert!(!reg.contains("unknown"));
}

#[test]
fn registry_all_commands() {
    let mut reg = CommandRegistry::new();
    reg.register(CommandInfo::new("a"));
    reg.register(CommandInfo::new("b"));
    assert_eq!(reg.all_commands().len(), 2);
}

#[test]
fn registry_namespace() {
    let mut reg = CommandRegistry::new();
    reg.register(CommandInfo::new("user.create"));
    reg.register(CommandInfo::new("user.list"));
    reg.register(CommandInfo::new("file.read"));
    let user_cmds = reg.namespace("user");
    assert_eq!(user_cmds.len(), 2);
}

// ───────────────────────────────────────────────────────────────────────────────
// VariableStore
// ───────────────────────────────────────────────────────────────────────────────

#[test]
fn variables_set_get() {
    let mut vs = VariableStore::new();
    vs.set("x", "42");
    assert_eq!(vs.get("x").map(|s| s.as_str()), Some("42"));
}

#[test]
fn variables_expand_braces() {
    let mut vs = VariableStore::new();
    vs.set("name", "Alice");
    assert_eq!(vs.expand("Hello ${name}!"), "Hello Alice!");
}

#[test]
fn variables_expand_unknown_unchanged() {
    let vs = VariableStore::new();
    assert_eq!(vs.expand("${undefined_xyz}"), "${undefined_xyz}");
}

#[test]
fn variables_expand_env_var() {
    std::env::set_var("FUNC_PARSER_TEST_VAR", "found");
    let vs = VariableStore::new();
    assert_eq!(vs.expand("$FUNC_PARSER_TEST_VAR"), "found");
}

#[test]
fn variables_get_owned() {
    let mut vs = VariableStore::new();
    vs.set("key", "val");
    assert_eq!(vs.get_owned("key"), Some("val".to_string()));
    assert_eq!(vs.get_owned("missing"), None);
}

// ───────────────────────────────────────────────────────────────────────────────
// PermissionChecker
// ───────────────────────────────────────────────────────────────────────────────

#[test]
fn permissions_admin_can_do_anything() {
    let checker = PermissionChecker::new();
    assert!(checker.check(&["admin".to_string()], &["any_perm".to_string()], "u1"));
}

#[test]
fn permissions_user_denied_by_default() {
    let checker = PermissionChecker::new();
    assert!(!checker.check(&["user".to_string()], &["admin".to_string()], "u1"));
}

#[test]
fn permissions_no_required_always_passes() {
    let checker = PermissionChecker::new();
    assert!(checker.check(&["user".to_string()], &[], "u1"));
}

#[test]
fn permissions_grant_and_check() {
    let mut checker = PermissionChecker::new();
    checker.grant("u1", "write");
    assert!(checker.check(&["user".to_string()], &["write".to_string()], "u1"));
}

#[test]
fn permissions_revoke() {
    let mut checker = PermissionChecker::new();
    checker.grant("u1", "write");
    checker.revoke("u1", "write");
    assert!(!checker.check(&["user".to_string()], &["write".to_string()], "u1"));
}

#[test]
fn permissions_require_raises_on_missing() {
    let checker = PermissionChecker::new();
    assert!(checker
        .require(&["user".to_string()], &["admin".to_string()], "u1")
        .is_err());
}

#[test]
fn permissions_add_role() {
    let mut checker = PermissionChecker::new();
    checker.add_role("editor", vec!["write".to_string(), "read".to_string()]);
    assert!(checker.check(&["editor".to_string()], &["write".to_string()], "u1"));
}

// ───────────────────────────────────────────────────────────────────────────────
// ArgDef builder
// ───────────────────────────────────────────────────────────────────────────────

#[test]
fn argdef_defaults() {
    let a = ArgDef::new("name");
    assert_eq!(a.name, "name");
    assert!(a.required);
    assert!(a.default.is_none());
}

#[test]
fn argdef_optional() {
    let a = ArgDef::new("name").optional("World");
    assert!(!a.required);
    assert_eq!(a.default.as_deref(), Some("World"));
}

#[test]
fn argdef_variadic() {
    let a = ArgDef::new("words").variadic();
    assert!(a.variadic);
}
