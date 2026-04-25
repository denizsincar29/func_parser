//! Integration tests for the async Parser and sync SyncParser.

use std::collections::HashMap;
use std::sync::Arc;

use func_parser_rs::{
    CommandRegistry, ExecutionContext, Parser, PermissionChecker,
    models::{ArgDef, ArgValue, AsyncHandler, CommandInfo, CommandStatus},
    middleware::MiddlewareChain,
    pipeline::AsyncPipeline,
    sync_parser::SyncParser,
    variables::VariableStore,
};

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

macro_rules! handler {
    ($f:expr) => {{
        let f = $f;
        Arc::new(
            move |ctx: ExecutionContext, args: HashMap<String, ArgValue>| {
                let f = f.clone();
                Box::pin(async move { f(ctx, args).await })
                    as std::pin::Pin<
                        Box<
                            dyn std::future::Future<
                                    Output = func_parser_rs::errors::Result<ArgValue>,
                                > + Send,
                        >,
                    >
            },
        ) as AsyncHandler
    }};
}

fn make_parser() -> (Parser, Arc<std::sync::RwLock<CommandRegistry>>) {
    let registry = Arc::new(std::sync::RwLock::new(CommandRegistry::new()));
    let parser = Parser::new(
        Arc::clone(&registry),
        VariableStore::new(),
        PermissionChecker::new(),
        MiddlewareChain::new(),
        AsyncPipeline::new(),
    );
    (parser, registry)
}

fn make_sync_parser() -> SyncParser {
    SyncParser::default()
}

// ─────────────────────────────────────────────────────────────────────────────
// Async parser tests
// ─────────────────────────────────────────────────────────────────────────────

#[tokio::test]
async fn async_simple_command() {
    let (mut parser, registry) = make_parser();
    let greet_h: AsyncHandler = handler!(Arc::new(
        |_ctx: ExecutionContext, args: HashMap<String, ArgValue>| async move {
            let name = args.get("name").and_then(|v| v.as_str()).unwrap_or("World");
            Ok(ArgValue::String(format!("Hello, {}!", name)))
        }
    ));
    registry.write().unwrap().register(
        CommandInfo::new("greet")
            .with_handler(greet_h)
            .with_arg(ArgDef::new("name")),
    );

    let result = parser.execute("/greet Alice", ExecutionContext::new()).await;
    assert!(result.ok(), "expected ok, got {:?}", result.status);
    assert_eq!(result.output.unwrap().to_string(), "Hello, Alice!");
}

#[tokio::test]
async fn async_alias() {
    let (mut parser, registry) = make_parser();
    let h: AsyncHandler = handler!(Arc::new(
        |_ctx: ExecutionContext, _args: HashMap<String, ArgValue>| async move {
            Ok(ArgValue::String("alias works".to_string()))
        }
    ));
    registry.write().unwrap().register(
        CommandInfo::new("verbose_cmd")
            .with_handler(h)
            .with_alias("vc"),
    );

    let result = parser.execute("/vc", ExecutionContext::new()).await;
    assert!(result.ok());
    assert_eq!(result.output.unwrap().to_string(), "alias works");
}

#[tokio::test]
async fn async_unknown_command() {
    let (mut parser, _) = make_parser();
    let result = parser.execute("/nonexistent", ExecutionContext::new()).await;
    assert_eq!(result.status, CommandStatus::Unknown);
}

#[tokio::test]
async fn async_default_text_handler() {
    let (mut parser, registry) = make_parser();
    let h: AsyncHandler = handler!(Arc::new(
        |_ctx: ExecutionContext, args: HashMap<String, ArgValue>| async move {
            let content = args.get("content").and_then(|v| v.as_str()).unwrap_or("");
            Ok(ArgValue::String(format!("echo: {}", content)))
        }
    ));
    registry.write().unwrap().set_default(h);

    let result = parser.execute("hello world", ExecutionContext::new()).await;
    assert!(result.ok());
    assert_eq!(result.output.unwrap().to_string(), "echo: hello world");
}

