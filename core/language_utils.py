"""
Language Utilities - Nhận diện ngôn ngữ cho syntax highlighting

Port từ: /home/hao/Desktop/labs/pastemax/src/utils/languageUtils.ts

Module này cung cấp khả năng nhận diện ngôn ngữ lập trình toàn diện
dựa trên tên file và extension, tối ưu hóa cho LLM code blocks.
"""

from typing import Dict

# Files không có extension và ngôn ngữ tương ứng
NO_EXTENSION_MAP: Dict[str, str] = {
    # Common no-extension files
    "Dockerfile": "dockerfile",
    "Makefile": "makefile",
    "makefile": "makefile",
    "Jenkinsfile": "groovy",
    "README": "markdown",
    "LICENSE": "text",
    "CODEOWNERS": "text",
    "CONTRIBUTING": "markdown",
    # Hidden configuration files
    ".gitignore": "gitignore",
    ".gitattributes": "gitattributes",
    ".gitmodules": "gitconfig",
    ".env": "shell",
    ".npmrc": "ini",
    ".yarnrc": "yaml",
    ".editorconfig": "ini",
    ".prettierrc": "json",
    ".eslintrc": "json",
    ".babelrc": "json",
    ".dockerignore": "gitignore",
    ".htaccess": "apacheconf",
    ".flowconfig": "ini",
}

# Compound extensions (extensions kép) và ngôn ngữ tương ứng
# Quan trọng cho các file config có nhiều phần extension
COMPOUND_EXT_MAP: Dict[str, str] = {
    # ESLint configurations
    ".eslintrc.js": "javascript",
    ".eslintrc.cjs": "javascript",
    ".eslintrc.mjs": "javascript",
    ".eslintrc.json": "json",
    ".eslintrc.yml": "yaml",
    ".eslintrc.yaml": "yaml",
    # Babel configurations
    ".babelrc.js": "javascript",
    ".babelrc.cjs": "javascript",
    ".babelrc.json": "json",
    # TypeScript configurations
    ".tsconfig.json": "json",
    "tsconfig.json": "json",
    "tsconfig.app.json": "json",
    "tsconfig.spec.json": "json",
    # Prettier configurations
    ".prettierrc.js": "javascript",
    ".prettierrc.cjs": "javascript",
    ".prettierrc.json": "json",
    ".prettierrc.yml": "yaml",
    ".prettierrc.yaml": "yaml",
    # Jest configurations
    "jest.config.js": "javascript",
    "jest.config.ts": "typescript",
    "jest.config.json": "json",
    # TypeScript declaration files
    ".d.ts": "typescript",
    # Test files
    ".test.js": "javascript",
    ".test.jsx": "jsx",
    ".test.ts": "typescript",
    ".test.tsx": "tsx",
    ".spec.js": "javascript",
    ".spec.jsx": "jsx",
    ".spec.ts": "typescript",
    ".spec.tsx": "tsx",
    ".e2e.js": "javascript",
    ".e2e.ts": "typescript",
    # Configuration files
    ".config.js": "javascript",
    ".config.ts": "typescript",
    # CSS Modules
    ".module.css": "css",
    ".module.scss": "scss",
    ".module.sass": "sass",
    ".module.less": "less",
    # React Native
    ".native.js": "javascript",
    ".ios.js": "javascript",
    ".android.js": "javascript",
    ".native.jsx": "jsx",
    ".ios.jsx": "jsx",
    ".android.jsx": "jsx",
    ".native.ts": "typescript",
    ".ios.ts": "typescript",
    ".android.ts": "typescript",
    ".native.tsx": "tsx",
    ".ios.tsx": "tsx",
    ".android.tsx": "tsx",
    # Webpack configs
    "webpack.config.js": "javascript",
    "webpack.config.ts": "typescript",
    "webpack.dev.js": "javascript",
    "webpack.prod.js": "javascript",
    "webpack.common.js": "javascript",
    # Rollup configs
    "rollup.config.js": "javascript",
    "rollup.config.ts": "typescript",
    # Next.js
    "next.config.js": "javascript",
    "next.config.mjs": "javascript",
    # Vite configs
    "vite.config.js": "javascript",
    "vite.config.ts": "typescript",
    # Astro configs
    "astro.config.mjs": "javascript",
    "astro.config.js": "javascript",
    "astro.config.ts": "typescript",
    # Svelte configs
    "svelte.config.js": "javascript",
    "svelte.config.cjs": "javascript",
    # Nuxt configs
    "nuxt.config.js": "javascript",
    "nuxt.config.ts": "typescript",
    # Tailwind CSS
    "tailwind.config.js": "javascript",
    "tailwind.config.cjs": "javascript",
    "tailwind.config.ts": "typescript",
    # PostCSS
    "postcss.config.js": "javascript",
    "postcss.config.cjs": "javascript",
}

