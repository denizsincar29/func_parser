//! Basic usage example for func_parser_rs.

use std::collections::HashMap;
use std::sync::Arc;

use func_parser_rs::{
    CommandRegistry, ExecutionContext, Parser, PermissionChecker,
    models::{ArgDef, ArgValue, AsyncHandler, CommandInfo, CommandStatus},
    middleware::MiddlewareChain,
    pipeline::AsyncPipeline,
    variables::VariableStore,
};

/// Convenience: wrap a simple async closure into an `AsyncHandler`.
macro_rules! handler {
    ($f:expr) => {{
        let f = $f;
        Arc::new(
            move |ctx: ExecutionContext, args: HashMap<String, ArgValue>| {
                let f = f.clone();
                Box::pin(async move { f(ctx, args).await })
                    as std::pin::Pin<Box<dyn std::future::Future<Output = func_parser_rs::errors::Result<ArgValue>> + Send>>
            },
        ) as AsyncHandler
    }};
}

#[tokio::main]
async fn main() {
    println!("=== func_parser_rs basic example ===\n");

    let mut registry = CommandRegistry::new();

    // Register /greet <name>
    let greet_handler: AsyncHandler = handler!(Arc::new(
        |_ctx: ExecutionContext, args: HashMap<String, ArgValue>| async move {
            let name = args.get("name")
                .and_then(|v| v.as_str())
                .unwrap_or("World");
            Ok(ArgValue::String(format!("Hello, {}!", name)))
        }
    ));

    registry.register(
        CommandInfo::new("greet")
            .with_handler(greet_handler)
            .with_arg(ArgDef::new("name"))
            .with_alias("g")
            .with_help("Greet someone"),
    );

    // Register /add <a> <b>
    let add_handler: AsyncHandler = handler!(Arc::new(
        |_ctx: ExecutionContext, args: HashMap<String, ArgValue>| async move {
            let a: f64 = args.get("a").and_then(|v| v.as_str()).unwrap_or("0").parse().unwrap_or(0.0);
            let b: f64 = args.get("b").and_then(|v| v.as_str()).unwrap_or("0").parse().unwrap_or(0.0);
            Ok(ArgValue::Float(a + b))
        }
    ));

    registry.register(
        CommandInfo::new("add")
            .with_handler(add_handler)
            .with_arg(ArgDef::new("a"))
            .with_arg(ArgDef::new("b"))
            .with_help("Add two numbers"),
    );

    // Register /upper <text>
    let upper_handler: AsyncHandler = handler!(Arc::new(
        |_ctx: ExecutionContext, args: HashMap<String, ArgValue>| async move {
            let text = args.get("text").and_then(|v| v.as_str()).unwrap_or("");
            Ok(ArgValue::String(text.to_uppercase()))
        }
    ));

    registry.register(
        CommandInfo::new("upper")
            .with_handler(upper_handler)
            .with_arg(ArgDef::new("text"))
            .with_help("Convert to uppercase"),
    );

    // Default handler for plain text
    let default_handler: AsyncHandler = handler!(Arc::new(
        |_ctx: ExecutionContext, args: HashMap<String, ArgValue>| async move {
            let content = args.get("content").and_then(|v| v.as_str()).unwrap_or("");
            Ok(ArgValue::String(format!("(text) {}", content)))
        }
    ));
    registry.set_default(default_handler);

    let registry = Arc::new(std::sync::RwLock::new(registry));
    let mut parser = Parser::new(
        registry,
        VariableStore::new(),
        PermissionChecker::new(),
        MiddlewareChain::new(),
        AsyncPipeline::new(),
    );

    let ctx = ExecutionContext::new();

    let inputs = vec![
        "/greet Alice",
        "/g Bob",          // alias
        "/add 10.5 31.5",
        "/upper hello world",
        "/upper hello | /greet",  // pipeline
        "plain text input",       // default handler
        "//set name=Rust",
        "/greet ${name}",          // variable expansion
    ];

    for input in &inputs {
        let result = parser.execute(input, ctx.clone()).await;
        let output = match &result.output {
            Some(o) => o.to_string(),
            None => format!("<{:?}>", result.status),
        };
        let status = if result.ok() { "✓" } else { "✗" };
        println!("{} > {}", status, input);
        println!("  → {}\n", output);
    }

    println!("All done!");
}