#[tokio::test]
async fn async_pipeline() {
    let (mut parser, registry) = make_parser();

    let upper_h: AsyncHandler = handler!(Arc::new(
        |_ctx: ExecutionContext, args: HashMap<String, ArgValue>| async move {
            let t = args.get("text").and_then(|v| v.as_str()).unwrap_or("");
            Ok(ArgValue::String(t.to_uppercase()))
        }
    ));
    let exclaim_h: AsyncHandler = handler!(Arc::new(
        |_ctx: ExecutionContext, args: HashMap<String, ArgValue>| async move {
            let t = args.get("text").and_then(|v| v.as_str()).unwrap_or("");
            Ok(ArgValue::String(format!("{}!", t)))
        }
    ));

    {
        let mut r = registry.write().unwrap();
        r.register(CommandInfo::new("upper").with_handler(upper_h).with_arg(ArgDef::new("text")));
        r.register(CommandInfo::new("exclaim").with_handler(exclaim_h).with_arg(ArgDef::new("text")));
    }

    let result = parser.execute("/upper hello | /exclaim", ExecutionContext::new()).await;
    assert!(result.ok());
    assert_eq!(result.output.unwrap().to_string(), "HELLO!");
}

#[tokio::test]
async fn async_and_short_circuit() {
    let (mut parser, registry) = make_parser();
    let calls = Arc::new(std::sync::Mutex::new(vec![]));

    let calls_clone = Arc::clone(&calls);
    let fail_h: AsyncHandler = handler!(Arc::new(move |_ctx, _args| {
        let _ = calls_clone;
        async move { Err(func_parser_rs::errors::FuncParserError::Other("fail".to_string())) }
    }));

    let calls_clone2 = Arc::clone(&calls);
    let after_h: AsyncHandler = handler!(Arc::new(move |_ctx, _args| {
        calls_clone2.lock().unwrap().push("after");
        async move { Ok(ArgValue::String("after".to_string())) }
    }));

    {
        let mut r = registry.write().unwrap();
        r.register(CommandInfo::new("fail_cmd").with_handler(fail_h));
        r.register(CommandInfo::new("after_cmd").with_handler(after_h));
    }

    let result = parser.execute("/fail_cmd && /after_cmd", ExecutionContext::new()).await;
    assert!(!result.ok());
    assert!(calls.lock().unwrap().is_empty(), "after_cmd should not have run");
}

#[tokio::test]
async fn async_or_second_runs_on_failure() {
    let (mut parser, registry) = make_parser();

    let fail_h: AsyncHandler = handler!(Arc::new(|_ctx, _args| async move {
        Err(func_parser_rs::errors::FuncParserError::Other("fail".to_string()))
    }));
    let fallback_h: AsyncHandler = handler!(Arc::new(|_ctx, _args| async move {
        Ok(ArgValue::String("fallback".to_string()))
    }));

    {
        let mut r = registry.write().unwrap();
        r.register(CommandInfo::new("fail2").with_handler(fail_h));
        r.register(CommandInfo::new("fallback").with_handler(fallback_h));
    }

    let result = parser.execute("/fail2 || /fallback", ExecutionContext::new()).await;
    assert!(result.ok());
    assert_eq!(result.output.unwrap().to_string(), "fallback");
}

#[tokio::test]
async fn async_set_var_and_expand() {
    let (mut parser, registry) = make_parser();

    let echo_h: AsyncHandler = handler!(Arc::new(
        |_ctx: ExecutionContext, args: HashMap<String, ArgValue>| async move {
            let msg = args.get("msg").and_then(|v| v.as_str()).unwrap_or("").to_string();
            Ok(ArgValue::String(msg))
        }
    ));
    registry.write().unwrap().register(
        CommandInfo::new("echo").with_handler(echo_h).with_arg(ArgDef::new("msg")),
    );

    parser.execute("//set greeting=hello", ExecutionContext::new()).await;
    let result = parser.execute("/echo ${greeting}", ExecutionContext::new()).await;
    assert!(result.ok());
    assert_eq!(result.output.unwrap().to_string(), "hello");
}

