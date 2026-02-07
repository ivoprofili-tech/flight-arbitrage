# CLAUDE.md

## Project Overview

**flight-arbitrage** is a Python-based flight price arbitrage system that finds the cheapest flights by combining multiple search strategies:

1. **Direct search** - Standard flight price comparison via Google Flights
2. **Skiplagged deals** - Discounted fares identified by Skiplagged.com
3. **Hidden-city ticketing** (skiplagging) - Booking A→C flights but exiting at layover B when that's cheaper than A→B direct
4. **Geo-arbitrage** - Comparing prices from different countries/points-of-sale, exploiting regional pricing differences

The project targets a specific use case: finding cheap flights from **Brazil to the US** (primarily GRU→MCO, São Paulo to Orlando), but supports arbitrary routes.

- **Repository**: ivoprofili-tech/flight-arbitrage
- **Created**: January 2026
- **Language**: Python 3 (asyncio-based)
- **Key tech**: Playwright (browser automation), SerpApi (Google Flights API), SQLite

## Repository Structure

```
flight-arbitrage/
├── src/
│   ├── models/
│   │   └── flight.py              # FlightResult dataclass, normalization, dedup
│   ├── scraper/
│   │   ├── google_flights.py      # Playwright-based Google Flights scraper
│   │   ├── google_flights_serpapi.py  # SerpApi-based Google Flights (fast, preferred)
│   │   └── skiplagged.py          # Skiplagged.com browser scraper
│   ├── database/
│   │   └── flights_db.py          # SQLite storage and query layer
│   ├── geo/
│   │   ├── geo_search.py          # Geo-arbitrage search engine
│   │   ├── proxy_config.py        # BrightData/Oxylabs/Smartproxy proxy setup
│   │   └── currency.py            # Exchange rate APIs + price parsing
│   ├── data/
│   │   └── route_database.py      # Hidden-city route mappings (A,B)→[C targets]
│   ├── utils/
│   │   └── layover_detection.py   # Airport/city matching for layover checks
│   ├── orchestrator.py            # Hidden-city deal orchestrator
│   └── parallel_search.py         # Multi-source parallel search engine
├── scripts/
│   ├── run_parallel_search.py     # Main CLI entry point (standard + geo + push)
│   ├── run_search.py              # Google Flights single search
│   ├── run_skiplagged.py          # Skiplagged single search
│   ├── test_skiplag.py            # Skiplag testing/debugging tool
│   ├── query_db.py                # Database query CLI
│   ├── push_results.sh            # Git commit/push automation
│   └── setup_cloud.sh             # Cloud VM deployment (Ubuntu + Playwright)
├── search_results/                # JSON output from searches
├── data/                          # SQLite database storage
├── debug/                         # Debug screenshots, videos, page dumps
├── requirements.txt               # Python dependencies
├── CLAUDE.md                      # This file
└── README.md                      # Project readme
```

## Development Setup

### Prerequisites

- Python 3.10+
- Playwright (`playwright install chromium`)
- SerpApi API key (for fast Google Flights searches)
- Optional: BrightData/Oxylabs proxy credentials (for geo-arbitrage with Playwright)

### Getting Started

```bash
git clone <repository-url>
cd flight-arbitrage
pip install -r requirements.txt
playwright install chromium
export SERPAPI_KEY="your-key-here"
```

### Running Searches

```bash
# Default search: GRU → MCO, 30 days out
python scripts/run_parallel_search.py

# Custom route and date
python scripts/run_parallel_search.py JFK LAX 2026-04-15

# Specific sources only
python scripts/run_parallel_search.py --sources google_flights
python scripts/run_parallel_search.py --sources skiplagged
python scripts/run_parallel_search.py --sources hidden_city

# Show browser window (debug)
python scripts/run_parallel_search.py --visible

# Quick mode (fewer hidden-city routes)
python scripts/run_parallel_search.py --quick

# Hybrid geo-arbitrage (recommended for best deals)
python scripts/run_parallel_search.py --geo
python scripts/run_parallel_search.py --geo --locations BR,US,CO

# Push results to GitHub
python scripts/run_parallel_search.py --geo --push
```

## Architecture

### How It Works

#### Standard Parallel Search

```
User: origin, destination, date
  ├─ Google Flights (SerpApi) ──→ direct flights + prices
  ├─ Skiplagged ────────────────→ deal flights + savings
  └─ Hidden City Orchestrator ──→ for each target C: search A→C, check if B is layover
       │
       ▼
  Normalize → Deduplicate → Filter (hidden city must beat direct price) → Sort by price
       │
       ▼
  Save JSON + Display results
```

#### Hybrid Geo-Arbitrage

```
Phase 1: Full parallel search from one location
  → Discover which hidden-city routes have deals
  → Find best direct price baseline

Phase 2: For each route (direct + discovered hidden-city):
  → Search from each geo location (BR, US, CO, PA, AR)
  → Compare prices in USD
  → Identify best Point of Sale per route
  → Calculate savings
```

### Why Geo-Arbitrage Works

