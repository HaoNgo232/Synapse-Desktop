"""
File Patterns Constants
Chua cac constants lien quan den file extensions va ignore patterns.
"""

# Danh sach binary extensions
BINARY_EXTENSIONS = {
    # Images
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tiff",
    ".tif",
    ".webp",
    ".svg",
    ".ico",
    ".heic",
    ".heif",
    ".avif",
    ".psd",
    ".icns",
    ".raw",
    ".cr2",
    ".nef",
    ".dng",
    ".arw",
    # Videos
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".wmv",
    ".flv",
    ".webm",
    ".m4v",
    ".3gp",
    ".ogv",
    ".mpg",
    ".mpeg",
    # Audio
    ".mp3",
    ".wav",
    ".flac",
    ".aac",
    ".ogg",
    ".wma",
    ".m4a",
    ".opus",
    ".oga",
    ".mid",
    ".midi",
    # Archives
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".lzma",
    ".cab",
    ".dmg",
    ".iso",
    ".asar",
    ".tgz",
    ".tbz2",
    ".txz",
    # Executables
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".app",
    ".deb",
    ".rpm",
    ".msi",
    ".pkg",
    ".apk",
    ".ipa",
    # Documents
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".odt",
    ".ods",
    ".odp",
    ".pages",
    ".numbers",
    ".key",
    # Fonts
    ".ttf",
    ".otf",
    ".woff",
    ".woff2",
    ".eot",
    ".cmap",
    # Database
    ".db",
    ".sqlite",
    ".sqlite3",
    ".mdb",
    ".accdb",
    # Flash/Multimedia
    ".swf",
    ".fla",
    # Other binary
    ".bin",
    ".dat",
    ".class",
    ".pyc",
    ".pyo",
    ".o",
    ".obj",
    ".a",
    ".lib",
    ".node",
    ".wasm",
    # 3D Models
    ".obj",
    ".fbx",
    ".blend",
    ".3ds",
    ".stl",
    # CAD
    ".dwg",
    ".dxf",
}

# Directory Quick Skip - dùng với os.walk để PRUNE directory TRƯỚC KHI enter
# Key: os.walk prune in-place nên sẽ KHÔNG traverse vào các folders này
# Bao gồm tất cả ngôn ngữ/framework phổ biến
DIRECTORY_QUICK_SKIP: frozenset[str] = frozenset({
    # === VCS ===
    ".git", ".hg", ".svn",
    # === JavaScript / Node.js ===
    "node_modules", "bower_components", "jspm_packages",
    ".next", ".nuxt", ".vuepress",
    ".npm", ".yarn", ".pnpm-store",
    ".serverless", ".fusebox", ".dynamodb",
    ".parcel-cache", ".cache", ".rollup.cache",
    ".webpack.cache", ".turbo",
    # === Python ===
    "__pycache__", ".venv", "venv", "env",
    ".tox", ".nox", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".pytype", ".ipynb_checkpoints",
    "*.egg-info",  # os.walk sẽ match exact name
    ".eggs", "site-packages",
    # === Rust ===
    "target",  # Cargo build output
    # === Java / Kotlin / Scala ===
    ".gradle", ".mvn", ".idea",
    ".settings", "bin",  # Eclipse
    # === Go ===
    "vendor",  # Go vendor
    # === Ruby ===
    ".bundle",
    # === PHP ===
    # vendor đã có ở Go section
    # === .NET / C# ===
    "obj", "packages",
    # === Dart / Flutter ===
    ".dart_tool", ".pub-cache",
    # === Swift / iOS ===
    ".build", "Pods", "DerivedData",
    # === Build outputs (chung) ===
    "dist", "build", "out", "output",
    "coverage", "lib-cov", ".nyc_output",
    # === IDE / Editor ===
    ".vscode", ".idea", ".vs",
    # === OS generated ===
    ".DS_Store", "Thumbs.db",
    # === Misc caches ===
    ".sass-cache", ".eslintcache",
    "tmp", "temp", ".tmp",
})

# Extended Ignore Patterns - Port tu Repomix (src/config/defaultIgnore.ts)
# Danh sach patterns mac dinh de ignore khi scan directory
# Ho tro nhieu ngon ngu/framework: Python, Node, Rust, Go, PHP, Ruby, etc.
EXTENDED_IGNORE_PATTERNS = [
    # Dependencies directories
    "**/node_modules/**",
    "**/bower_components/**",
    "**/jspm_packages/**",
    "vendor/**",
    "**/.bundle/**",
    "**/.gradle/**",
    "target/**",
    # Logs
    "logs/**",
    "**/*.log",
    "**/npm-debug.log*",
    "**/yarn-debug.log*",
    "**/yarn-error.log*",
    # Runtime data
    "pids/**",
    "*.pid",
    "*.seed",
    "*.pid.lock",
    # Coverage directories
    "lib-cov/**",
    "coverage/**",
    ".nyc_output/**",
    # Build tool caches
    ".grunt/**",
    ".lock-wscript",
    "build/Release/**",
    "typings/**",
    "**/.npm/**",
    # Cache directories
    ".eslintcache",
    ".rollup.cache/**",
    ".webpack.cache/**",
    ".parcel-cache/**",
    ".sass-cache/**",
    "*.cache",
    # REPL history
    ".node_repl_history",
    # npm pack output
    "*.tgz",
    # Yarn
    "**/.yarn/**",
    "**/.yarn-integrity",
    # Environment files
    ".env",
    # JS Frameworks build outputs
    ".next/**",
    ".nuxt/**",
    ".vuepress/dist/**",
    ".serverless/**",
    ".fusebox/**",
    ".dynamodb/**",
    # Build outputs
    "dist/**",
    "build/**",
    "out/**",
    # OS generated files
    "**/.DS_Store",
    "**/Thumbs.db",
    # Editor/IDE directories
    ".idea/**",
    ".vscode/**",
    "**/*.swp",
    "**/*.swo",
    "**/*.swn",
    "**/*.bak",
    # Temporary files
    "tmp/**",
    "temp/**",
    # Node.js lock files
    "**/package-lock.json",
    "**/yarn.lock",
    "**/pnpm-lock.yaml",
    "**/bun.lockb",
    "**/bun.lock",
    # Python-related
    "**/__pycache__/**",
    "**/*.py[cod]",
    "**/venv/**",
    "**/.venv/**",
    "**/.pytest_cache/**",
    "**/.mypy_cache/**",
    "**/.ipynb_checkpoints/**",
    "**/Pipfile.lock",
    "**/poetry.lock",
    "**/uv.lock",
    # Rust-related
    "**/Cargo.lock",
    "**/Cargo.toml.orig",
    "**/target/**",
    "**/*.rs.bk",
    # PHP-related
    "**/composer.lock",
    # Ruby-related
    "**/Gemfile.lock",
    # Go-related
    "**/go.sum",
    # Elixir-related
    "**/mix.lock",
    # Haskell-related
    "**/stack.yaml.lock",
    "**/cabal.project.freeze",
    # Repomix/Synapse output files
    "**/repomix-output.*",
    "**/repopack-output.*",
    "**/synapse-output.*",
]