#[tokio::test]
async fn async_permission_denied() {
    let (mut parser, registry) = make_parser();

    let secret_h: AsyncHandler = handler!(Arc::new(|_ctx, _args| async move {
        Ok(ArgValue::String("secret".to_string()))
    }));
    registry.write().unwrap().register(
        CommandInfo::new("secret")
            .with_handler(secret_h)
            .with_permission("admin"),
    );

    let mut ctx_user = ExecutionContext::new();
    ctx_user.user.roles = vec!["user".to_string()];

    let mut ctx_admin = ExecutionContext::new();
    ctx_admin.user.roles = vec!["admin".to_string()];

    let denied = parser.execute("/secret", ctx_user).await;
    assert_eq!(denied.status, CommandStatus::PermissionDenied);

    let allowed = parser.execute("/secret", ctx_admin).await;
    assert!(allowed.ok());
}

#[tokio::test]
async fn async_optional_arg_default() {
    let (mut parser, registry) = make_parser();

    let greet_h: AsyncHandler = handler!(Arc::new(
        |_ctx: ExecutionContext, args: HashMap<String, ArgValue>| async move {
            let name = args.get("name").and_then(|v| v.as_str()).unwrap_or("World");
            Ok(ArgValue::String(format!("Hello, {}!", name)))
        }
    ));
    registry.write().unwrap().register(
        CommandInfo::new("greet2")
            .with_handler(greet_h)
            .with_arg(ArgDef::new("name").optional("World")),
    );

    let result = parser.execute("/greet2", ExecutionContext::new()).await;
    assert!(result.ok());
    assert_eq!(result.output.unwrap().to_string(), "Hello, World!");
}

// ─────────────────────────────────────────────────────────────────────────────
// SyncParser tests
// ─────────────────────────────────────────────────────────────────────────────

#[test]
fn sync_simple_command() {
    let mut sp = make_sync_parser();

    let greet_h: AsyncHandler = handler!(Arc::new(
        |_ctx: ExecutionContext, args: HashMap<String, ArgValue>| async move {
            let name = args.get("name").and_then(|v| v.as_str()).unwrap_or("World");
            Ok(ArgValue::String(format!("Hi, {}!", name)))
        }
    ));
    sp.register(
        CommandInfo::new("greet")
            .with_handler(greet_h)
            .with_arg(ArgDef::new("name")),
    );

    let result = sp.execute("/greet Bob", ExecutionContext::new());
    assert!(result.ok());
    assert_eq!(result.output.unwrap().to_string(), "Hi, Bob!");
}

#[test]
fn sync_default_text_handler() {
    let mut sp = make_sync_parser();

    let default_h: AsyncHandler = handler!(Arc::new(
        |_ctx: ExecutionContext, args: HashMap<String, ArgValue>| async move {
            let content = args.get("content").and_then(|v| v.as_str()).unwrap_or("").to_string();
            Ok(ArgValue::String(format!("text: {}", content)))
        }
    ));
    sp.set_default(default_h);

    let result = sp.execute("plain text", ExecutionContext::new());
    assert!(result.ok());
    assert_eq!(result.output.unwrap().to_string(), "text: plain text");
}

#[test]
fn sync_unknown_command() {
    let mut sp = make_sync_parser();
    let result = sp.execute("/unknown", ExecutionContext::new());
    assert_eq!(result.status, CommandStatus::Unknown);
}

