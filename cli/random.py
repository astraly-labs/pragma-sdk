import argparse
import asyncio

from .verify_random import verify_random


def main():
    parser = argparse.ArgumentParser(description="Pragma CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Define the 'random' subparser
    random_parser = subparsers.add_parser("random")
    random_subparsers = random_parser.add_subparsers(dest="random_command")

    # Define the 'verify-random' subcommand
    verify_random_parser = random_subparsers.add_parser("verify-random")
    verify_random_parser.add_argument(
        "transaction_hash", type=str, help="Transaction hash"
    )
    verify_random_parser.add_argument(
        "--network",
        type=str,
        default="mainnet",
        help="Network name (default:  mainnet))",
    )

    args = parser.parse_args()

    if args.command == "random" and args.random_command == "verify-random":
        asyncio.run(verify_random(args.transaction_hash, args.network))


if __name__ == "__main__":
    main()
