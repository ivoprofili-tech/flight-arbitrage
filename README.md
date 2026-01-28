# Flight Arbitrage

A Python tool for finding flight arbitrage deals by comparing prices across different booking sources.

## What is Flight Arbitrage?

Flight arbitrage involves finding price differences for the same flight across different booking platforms or currencies. This tool helps you discover these opportunities to save money on air travel.

## Project Structure

```
flight-arbitrage/
├── src/
│   ├── scraper/           # Web scraping modules for flight data
│   │   └── google_flights.py  # Google Flights scraper
│   └── arbitrage/         # Price comparison and deal detection
├── app/                   # Streamlit web application
├── scripts/
│   ├── setup_cloud.sh     # Cloud VM setup script
│   └── run_search.py      # Command-line search script
├── requirements.txt       # Python dependencies
└── README.md
```

## Quick Start (Local)

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/flight-arbitrage.git
   cd flight-arbitrage
   ```

2. Create a virtual environment (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install Playwright browsers:
   ```bash
   playwright install chromium
   ```

5. Run a test search:
   ```bash
   python scripts/run_search.py "New York" "Los Angeles" 2025-03-01
   ```

## Cloud Deployment

Running the scraper on a cloud VM allows it to run 24/7 without keeping your computer on.

### Recommended Cloud Providers (Free Tiers Available)

| Provider | Free Tier | Best For |
|----------|-----------|----------|
| **Google Cloud** | $300 credit for 90 days | Beginners, great docs |
| **AWS** | 750 hours/month for 12 months | Most popular, lots of tutorials |
| **DigitalOcean** | $200 credit for 60 days | Simple, developer-friendly |
| **Oracle Cloud** | Always free tier (2 VMs) | Truly free forever |

### Setting Up a Cloud VM

1. **Create a VM** on your chosen provider:
   - OS: Ubuntu 22.04 or 24.04 LTS
   - Size: 1 vCPU, 1GB RAM minimum (2GB recommended)
   - Storage: 20GB

2. **Connect to your VM** via SSH:
   ```bash
   ssh username@your-vm-ip-address
   ```

3. **Clone and set up the project**:
   ```bash
   git clone https://github.com/yourusername/flight-arbitrage.git
   cd flight-arbitrage
   bash scripts/setup_cloud.sh
   ```

4. **Run a search**:
   ```bash
   source venv/bin/activate
   python scripts/run_search.py "New York" "London" 2025-04-01 2025-04-08
   ```

### Automating Searches (Cron Jobs)

To run searches automatically, use cron:

```bash
# Edit crontab
crontab -e

# Add a job to search every day at 9 AM
0 9 * * * cd /home/user/flight-arbitrage && /home/user/flight-arbitrage/venv/bin/python scripts/run_search.py "New York" "Los Angeles" 2025-03-01 >> /var/log/flights.log 2>&1
```

## Usage Examples

### Command Line

```bash
# One-way flight
python scripts/run_search.py "Miami" "Chicago" 2025-03-15

# Round trip
python scripts/run_search.py "Boston" "San Francisco" 2025-04-01 2025-04-08
```

### In Python Code

```python
import asyncio
from src.scraper import search_google_flights, save_results_to_file

async def find_flights():
    flights = await search_google_flights(
        origin="New York",
        destination="Paris",
        departure_date="2025-06-01",
        return_date="2025-06-15",
        headless=True  # Set False to watch the browser
    )

    # Save results to file
    save_results_to_file(
        flights, "New York", "Paris",
        "2025-06-01", "2025-06-15"
    )

    return flights

# Run the search
flights = asyncio.run(find_flights())
```

## Output Format

Results are saved to text files like `flights_New_York_to_Paris_20250301_143022.txt`:

```
============================================================
FLIGHT SEARCH RESULTS
============================================================

Search performed: 2025-03-01 14:30:22
Route: New York → Paris
Departure: 2025-06-01
Return: 2025-06-15

------------------------------------------------------------
Found 5 flight(s)
------------------------------------------------------------

FLIGHT 1
------------------------------
  Price: $487
  Departure Time: 6:00 PM
  Arrival Time: 7:30 AM+1
  Duration: 7h 30m
  Stops: Nonstop
  Airline: Air France
```

## Dependencies

- **playwright** - Browser automation for web scraping
- **streamlit** - Web application framework (for future UI)
- **pandas** - Data manipulation and analysis

## Troubleshooting

### "Browser not found" error
```bash
python -m playwright install chromium
```

### "Missing dependencies" on Linux
```bash
playwright install-deps chromium
```

### Network errors on cloud VM
Make sure your VM's firewall allows outbound HTTPS (port 443).

## License

MIT
