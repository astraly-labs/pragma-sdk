# LMAX Connector

A service that connects to LMAX Exchange via FIX 4.4 protocol and pushes EUR/USD price data to the Pragma Oracle.

## Features

- Connects to LMAX Exchange using FIX 4.4 protocol
- Subscribes to EUR/USD market data
- Pushes mid-price to Pragma Oracle
- Graceful shutdown handling
- Configurable via environment variables

## Prerequisites

- Python 3.11 or higher
- uv for dependency management
- LMAX Exchange credentials
- Pragma Oracle API credentials

## Installation

1. Clone the repository
2. Install dependencies:
```bash
uv pip install -e .
```

## Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` and fill in your credentials:
- `LMAX_SENDER_COMP_ID`: Your LMAX FIX sender ID
- `LMAX_TARGET_COMP_ID`: LMAX FIX target ID (usually LMXBLM)
- `LMAX_HOST`: LMAX FIX host (usually fix-md.lmaxtrader.com)
- `LMAX_PORT`: LMAX FIX port (usually 443)
- `PRAGMA_API_KEY`: Your Pragma API key
- `PRAGMA_PUBLISHER_ID`: Your Pragma publisher ID
- `PRAGMA_API_BASE_URL`: Pragma API base url (dev/prod)

## Running the Service

```bash
python -m lmax_connector
```

The service will:
1. Connect to LMAX Exchange via FIX
2. Subscribe to EUR/USD market data
3. Push mid-prices to Pragma Oracle
4. Handle graceful shutdown on SIGTERM/SIGINT

## Development

### Running Tests

```bash
poe test
```

### Code Style

The project uses:
- Ruff for code formatting and linting
- MyPy for type checking

Run all checks:
```bash
poe format  # Format code
poe lint    # Run linter
poe typecheck  # Run type checker
``` 