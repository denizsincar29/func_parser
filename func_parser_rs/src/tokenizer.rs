//! Tokenizer for func_parser_rs.

/// All token types.
#[derive(Debug, Clone, PartialEq)]
pub enum TokenType {
    Command,
    Arg,
    Pipe,
    And,
    Or,
    RedirectOut,
    RedirectAppend,
    RedirectClipboard,
    SetVar,
    Execute,
    Comment,
    Eof,
}

/// A single token.
#[derive(Debug, Clone)]
pub struct Token {
    pub kind: TokenType,
    pub value: String,
    pub pos: usize,
}

impl Token {
    pub fn new(kind: TokenType, value: impl Into<String>, pos: usize) -> Self {
        Self { kind, value: value.into(), pos }
    }
}

/// Converts a raw input string into a list of `Token` objects.
pub struct Tokenizer;

impl Tokenizer {
    pub fn new() -> Self {
        Self
    }

    pub fn tokenize(&self, text: &str) -> Vec<Token> {
        let mut tokens = Vec::new();
        let chars: Vec<char> = text.chars().collect();
        let length = chars.len();
        let mut i = 0;

        while i < length {
            // Skip whitespace
            if chars[i].is_whitespace() {
                i += 1;
                continue;
            }

            // Comment
            if chars[i] == '#' {
                tokens.push(Token::new(TokenType::Comment, &text[i..], i));
                break;
            }

            // Check for >> (before >)
            if i + 1 < length && chars[i] == '>' && chars[i + 1] == '>' {
                // Look for "clipboard" after >>
                let rest_start = i + 2;
                let rest = text[rest_start..].trim_start();
                if rest.starts_with("clipboard") {
                    tokens.push(Token::new(TokenType::RedirectClipboard, ">>clipboard", i));
                    i = rest_start + (text[rest_start..].len() - rest.len()) + "clipboard".len();
                } else {
                    tokens.push(Token::new(TokenType::RedirectAppend, ">>", i));
                    i += 2;
                }
                continue;
            }

            // Check for >
            if chars[i] == '>' {
                let rest_start = i + 1;
                let rest = text[rest_start..].trim_start();
                if rest.starts_with("clipboard") {
                    tokens.push(Token::new(TokenType::RedirectClipboard, ">clipboard", i));
                    i = rest_start + (text[rest_start..].len() - rest.len()) + "clipboard".len();
                } else {
                    tokens.push(Token::new(TokenType::RedirectOut, ">", i));
                    i += 1;
                }
                continue;
            }

            // || (before |)
            if i + 1 < length && chars[i] == '|' && chars[i + 1] == '|' {
                tokens.push(Token::new(TokenType::Or, "||", i));
                i += 2;
                continue;
            }

            // &&
            if i + 1 < length && chars[i] == '&' && chars[i + 1] == '&' {
                tokens.push(Token::new(TokenType::And, "&&", i));
                i += 2;
                continue;
            }

            // |
            if chars[i] == '|' {
                tokens.push(Token::new(TokenType::Pipe, "|", i));
                i += 1;
                continue;
            }

            // Quoted string
            if chars[i] == '"' || chars[i] == '\'' {
                let (value, new_i) = self.read_quoted(&chars, i);
                tokens.push(Token::new(TokenType::Arg, value, i));
                i = new_i;
                continue;
            }

            // {file.txt} injection
            if chars[i] == '{' {
                if let Some(end) = text[i..].find('}') {
                    let value = &text[i..i + end + 1];
                    tokens.push(Token::new(TokenType::Arg, value, i));
                    i += end + 1;
                    continue;
                }
            }

            // Word token
            let (word, new_i) = self.read_word(&chars, i);
            let kind = self.classify_word(&word, &tokens);
            tokens.push(Token::new(kind, word, i));
            i = new_i;
        }

        tokens.push(Token::new(TokenType::Eof, "", length));
        tokens
    }

    fn read_quoted(&self, chars: &[char], start: usize) -> (String, usize) {
        let quote = chars[start];
        let mut i = start + 1;
        let mut buf = String::new();
        while i < chars.len() {
            let ch = chars[i];
            if ch == '\\' && i + 1 < chars.len() {
                let next = chars[i + 1];
                let escaped = match next {
                    'n' => '\n',
                    't' => '\t',
                    'r' => '\r',
                    '\\' => '\\',
                    c if c == quote => quote,
                    c => c,
                };
                buf.push(escaped);
                i += 2;
            } else if ch == quote {
                i += 1;
                break;
            } else {
                buf.push(ch);
                i += 1;
            }
        }
        (buf, i)
    }

    fn read_word(&self, chars: &[char], start: usize) -> (String, usize) {
        let mut i = start;
        while i < chars.len() {
            let ch = chars[i];
            if ch.is_whitespace() {
                break;
            }
            if matches!(ch, '|' | '&' | '>' | '#') {
                if i == start {
                    i += 1;
                }
                break;
            }
            i += 1;
        }
        let word: String = chars[start..i].iter().collect();
        (word, i)
    }

    fn classify_word(&self, word: &str, preceding: &[Token]) -> TokenType {
        let low = word.to_lowercase();
        if low == "//set" || low == "//setenv" {
            return TokenType::SetVar;
        }
        if low == "/execute" {
            return TokenType::Execute;
        }
        let meaningful: Vec<&Token> = preceding
            .iter()
            .filter(|t| !matches!(t.kind, TokenType::Eof | TokenType::Comment))
            .collect();

        if meaningful.is_empty() {
            // Only classify as Command if the word starts with '/'
            if word.starts_with('/') {
                return TokenType::Command;
            }
            return TokenType::Arg;
        }

        if let Some(last) = meaningful.last() {
            if matches!(last.kind, TokenType::Pipe | TokenType::And | TokenType::Or) {
                return TokenType::Command;
            }
        }
        TokenType::Arg
    }
}

impl Default for Tokenizer {
    fn default() -> Self {
        Self::new()
    }
}