# Extension map - Bản đồ extension đầy đủ nhất
EXTENSION_MAP: Dict[str, str] = {
    # Web Technologies
    "html": "html",
    "htm": "html",
    "xhtml": "html",
    "shtml": "html",
    "css": "css",
    "pcss": "css",  # PostCSS
    "scss": "scss",
    "sass": "sass",
    "less": "less",
    "styl": "stylus",
    "js": "javascript",
    "jsx": "jsx",
    "mjs": "javascript",  # ES modules
    "cjs": "javascript",  # CommonJS modules
    "ts": "typescript",
    "tsx": "tsx",
    "cts": "typescript",  # CommonJS TypeScript
    "mts": "typescript",  # ES Module TypeScript
    "json": "json",
    "jsonc": "jsonc",  # JSON with comments
    "json5": "json5",
    "webmanifest": "json",
    "wasm": "wasm",
    # Template Languages
    "pug": "pug",
    "jade": "pug",
    "ejs": "ejs",
    "hbs": "handlebars",
    "handlebars": "handlebars",
    "mustache": "mustache",
    "twig": "twig",
    "liquid": "liquid",
    "njk": "nunjucks",
    "haml": "haml",
    "slim": "slim",
    # Modern Web Frameworks
    "vue": "vue",
    "svelte": "svelte",
    "astro": "astro",
    "mdx": "mdx",
    "cshtml": "razor",
    "razor": "razor",
    "graphql": "graphql",
    "gql": "graphql",
    "apollo": "graphql",
    # Documentation
    "md": "markdown",
    "markdown": "markdown",
    "txt": "text",
    "text": "text",
    "rst": "restructuredtext",
    "rest": "restructuredtext",
    "adoc": "asciidoc",
    "asciidoc": "asciidoc",
    "tex": "latex",
    "latex": "latex",
    "wiki": "wiki",
    "org": "org",
    # Configuration
    "yaml": "yaml",
    "yml": "yaml",
    "toml": "toml",
    "ini": "ini",
    "cfg": "ini",
    "conf": "ini",
    "config": "ini",
    "properties": "properties",
    "prop": "properties",
    "env": "shell",
    "dotenv": "shell",
    "editorconfig": "ini",
    "gitignore": "gitignore",
    "gitattributes": "gitattributes",
    "gitconfig": "gitconfig",
    "dockerignore": "gitignore",
    "htaccess": "apacheconf",
    "nginx": "nginx",
    "xml": "xml",
    "plist": "xml",
    "svg": "svg",
    "ant": "xml",
    "dtd": "xml",
    "xsd": "xml",
    "xsl": "xsl",
    "xslt": "xsl",
    "wsdl": "xml",
    "xliff": "xml",
    "xaml": "xml",
    # Scripts and Shell
    "sh": "shell",
    "bash": "bash",
    "zsh": "shell",
    "fish": "shell",
    "ksh": "shell",
    "csh": "shell",
    "tcsh": "shell",
    "bat": "batch",
    "cmd": "batch",
    "ps1": "powershell",
    "psm1": "powershell",
    "psd1": "powershell",
    "ps1xml": "powershell",
    # Programming Languages - Scripting
    "py": "python",
    "pyi": "python",  # Python interface files
    "pyc": "python",
    "pyd": "python",
    "pyw": "python",
    "pyx": "cython",
    "pxd": "cython",
    "ipynb": "jupyter",  # Jupyter notebook
    "rb": "ruby",
    "erb": "erb",  # Ruby templating
    "gemspec": "ruby",
    "rake": "ruby",
    "php": "php",
    "php4": "php",
    "php5": "php",
    "php7": "php",
    "php8": "php",
    "phps": "php",
    "phpt": "php",
    "phtml": "php",
    "pl": "perl",
    "pm": "perl",
    "t": "perl",
    "pod": "perl",
    "lua": "lua",
    "r": "r",
    "rmd": "rmarkdown",
    "swift": "swift",
    "tcl": "tcl",
    "tk": "tcl",
    "exp": "tcl",
    # Programming Languages - JVM
    "java": "java",
    "jsp": "jsp",
    "jspx": "jsp",
    "groovy": "groovy",
    "gvy": "groovy",
    "gy": "groovy",
    "gsh": "groovy",
    "gradle": "gradle",
    "kt": "kotlin",
    "kts": "kotlin",
    "ktm": "kotlin",
    "scala": "scala",
    "sc": "scala",
    "clj": "clojure",
    "cljs": "clojure",
    "cljc": "clojure",
    "edn": "clojure",
    # Programming Languages - C-family
    "c": "c",
    "h": "c",
    "i": "c",
    "cpp": "cpp",
    "cc": "cpp",
    "cxx": "cpp",
    "c++": "cpp",
    "hpp": "cpp",
    "hh": "cpp",
    "hxx": "cpp",
    "h++": "cpp",
    "ii": "cpp",
    "ino": "cpp",  # Arduino
    "cs": "csharp",
    "csx": "csharp",
    "cake": "csharp",
    "fs": "fsharp",
    "fsi": "fsharp",
    "fsx": "fsharp",
    "fsproj": "xml",
    "vb": "vb",
    "vbs": "vb",
    "vba": "vb",
    "bas": "vb",
    "frm": "vb",
    "cls": "vb",
    "m": "objectivec",  # Objective-C or Matlab
    "mm": "objectivec",
    # Programming Languages - Others
    "go": "go",
    "rs": "rust",
    "dart": "dart",
    "ex": "elixir",
    "exs": "elixir",
    "erl": "erlang",
    "hrl": "erlang",
    "hs": "haskell",
    "lhs": "haskell",
    "cabal": "haskell",
    "agda": "agda",
    "elm": "elm",
    "lisp": "lisp",
    "scm": "scheme",
    "ss": "scheme",
    "rkt": "racket",
    "ml": "ocaml",
    "mli": "ocaml",
    # Game Development
    "gd": "gdscript",  # Godot
    "unity": "yaml",  # Unity metadata
    "prefab": "yaml",  # Unity prefab
    "mat": "yaml",  # Unity material
    "anim": "yaml",  # Unity animation
    # Infrastructure & DevOps
    "tf": "terraform",
    "tfvars": "terraform",
    "hcl": "hcl",
    "workflow": "yaml",  # GitHub Actions
    "jenkinsfile": "groovy",
    "dockerfile": "dockerfile",
    "vagrantfile": "ruby",
    "proto": "protobuf",
    "bicep": "bicep",  # Azure Bicep
    "nomad": "hcl",
    # Data Formats
    "csv": "csv",
    "tsv": "tsv",
    "sql": "sql",
    "mysql": "sql",
    "pgsql": "sql",
    "sqlite": "sql",
    "prisma": "prisma",
    "graphqls": "graphql",
    # Build configuration
    "makefile": "makefile",
    "mk": "makefile",
    "mak": "makefile",
    "cmake": "cmake",
    # Mobile Development
    "xcodeproj": "json",
    "pbxproj": "json",
    "storyboard": "xml",
    "xib": "xml",
    # Others
    "diff": "diff",
    "patch": "diff",
}

