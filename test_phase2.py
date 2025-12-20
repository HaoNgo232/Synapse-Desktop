#!/usr/bin/env python
"""Test Phase 2 - Rust and Go support"""

from core.smart_context.parser import smart_parse

print('=== PHASE 2 TESTS ===')
print()

# Test Rust
rust_code = '''
use std::io;

struct User {
    name: String,
    age: u32,
}

impl User {
    fn new(name: String) -> Self {
        User { name, age: 0 }
    }
}

fn main() {
    println!("Hello, world!");
}
'''

result = smart_parse('test.rs', rust_code)
print('=== RUST TEST ===')
print(result if result else 'FAILED - using fallback or no result')
print()

# Test Go
go_code = '''
package main

import "fmt"

type User struct {
    Name string
    Age  int
}

func NewUser(name string) *User {
    return &User{Name: name}
}

func main() {
    fmt.Println("Hello, world!")
}
'''

result = smart_parse('test.go', go_code)
print('=== GO TEST ===')
print(result if result else 'FAILED - using fallback or no result')
print()

# Verify existing languages still work
print('=== REGRESSION TESTS ===')
py_result = smart_parse('test.py', 'class Foo: pass')
print('Python:', 'OK' if py_result else 'FAILED')

js_result = smart_parse('test.js', 'function foo() {}')
print('JavaScript:', 'OK' if js_result else 'FAILED')

ts_result = smart_parse('test.ts', 'interface Foo {}')
print('TypeScript:', 'OK' if ts_result else 'FAILED')

print()
print('=== PHASE 2 TEST COMPLETE ===')
