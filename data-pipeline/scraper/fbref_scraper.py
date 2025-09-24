import requests
import time
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import logging
from typing import Dict, List, Optional
import urllib.request
import urllib.error
import urllib.parse
import gzip
import os

class FBRefScraper:
    """
    Scrapes soccer statistics from FBRef and organizes all our functions in one place
    """

    def __init__(self):
        """
        Initialize the scraper when we create a new instance
        """

        # Base URL for FBRef
        self.base_url = "https://fbref.com"

        # Create a session to maintain cookies and connection across requests
        self.session = requests.Session()

        # Minimum delay between requests to avoid being blocked
        self.min_delay = 7.0

        # Track when we made our last request
        self.last_request = None

        # Set up professional headers so FBRef knows we're legit
        self.session.headers.update({
            # Use a standard Chrome browser user agent instead of identifying as a bot
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            # Specify what content types we can accept
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            # Specify what languages we prefer  
            'Accept-Language': 'en-US,en;q=0.9',
            # Specify what compression we can handle
            'Accept-Encoding': 'gzip, deflate, br',
            # Keep the connection alive for efficiency
            'Connection': 'keep-alive',
            # Tell server we want HTTPS when possible
            'Upgrade-Insecure-Requests': '1',
            # Add some additional browser-like headers
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        })

        # Initialize logging for tracking what the scraper is doing
        self._setup_logging()

    def _setup_logging(self):
        """
        Private method to track scraper activity
        """

        # Configure logging system
        logging.basicConfig(
            level=logging.INFO, # Log at INFO level and above
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', # Format of log messages
            handlers=[
                logging.FileHandler('scraper.log', encoding='utf-8'), # Log to a file
                logging.StreamHandler(), # Log to the console
            ],
            force=True # Force reconfiguration of logging
        )

        # Create a logger for this class
        self.logger = logging.getLogger(__name__)

    def _rate_limit(self):
        """
        Private method to enforce delays between requests
        """

        # Check if we made a request recently
        if self.last_request is not None:
            # Calculate time since last request
            elapsed = time.time() - self.last_request

            # Check if we need to wait
            if elapsed < self.min_delay:
                # Calculate how long to wait
                sleep_time = self.min_delay - elapsed
                # Log the wait
                self.logger.info(f"Waiting {sleep_time:.2f} seconds before next request")
                # Wait for the required time
                time.sleep(sleep_time)

        # Update the last request time
        self.last_request = time.time()

    def test_connection_urllib(self, team_id: str, team_name: str, season: str = "2025-2026"):
        """
        Test connection using urllib instead of requests library
        Now with proper gzip decompression handling
        """
        # Build the URL just like before
        url = f"{self.base_url}/en/squads/{team_id}/{season}/c9/{team_name}-Stats-Premier-League"
        
        try:
            # Apply our rate limiting
            self._rate_limit()
            
            # Log what we're attempting
            self.logger.info(f"Testing urllib connection to: {url}")
            
            # Create a request object with headers
            request = urllib.request.Request(url)
            
            # Add all our headers to the request
            request.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            request.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8')
            request.add_header('Accept-Language', 'en-US,en;q=0.9')
            # Don't request gzip encoding to avoid compression issues
            # request.add_header('Accept-Encoding', 'gzip, deflate')  # Comment this out
            request.add_header('Connection', 'keep-alive')
            request.add_header('Upgrade-Insecure-Requests', '1')
            request.add_header('Cache-Control', 'max-age=0')
            
            # Make the actual request with urllib
            with urllib.request.urlopen(request, timeout=30) as response:
                # Read the response content as bytes first
                content_bytes = response.read()
                
                # Check if content is compressed (starts with gzip magic bytes)
                if content_bytes.startswith(b'\x1f\x8b'):
                    # Content is gzip compressed, decompress it
                    import gzip
                    html_content = gzip.decompress(content_bytes).decode('utf-8')
                    self.logger.info("Decompressed gzip content successfully")
                else:
                    # Content is not compressed, decode directly
                    html_content = content_bytes.decode('utf-8')
                    self.logger.info("Content was not compressed")
                
                # Log success information
                self.logger.info(f"urllib success! Status: {response.status}")
                self.logger.info(f"Content length: {len(html_content)} bytes")
                
                # Return success information
                return {
                    'success': True,
                    'url': url,
                    'status_code': response.status,
                    'content_length': len(html_content),
                    'content_preview': html_content[:500]
                }
        
        # Handle different types of urllib errors
        except urllib.error.HTTPError as e:
            # HTTP errors like 403, 404, 500
            self.logger.error(f"urllib HTTPError: {e.code} - {e.reason}")
            return {'success': False, 'error': f'HTTPError: {e.code} - {e.reason}'}
        
        except urllib.error.URLError as e:
            # Network errors like connection timeout
            self.logger.error(f"urllib URLError: {e.reason}")
            return {'success': False, 'error': f'URLError: {e.reason}'}
        
        except UnicodeDecodeError as e:
            # Handle encoding issues
            self.logger.error(f"Encoding error: {e}")
            return {'success': False, 'error': f'Encoding error: {e}'}
        
        except Exception as e:
            # Any other unexpected errors
            self.logger.error(f"urllib unexpected error: {e}")
            return {'success': False, 'error': f'Unexpected: {e}'}

    def discover_team_id(self, team_search_name: str, season: str = "2025-2026"):
        """
        Find a team's FBRef ID by searching the Premier League team page
        """

        try:
            # Apply rate limiting
            self._rate_limit()

            # Try the Premier League stats page to find team links
            standings_url = f"{self.base_url}/en/comps/9/{season}/{season}-Premier-League-Stats"

            # Log what we're attempting
            self.logger.info(f"Searching for team ID for: {team_search_name}")
            self.logger.info(f"Checking standings page: {standings_url}")

            # Make request with urllib
            request = urllib.request.Request(standings_url)
            request.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

            with urllib.request.urlopen(request, timeout=30) as response:
                html_content = response.read().decode('utf-8')

            # Parse with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            # Find all team links on the page
            team_links = soup.find_all('a', href=True)

            # Search through all links for team matches
            for link in team_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)

                # Check if this looks like a team stats page link
                if "/squads/" in href and team_search_name.lower() in text.lower():
                    # Extract the team ID from the URL
                    team_id = href.split('/squads/')[1].split('/')[0]

                    # Log success
                    self.logger.info(f"Found team ID {team_id} for {team_search_name}")
                    
                    # Test if this team ID actually works
                    test_result = self.test_team_id(team_id, text, season)

                    if test_result['success']:
                        return {
                            "success": True,
                            "team_id": team_id,
                            "team_name": text,
                            "fbref_name": self._extract_fbref_name_from_url(href)
                        }
            # If no match found, return failure
            self.logger.warning(f"No team ID found for {team_search_name}")
            return { "success": False, "error": f"No team ID found for {team_search_name}" }
        
        except Exception as e:
            # Handle any other errors
            self.logger.error(f"Unexpected error discovering team ID for {team_search_name}: {e}")
            return { "success": False, "error": str(e) }

    def test_team_id(self, team_id: str, team_name: str, season: str = "2025-2026"):
        """
        Test if a team ID actually works by trying to access the team's stats page
        """

        try:
            # Apply rate limiting
            self._rate_limit()

            # Clean the team name to match FBRef's format
            clean_name = team_name.replace(" ", "-").replace("&", "").replace(".", "")

            # Build the URL
            url = f"{self.base_url}/en/squads/{team_id}/{season}/c9/{clean_name}-Stats-Premier-League"

            # Make request with urllib
            request = urllib.request.Request(url)
            request.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

            with urllib.request.urlopen(request, timeout=30) as response:
                if response.status == 200:
                    self.logger.info(f"Confirmed working team ID: {team_id} for {team_name}")
                    return { "success": True, "url": url }
                else:
                    return { "success": False, "error": f"Got status code {response.status} for {url}" }

        except Exception as e:
            # Handle any other errors
            self.logger.error(f"Unexpected error testing team ID {team_id} for {team_name}: {e}")
            return { "success": False, "error": str(e) }

    def _extract_fbref_name_from_url(self, url: str):
        """
        Extract the FBRef name from a URL
        """

        try:
            # Split by '/' and look for the team name part
            parts = url.split('/')
            for part in parts:
                if "-Stats" in part:
                    return part.replace("-Stats", "")
            # If no match found, return the part after the team ID
            if "squads" in url:
                squad_parts = url.split('/squads/')[1].split('/')
                if len(squad_parts) >= 3:
                    return squad_parts[2].replace("-Stats", "")
        except:
            pass
        return ""

    def discover_all_premier_league_teams(self, season: str = "2025-2026"):
        """
        Discover Premier League teams using only structural patterns, no hardcoded lists
        """
        try:
            # Apply rate limiting
            self._rate_limit()

            # Get the broader Premier League stats page
            stats_url = f"{self.base_url}/en/comps/9/{season}/{season}-Premier-League-Stats"
            
            self.logger.info(f"Discovering Premier League teams from: {stats_url}")

            # Make request with urllib
            request = urllib.request.Request(stats_url)
            request.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

            with urllib.request.urlopen(request, timeout=30) as response:
                html_content = response.read().decode('utf-8')

            # Parse with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            teams = {}

            # Find all squad links
            all_links = soup.find_all('a', href=True)
            
            for link in all_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                # Only process squad links that look valid
                if ('/squads/' in href and text and len(text) > 2):
                    
                    team_id = href.split('/squads/')[1].split('/')[0]
                    
                    # Only process if we have a valid 8-character team ID
                    if len(team_id) == 8:
                        # Skip obvious non-team entries
                        skip_patterns = ['vs ', '(M)', '(F)', 'Stats', 'Squad', 'Table', 'Clubs', '...']
                        if any(pattern in text for pattern in skip_patterns):
                            continue
                        
                        team_key = text.lower().replace(' ', '_').replace('-', '_')
                        
                        # Avoid duplicates
                        if team_key not in teams:
                            teams[team_key] = {
                                "id": team_id,
                                "name": text.replace(' ', '-'),
                                "official_name": text,
                            }
            
            # If we got way too many teams, take the first 20 alphabetically
            if len(teams) > 25:
                self.logger.info(f"Found {len(teams)} teams - filtering to likely Premier League teams")
                # Sort alphabetically and take first 20
                sorted_teams = dict(sorted(teams.items())[:20])
                teams = sorted_teams
            
            # Log what we found
            for team_key, team_data in teams.items():
                self.logger.info(f"Found team: {team_data['official_name']} (ID: {team_data['id']})")
            
            self.logger.info(f"Successfully discovered {len(teams)} teams")
            return {"success": True, "teams": teams}

        except Exception as e:
            self.logger.error(f"Error discovering Premier League teams: {e}")
            return {"success": False, "error": str(e)}

    def scrape_multiple_teams(self, teams: Dict):
        """
        Scrape multiple teams in parallel with progress tracking
        """

        results = {}
        successful_teams = 0
        failed_teams = 0

        # Get all teams
        team_items = list(teams.items())    

        self.logger.info(f"Scraping {len(team_items)} teams in parallel")

        for team_key, team_info in team_items:
            try:
                self.logger.info(f"Scraping {team_info['official_name']}")

                # Scrape the team
                result = self.parse_player_stats(team_info['id'], team_info['name'])

                if result['success']:
                    # Save to CSV
                    save_result = self.save_to_csv(result)

                    if save_result['success']:
                        results[team_key] = {
                            "success": True,
                            "players": result["player_count"],
                            "csv_file": save_result["file_path"],
                        }

                        successful_teams += 1
                        self.logger.info(f" {team_info['official_name']}: {result['player_count']} players saved")
                    else:
                        results[team_key] = { "success": False, "error": save_result["error"] }
                        failed_teams += 1
                else:
                    results[team_key] = { "success": False, "error": result["error"] }
                    failed_teams += 1
            except Exception as e:
                results[team_key] = { "success": False, "error": str(e) }
                failed_teams += 1
        
        return {
            "success": True,
            "total_teams": len(team_items),
            "successful_teams": successful_teams,
            "failed_teams": failed_teams,
            "results": results,
        }
            
    def parse_player_stats(self, team_id: str, team_name: str, season: str = "2025-2026"):
        """
        Extract actual player statistics in a structured format to export to a CSV file
        """

        # Build the URL
        url = f"{self.base_url}/en/squads/{team_id}/{season}/c9/{team_name}-Stats-Premier-League"

        try:
            # Apply rate limiting
            self._rate_limit()

            # Log what we're attempting
            self.logger.info(f"Parsing player stats from: {url}")

            # Make request with urllib
            request = urllib.request.Request(url)
            request.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

            # Get the page content
            with urllib.request.urlopen(request, timeout=30) as response:
                html_content = response.read().decode('utf-8')

            # Parse with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            # Find the table with the stats
            stats_table = soup.find('table', {'id': 'stats_standard_9'})

            # Abort if no table is found
            if not stats_table:
                return { "success": False, "error": "No stats table found" }

            # Extract table headers with data-stat attributes
            thead = stats_table.find('thead')
            header_rows = thead.find_all('tr')

            # Use the second header row with the actual column headers
            if len(header_rows) > 2:
                return { "success": False, "error": "Could not find detailed header row" }

            # Extract table headers
            header_row = header_rows[1]
            headers = []
            for th in header_row.find_all('th'):
                # Get the data-stat attribute
                stat_name = th.get('data-stat', '')
                if stat_name:
                    headers.append(stat_name)
                else:
                    # If no data-stat, use the text content
                    text_context = th.get_text(strip=True)
                    if text_context:
                        headers.append(text_context)

            self.logger.info(f"Found {len(headers)} columns: {headers[:10]}...") # Log the first 10 headers

            # Extract player data
            players_data = []
            tbody = stats_table.find('tbody')

            for row_index, row in enumerate(tbody.find_all('tr')):
                # Get all cells in this row
                cells = row.find_all(['th', 'td'])

                # Skip rows that don't have enough cells
                if len(cells) < 10:
                    self.logger.info(f"Skipping row {row_index} with only {len(cells)} cells")
                    continue

                player_data = {}

                # Map each cell to its corresponding header
                for i, cell in enumerate(cells):
                    if i < len(headers):
                        column_name = headers[i]
                        cell_value = cell.get_text(strip=True)

                        # Handle special cases like players with links
                        if column_name == 'player' and cell.find('a'):
                            # Get the link
                            link = cell.find('a')
                            player_data['player_url'] = link.get('href', '')

                            # Extract player ID from URL
                            if '/players/' in player_data['player_url']:
                                player_id = player_data['player_url'].split('/players/')[1].split('/')[0] 
                                player_data['player_id'] = player_id

                        player_data[column_name] = cell_value

                # Only add if we have all required data
                if player_data.get('player') and len(player_data) > 5:
                    players_data.append(player_data)
                    self.logger.info(f"Added player {player_data.get('player')} to data")
                else:
                    self.logger.info(f"Skipping player {player_data.get('player')} because it doesn't have all required data")

            # Log the number of players found
            self.logger.info(f"Successfully parsed {len(players_data)} players")

            # Return structed data
            return {
                "success": True,
                "team_id": team_id,
                "team_name": team_name,
                "season": season,
                "scraped_at": datetime.now().isoformat(),
                "headers": headers,
                "players": players_data,
                "player_count": len(players_data),
            }

        except Exception as e:
            # Handle any other errors
            self.logger.error(f"Unexpected error parsing player stats: {e}")
            return { "success": False, "error": str(e) }

    def save_to_csv(self, data: Dict, filename: str = None):
        """
        Save the parsed player data to a CSV file in the correct directory
        """
        
        # Ensure we have valid data to save
        if not data.get('success') or not data.get('players'):
            self.logger.error("No valid player data to save")
            return {"success": False, "error": "No valid player data to save"}

        try:
            # Create the data/raw directory if it doesn't exist
            data_dir = "data/raw"
            os.makedirs(data_dir, exist_ok=True)
            
            # Generate filename if not provided
            if not filename:
                # Create filename based on team and season
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{data['team_name']}_{data['season']}_{timestamp}.csv"

            # Create the full file path
            file_path = f"{data_dir}/{filename}"

            # Log what we're doing
            self.logger.info(f"Saving {len(data['players'])} players to: {file_path}")

            # Convert to pandas DataFrame for easy CSV writing
            df = pd.DataFrame(data['players'])

            # Save to CSV with proper encoding
            df.to_csv(file_path, encoding='utf-8', index=False)

            # Log success
            self.logger.info(f"Successfully saved player data to {file_path}")
            self.logger.info(f"Saved {len(df)} rows with {len(df.columns)} columns")

            # Return success info
            return {
                "success": True,
                "file_path": file_path,
                "rows_saved": len(df),
                "columns_saved": len(df.columns),
                "filename": filename
            }

        except Exception as e:
            # Handle any other errors
            self.logger.error(f"Error saving to CSV: {e}")
            return {"success": False, "error": str(e)}