# LLM-compatible language identifiers
# Chuẩn hóa tên ngôn ngữ để LLM hiểu tốt nhất
LLM_LANGUAGE_MAP: Dict[str, str] = {
    # Standardized names
    "javascript": "javascript",
    "typescript": "typescript",
    "jsx": "jsx",
    "tsx": "tsx",
    "json": "json",
    "css": "css",
    "html": "html",
    "markdown": "markdown",
    "python": "python",
    "ruby": "ruby",
    "go": "go",
    "rust": "rust",
    "java": "java",
    "c": "c",
    "cpp": "cpp",
    "csharp": "csharp",
    "shell": "shell",
    "bash": "bash",
    "sql": "sql",
    "yaml": "yaml",
    "dockerfile": "dockerfile",
    # Aliases and normalizations
    "yml": "yaml",
    "sh": "shell",
    "js": "javascript",
    "ts": "typescript",
    "md": "markdown",
    "py": "python",
    "rb": "ruby",
    "rs": "rust",
    "cs": "csharp",
    "c++": "cpp",
    "makefile": "makefile",
    "plaintext": "text",
}


def get_llm_compatible_language(language: str) -> str:
    """
    Chuyển đổi ngôn ngữ sang định dạng tương thích với LLM.

    Args:
        language: Tên ngôn ngữ gốc

    Returns:
        Tên ngôn ngữ chuẩn hóa cho LLM
    """
    return LLM_LANGUAGE_MAP.get(language.lower(), language)


def get_language_from_filename(filename: str) -> str:
    """
    Xác định ngôn ngữ lập trình dựa trên tên file.

    Xử lý các trường hợp:
    - Files không có extension (Dockerfile, Makefile, ...)
    - Files có extension kép (.test.tsx, .config.js, ...)
    - Extension thông thường

    Args:
        filename: Tên file (không cần đường dẫn đầy đủ)

    Returns:
        Ngôn ngữ tối ưu cho LLM code blocks
    """
    # Normalize filename to lowercase for matching
    lowercase_filename = filename.lower()

    # 1. Handle files with no extension
    if "." not in lowercase_filename:
        language = NO_EXTENSION_MAP.get(filename, "text")
        return get_llm_compatible_language(language)

    # 2. Try exact filename match for config files
    if lowercase_filename in COMPOUND_EXT_MAP:
        return get_llm_compatible_language(COMPOUND_EXT_MAP[lowercase_filename])

    # 3. Check compound extensions (case-insensitive)
    for ext, lang in COMPOUND_EXT_MAP.items():
        if lowercase_filename.endswith(ext.lower()):
            return get_llm_compatible_language(lang)

    # 4. Use last extension as fallback
    extension = (
        lowercase_filename.rsplit(".", 1)[-1] if "." in lowercase_filename else ""
    )

    # Get language from extension map
    language = EXTENSION_MAP.get(extension, extension or "text")

    return get_llm_compatible_language(language)


def get_language_from_path(file_path: str) -> str:
    """
    Xác định ngôn ngữ từ đường dẫn file đầy đủ.

    Args:
        file_path: Đường dẫn file (có thể là tuyệt đối hoặc tương đối)

    Returns:
        Ngôn ngữ tối ưu cho LLM code blocks
    """
    # Extract filename from path
    filename = file_path.replace("\\", "/").rsplit("/", 1)[-1]
    return get_language_from_filename(filename)