#[test]
fn sync_pipeline() {
    let mut sp = make_sync_parser();

    let upper_h: AsyncHandler = handler!(Arc::new(
        |_ctx: ExecutionContext, args: HashMap<String, ArgValue>| async move {
            let t = args.get("text").and_then(|v| v.as_str()).unwrap_or("").to_string();
            Ok(ArgValue::String(t.to_uppercase()))
        }
    ));
    let exclaim_h: AsyncHandler = handler!(Arc::new(
        |_ctx: ExecutionContext, args: HashMap<String, ArgValue>| async move {
            let t = args.get("text").and_then(|v| v.as_str()).unwrap_or("").to_string();
            Ok(ArgValue::String(format!("{}!", t)))
        }
    ));

    sp.register(CommandInfo::new("upper").with_handler(upper_h).with_arg(ArgDef::new("text")));
    sp.register(CommandInfo::new("exclaim").with_handler(exclaim_h).with_arg(ArgDef::new("text")));

    let result = sp.execute("/upper hello | /exclaim", ExecutionContext::new());
    assert!(result.ok());
    assert_eq!(result.output.unwrap().to_string(), "HELLO!");
}

#[test]
fn sync_set_var_and_expand() {
    let mut sp = make_sync_parser();

    let echo_h: AsyncHandler = handler!(Arc::new(
        |_ctx: ExecutionContext, args: HashMap<String, ArgValue>| async move {
            let msg = args.get("msg").and_then(|v| v.as_str()).unwrap_or("").to_string();
            Ok(ArgValue::String(msg))
        }
    ));
    sp.register(CommandInfo::new("echo").with_handler(echo_h).with_arg(ArgDef::new("msg")));

    sp.execute("//set greeting=world", ExecutionContext::new());
    let result = sp.execute("/echo ${greeting}", ExecutionContext::new());
    assert!(result.ok());
    assert_eq!(result.output.unwrap().to_string(), "world");
}

#[test]
fn sync_alias() {
    let mut sp = make_sync_parser();

    let h: AsyncHandler = handler!(Arc::new(|_ctx, _args| async move {
        Ok(ArgValue::String("alias ok".to_string()))
    }));
    sp.register(CommandInfo::new("long_name").with_handler(h).with_alias("ln"));

    let result = sp.execute("/ln", ExecutionContext::new());
    assert!(result.ok());
    assert_eq!(result.output.unwrap().to_string(), "alias ok");
}

#[test]
fn sync_help() {
    let mut sp = make_sync_parser();
    let h: AsyncHandler = handler!(Arc::new(|_ctx, _args| async move {
        Ok(ArgValue::None)
    }));
    sp.register(CommandInfo::new("demo").with_handler(h).with_help("A demo command"));
    let help = sp.help();
    assert!(help.contains("demo"));
    assert!(help.contains("A demo command"));
}

#[test]
fn sync_and_short_circuit() {
    let mut sp = make_sync_parser();

    let fail_h: AsyncHandler = handler!(Arc::new(|_ctx, _args| async move {
        Err(func_parser_rs::errors::FuncParserError::Other("fail".to_string()))
    }));
    let after_h: AsyncHandler = handler!(Arc::new(|_ctx, _args| async move {
        Ok(ArgValue::String("should not run".to_string()))
    }));

    sp.register(CommandInfo::new("sfail").with_handler(fail_h));
    sp.register(CommandInfo::new("safter").with_handler(after_h));

    let result = sp.execute("/sfail && /safter", ExecutionContext::new());
    assert!(!result.ok());
}

#[test]
fn sync_or_fallback() {
    let mut sp = make_sync_parser();

    let fail_h: AsyncHandler = handler!(Arc::new(|_ctx, _args| async move {
        Err(func_parser_rs::errors::FuncParserError::Other("fail".to_string()))
    }));
    let fallback_h: AsyncHandler = handler!(Arc::new(|_ctx, _args| async move {
        Ok(ArgValue::String("fell back".to_string()))
    }));

    sp.register(CommandInfo::new("sfail2").with_handler(fail_h));
    sp.register(CommandInfo::new("sfallback").with_handler(fallback_h));

    let result = sp.execute("/sfail2 || /sfallback", ExecutionContext::new());
    assert!(result.ok());
    assert_eq!(result.output.unwrap().to_string(), "fell back");
}