Airlines use dynamic pricing based on browser location and point-of-sale. The same flight can have different prices when searched from different countries. Example:
- GRU→MCO from Brazil: R$1,200 (~$240 USD)
- GRU→MCO from USA: $299 USD
- Savings: $59 (20%)

### Why Hidden-City Ticketing Works

Airlines sometimes price A→C (with B layover) cheaper than A→B direct due to route competition and hub allocation. Example:
- GRU→MCO direct: $350
- GRU→MIA with MCO layover: $250
- Strategy: Book GRU→MIA, exit at MCO, save $100

**Limitations**: One-way only, no checked bags, airlines may penalize repeat offenders.

### Data Sources

| Source | Method | Speed | Best For |
|--------|--------|-------|----------|
| Google Flights (SerpApi) | HTTP API | ~2s/search | Fast direct searches, geo-targeting via `gl` param |
| Google Flights (Playwright) | Browser automation | ~30s/search | Fallback when SerpApi unavailable |
| Skiplagged | Browser automation | ~30s/search | Finding deal fares and skiplagged discounts |

### Database Schema (SQLite)

**`searches`**: search metadata (origin, destination, date, type, timestamp)
**`flights`**: individual flight results linked to searches (airline, times, price, source, geo location, currency, price_usd)

Indexed on: search_id, price_usd, route, location, airline+time.

### Route Database

Two-tier system for hidden-city target selection:

1. **PAIR_ROUTES** `(origin_A, dest_B) → [C targets]` - Origin-aware, most accurate
   - `("JFK", "DEN") → ["LAX", "SFO", "SEA", ...]` (westbound)
   - `("GRU", "MCO") → [30+ US destinations]` (Brazil→Orlando specialty)
2. **ROUTE_DATABASE** `dest_B → [C targets]` - Fallback for any origin

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SERPAPI_KEY` | SerpApi API key for Google Flights | Yes (for SerpApi scraper) |
| `PROXY_PROVIDER` | Proxy service: `brightdata`, `oxylabs`, `smartproxy` | No (for geo w/ Playwright) |
| `PROXY_USERNAME` | Proxy auth username | No |
| `PROXY_PASSWORD` | Proxy auth password | No |
| `PROXY_HOST` | Custom proxy host | No |
| `PROXY_PORT` | Custom proxy port | No |

## Key Dependencies

- **playwright** - Browser automation for Google Flights and Skiplagged
- **aiohttp** - Async HTTP for SerpApi calls and exchange rate APIs
- **sqlite3** - Flight database (built-in)
- **asyncio** - Concurrent search execution
- **streamlit** - Web UI (installed, not yet active)
- **pandas** - Data analysis (installed, not yet active)

## Code Conventions

### General Guidelines

- Keep code simple and focused; avoid over-engineering
- Write clear commit messages that explain the "why"
- Add tests for new functionality
- Validate inputs at system boundaries (user input, external APIs)
- Do not commit secrets, API keys, or credentials

### Python Patterns Used

- **Dataclasses** for data models (`FlightResult`, `GeoFlightResult`)
- **Enums** for type safety (`FlightSource`, `DealType`)
- **asyncio** with `Semaphore` for concurrency control
- **Multiple extraction strategies** with fallbacks (DOM → text → regex)
- **Composite key deduplication** (`airline|dep_time|arr_time|price`)
- **Normalization functions** per source to unified `FlightResult`

### Git Workflow

- Feature branches for development
- Search results and debug artifacts are committed to track experiments
- `--push` flag on CLI auto-commits and pushes results to GitHub
- Auto-sync (`git fetch`/`pull`) before searches to prevent conflicts

## What's Working

- Multi-source parallel search (Google Flights + Skiplagged + Hidden City)
- SerpApi integration for fast Google Flights queries
- Geo-arbitrage across 5 countries (BR, US, CO, PA, AR)
- Currency conversion with API fallback and static rates
- Hidden-city deal detection with multi-strategy layover extraction
- Pair-specific route database (25+ origins, 35+ destinations)
- SQLite database for historical price tracking
- CLI with comprehensive options
- GitHub auto-push for results

## What's Planned / In Progress

- Streamlit web UI for interactive searches
- Advanced analytics and price trend visualization
- Deal notification system (alerts when prices drop)
- Machine learning for price prediction
- Integration with booking systems

## Common Tasks for AI Assistants

When working on this repository:

1. **Before making changes**: Read relevant files first; never modify code you haven't read
2. **Keep it minimal**: Only add what is explicitly requested
3. **Update this file**: When adding new tooling, commands, or architectural decisions, update CLAUDE.md
4. **No unnecessary files**: Don't create documentation or config files unless specifically asked
5. **Security**: Never commit `.env` files or secrets; use `.gitignore` appropriately
6. **Understand the branches**: Most development has happened on feature branches, not `main`. Check the latest branch for current code state
7. **Test searches**: Use `--quick` flag when testing to limit hidden-city route count
8. **Debug artifacts**: Screenshots and videos in `debug/` are useful for diagnosing scraper issues
