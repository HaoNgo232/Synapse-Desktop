#!/usr/bin/env python
"""Test Phase 3 - Java, C#, C, C++ support"""

from core.smart_context.parser import smart_parse

print("=== PHASE 3 TESTS ===")
print()

# Test Java
java_code = """
package com.example;

import java.util.List;

public class User {
    private String name;
    
    public User(String name) {
        this.name = name;
    }
    
    public String getName() {
        return name;
    }
}
"""

result = smart_parse("test.java", java_code)
print("=== JAVA TEST ===")
print(result if result else "FAILED")
print()

# Test C#
csharp_code = """
using System;

namespace MyApp
{
    public class User
    {
        public string Name { get; set; }
        
        public void SayHello()
        {
            Console.WriteLine("Hello");
        }
    }
}
"""

result = smart_parse("test.cs", csharp_code)
print("=== C# TEST ===")
print(result if result else "FAILED")
print()

# Test C
c_code = """
#include <stdio.h>

struct User {
    char* name;
    int age;
};

void print_user(struct User* user) {
    printf("%s\\n", user->name);
}

int main() {
    return 0;
}
"""

result = smart_parse("test.c", c_code)
print("=== C TEST ===")
print(result if result else "FAILED")
print()

# Test C++
cpp_code = """
#include <string>

class User {
private:
    std::string name;
    
public:
    User(std::string n) : name(n) {}
    
    std::string getName() {
        return name;
    }
};

int main() {
    return 0;
}
"""

result = smart_parse("test.cpp", cpp_code)
print("=== C++ TEST ===")
print(result if result else "FAILED")
print()

print("=== PHASE 3 TEST COMPLETE ===")
