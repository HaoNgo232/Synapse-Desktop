import argparse
import sys
from .kiro_conv import convert_kiro
from .copilot_conv import convert_copilot
from .kit_sync import update_kit

def main():
    parser = argparse.ArgumentParser(description="Agent Bridge - Multi-format Agent Converter")
    subparsers = parser.add_subparsers(dest="format", help="Target format")

    # Kiro Subcommand
    kiro_parser = subparsers.add_parser("kiro", help="Convert to Kiro format")
    kiro_parser.add_argument("--source", default=".agent", help="Source directory")
    kiro_parser.add_argument("--output", default=".kiro", help="Output directory")

    # Copilot Subcommand
    copilot_parser = subparsers.add_parser("copilot", help="Convert to GitHub Copilot format")
    copilot_parser.add_argument("--source", default=".agent", help="Source directory")
    copilot_parser.add_argument("--output", default=".github/copilot-instructions.md", help="Output file path")

    # Update-kit Subcommand
    update_parser = subparsers.add_parser("update-kit", help="Update agents/skills from the original Antigravity Kit repo")
    update_parser.add_argument("--target", default=".agent", help="Target directory to update")

    args = parser.parse_args()

    if args.format == "kiro":
        convert_kiro(args.source, args.output)
    elif args.format == "copilot":
        convert_copilot(args.source, args.output)
    elif args.format == "update-kit":
        update_kit(args.target)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
