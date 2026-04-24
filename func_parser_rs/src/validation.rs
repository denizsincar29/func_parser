//! Argument validation for func_parser_rs.

use regex::Regex;
use crate::errors::{FuncParserError, Result};
use crate::models::{ArgDef, ArgValue};

/// Built-in validation presets.
pub fn preset_pattern(name: &str) -> Option<&'static str> {
    match name {
        "email" => Some(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"),
        "url"   => Some(r"^https?://[^\s/$.?#].[^\s]*$"),
        "phone" => Some(r"^\+?[\d\s\-().]{7,20}$"),
        "uuid"  => Some(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"),
        _ => None,
    }
}

/// Coerce a raw string value to an `ArgValue`.
pub fn coerce(raw: &str) -> ArgValue {
    ArgValue::String(raw.to_string())
}

/// Validate an `ArgValue` against an `ArgDef`.
pub fn validate(value: &ArgValue, arg: &ArgDef) -> Result<()> {
    let s = value.to_string();

    // choices
    if let Some(choices) = &arg.choices {
        if !choices.iter().any(|c| c == &s) {
            return Err(FuncParserError::InvalidArg {
                arg: arg.name.clone(),
                reason: format!("must be one of {:?}, got {:?}", choices, s),
            });
        }
    }

    // numeric range
    if arg.min.is_some() || arg.max.is_some() {
        if let Ok(n) = s.parse::<f64>() {
            if let Some(min) = arg.min {
                if n < min {
                    return Err(FuncParserError::InvalidArg {
                        arg: arg.name.clone(),
                        reason: format!("must be >= {}, got {}", min, n),
                    });
                }
            }
            if let Some(max) = arg.max {
                if n > max {
                    return Err(FuncParserError::InvalidArg {
                        arg: arg.name.clone(),
                        reason: format!("must be <= {}, got {}", max, n),
                    });
                }
            }
        }
    }

    // regex / preset
    let pattern = arg.regex.as_deref()
        .or_else(|| arg.preset.as_deref().and_then(preset_pattern));

    if let Some(pat) = pattern {
        let re = Regex::new(pat).map_err(|e| FuncParserError::Other(e.to_string()))?;
        if !re.is_match(&s) {
            let label = arg.preset.as_deref().unwrap_or("regex");
            return Err(FuncParserError::ValidationError {
                arg: arg.name.clone(),
                message: format!("value {:?} does not match {} pattern", s, label),
            });
        }
    }

    Ok(())
}
