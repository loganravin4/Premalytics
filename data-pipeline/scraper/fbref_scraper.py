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
    Scrapes soccer statistics from FBRef and organizes all our functions in one place with multi-table support
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

        # Define additional table types we can scrape beyond standard stats
        self.additional_tables = {
            'keeper': {
                'table_id': 'stats_keeper_9',
                'display_name': 'Goalkeeping Stats',
                'description': 'Playing Time, Performance, Penalties'
            },
            'advanced_keeper': {
                'table_id': 'stats_keeper_adv_9',
                'display_name': 'Advanced Goalkeeping Stats',
                'description': 'Goals, Expected, Launched, Passes, Goal Kicks, Crosses, Sweeper'
            },
            'shooting': {
                'table_id': 'stats_shooting_9',
                'display_name': 'Shooting Stats',
                'description': 'Shots, shot accuracy, expected goals, finishing'
            },
            'passing': {
                'table_id': 'stats_passing_9',
                'display_name': 'Passing Stats',
                'description': 'Pass completion, creativity, distribution'
            },
            'passing_types': {
                'table_id': 'stats_passing_types_9',
                'display_name': 'Passing Types',
                'description': 'Pass Types, Corner Kicks, Outcomes'
            },
            'gca': {
                'table_id': 'stats_gca_9',
                'display_name': 'Goal Creating Actions',
                'description': 'Passes, Crosses, Shots, Key Passes, Long Balls'
            },
            'defense': {
                'table_id': 'stats_defense_9',
                'display_name': 'Defensive Actions',
                'description': 'Tackles, blocks, interceptions, clearances'
            },
            'possession': {
                'table_id': 'stats_possession_9',
                'display_name': 'Possession Stats',
                'description': 'Touches, carries, dribbles, ball control'
            }
        }

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

    def test_connection_urllib(self, team_id: str, team_name: str, season: str):
        """
        Test connection using urllib instead of requests library
        Now with proper gzip decompression handling
        """

        # Build the URL
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

    def discover_team_id(self, team_search_name: str, season: str):
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

    def test_team_id(self, team_id: str, team_name: str, season: str):
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

    def discover_all_premier_league_teams(self, season: str):
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

    def _parse_table_by_id(self, soup: BeautifulSoup, table_id: str, table_name: str = None) -> Dict:
        """
        Private method to parse any table from the HTML soup using the table ID
        """

        try:
            # Find the specific stats table
            stats_table = soup.find('table', {'id': table_id})

            # Check if table exists
            if not stats_table:
                return {"success": False, "error": f"No {table_name or table_id} table found"}

            # Extract table headers from second row
            thead = stats_table.find('thead')
            header_rows = thead.find_all('tr')

            # Validate we have enough header rows
            if len(header_rows) < 2:
                return {"success": False, "error": f"Could not find detailed header row in {table_name or table_id}"}

            # Extract table headers from second row
            header_row = header_rows[1]
            headers = []
            for th in header_row.find_all('th'):
                # Get the data-stat attribute for clean column names
                stat_name = th.get('data-stat', '')
                if stat_name:
                    headers.append(stat_name)
                else:
                    # Fallback to text content if no data-stat
                    text_content = th.get_text(strip=True)
                    if text_content:
                        headers.append(text_content)

            self.logger.info(f"Found {len(headers)} columns in {table_name or table_id}")

            # Extract player data from tbody
            players_data = []
            tbody = stats_table.find('tbody')

            for row_index, row in enumerate(tbody.find_all('tr')):
                # Get all cells in this row
                cells = row.find_all(['th', 'td'])

                # Skip rows with insufficient cells (likely summary rows)
                if len(cells) < 10:
                    continue

                player_data = {}

                # Map each cell value to its corresponding header
                for i, cell in enumerate(cells):
                    if i < len(headers):
                        column_name = headers[i]
                        cell_value = cell.get_text(strip=True)

                        # Special handling for player links to extract IDs
                        if column_name == 'player' and cell.find('a'):
                            link = cell.find('a')
                            player_data['player_url'] = link.get('href', '')

                            # Extract player ID from URL pattern
                            if '/players/' in player_data['player_url']:
                                player_id = player_data['player_url'].split('/players/')[1].split('/')[0] 
                                player_data['player_id'] = player_id

                        # Store the cell value
                        player_data[column_name] = cell_value

                # Only add players with sufficient data
                if player_data.get('player') and len(player_data) > 5:
                    players_data.append(player_data)

            # Log successful parsing
            self.logger.info(f"Successfully parsed {len(players_data)} players from {table_name or table_id}")

            # Return structured data
            return {
                "success": True,
                "table_id": table_id,
                "headers": headers,
                "players": players_data,
                "player_count": len(players_data),
            }

        except Exception as e:
            self.logger.error(f"Error parsing table {table_id}: {e}")
            return {"success": False, "error": str(e)}

    def parse_player_stats(self, team_id: str, team_name: str, season: str, include_additional: List[str] = None):
        """
        Extract player statistics with optional additional table types
        If include_additional is None, gets only standard stats
        """

        # Build URL
        url = f"{self.base_url}/en/squads/{team_id}/{season}/c9/{team_name}-Stats-Premier-League"
        max_retries = 3
        retry_count = 0
        
        # Use retry logic
        while retry_count < max_retries:
            try:
                # Apply rate limiting
                self._rate_limit()

                if retry_count > 0:
                    self.logger.info(f"Retry attempt {retry_count} for {team_name} {season}")
                else:
                    table_info = f" + {len(include_additional)} additional" if include_additional else ""
                    self.logger.info(f"Parsing player stats{table_info} from: {url}")

                # Make request
                request = urllib.request.Request(url)
                request.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

                with urllib.request.urlopen(request, timeout=60) as response:
                    html_content = response.read().decode('utf-8')

                soup = BeautifulSoup(html_content, 'html.parser')

                # Parse standard stats table first
                standard_result = self._parse_table_by_id(soup, 'stats_standard_9', 'Standard Stats')
                
                if not standard_result['success']:
                    return standard_result

                # Add metadata
                standard_result.update({
                    "team_id": team_id,
                    "team_name": team_name,
                    "season": season,
                    "scraped_at": datetime.now().isoformat(),
                })

                # If no additional tables requested, return
                if not include_additional:
                    return standard_result

                # Parse additional tables using the same HTML soup
                additional_data = {}
                successful_additional = 0
                failed_additional = []
                
                for table_type in include_additional:
                    if table_type in self.additional_tables:
                        config = self.additional_tables[table_type]
                        self.logger.info(f"Parsing {config['display_name']}...")
                        
                        table_result = self._parse_table_by_id(soup, config['table_id'], config['display_name'])
                        if table_result['success']:
                            additional_data[table_type] = {
                                'table_type': table_type,
                                'display_name': config['display_name'],
                                'description': config['description'],
                                'headers': table_result['headers'],
                                'players': table_result['players'],
                                'player_count': table_result['player_count']
                            }
                            successful_additional += 1
                        else:
                            failed_additional.append(table_type)
                            self.logger.warning(f"Failed to parse {config['display_name']}")
                    else:
                        failed_additional.append(table_type)
                        self.logger.error(f"Unknown table type: {table_type}")

                # Add additional data to the result
                standard_result.update({
                    "additional_tables": additional_data,
                    "additional_tables_successful": successful_additional,
                    "additional_tables_failed": failed_additional,
                    "total_tables_parsed": 1 + successful_additional
                })
                
                self.logger.info(f"Successfully parsed standard + {successful_additional} additional tables")
                return standard_result

            except urllib.error.HTTPError as e:
                # Handle HTTP errors with retry logic
                if e.code in [403, 500, 502, 504]:
                    retry_count += 1
                    if retry_count < max_retries:
                        # Exponential backoff: 30s, 60s, 120s
                        wait_time = 30 * (2 ** (retry_count - 1))
                        self.logger.warning(f"HTTP {e.code} error, waiting {wait_time}s before retry {retry_count}...")
                        time.sleep(wait_time)
                        continue
                    else:
                        # All retries exhausted
                        self.logger.error(f"HTTP {e.code} error persisted after {max_retries} attempts")
                        return {"success": False, "error": f"HTTP {e.code} after {max_retries} retries"}
                else:
                    # Non-retryable HTTP error
                    return {"success": False, "error": f"HTTP Error {e.code}: {e.reason}"}
                    
            except Exception as e:
                # Handle timeout and other errors
                error_message = str(e).lower()
                
                if "timed out" in error_message or "timeout" in error_message:
                    retry_count += 1
                    if retry_count < max_retries:
                        # Linear backoff for timeouts: 20s, 40s, 60s
                        wait_time = 20 * retry_count
                        self.logger.warning(f"Timeout error, waiting {wait_time}s before retry {retry_count}...")
                        time.sleep(wait_time)
                        continue
                    else:
                        # All retries exhausted
                        self.logger.error(f"Timeout persisted after {max_retries} attempts")
                        return {"success": False, "error": f"Timeout after {max_retries} retries"}
                else:
                    # Non-retryable error
                    return {"success": False, "error": str(e)}
    
        # If we exit the while loop without returning, all retries failed
        return {"success": False, "error": f"Failed after {max_retries} retry attempts"}

    def save_to_csv(self, data: Dict, filename: str = None):
        """
        Save the parsed player data to a CSV file
        """
        
        # Ensure we have valid data to save
        if not data.get('success') or not data.get('players'):
            self.logger.error("No valid player data to save")
            return {"success": False, "error": "No valid player data to save"}

        try:
            # Get the season from the data
            season = data.get('season', 'unknown')
            
            # Get the team name from the data
            team_name = data.get('team_name', 'unknown')
            
            # Create the NEW directory structure: data/raw/{season}/{team}/
            team_dir = f"data/raw/{season}/{team_name}"
            os.makedirs(team_dir, exist_ok=True)
            
            # Generate filename if not provided
            if not filename:
                # Create filename based on team and season
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{team_name}_{season}_{timestamp}.csv"
            
            # Create the full file path (NOW in team subfolder)
            file_path = f"{team_dir}/{filename}"
            
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
                "filename": filename,
                "team_dir": team_dir  # Include this for consistency with new methods
            }
            
        except Exception as e:
            # Handle any other errors
            self.logger.error(f"Error saving to CSV: {e}")
            return {"success": False, "error": str(e)}

    def save_extended_data(self, extended_data: Dict, base_filename: str = None):
        """
        Save extended data that includes both standard and additional tables
        Creates separate CSV files for each table type with organized naming
        """

        if not extended_data.get('success'):
            return {'success': False, 'error': 'No valid extended data to save'}
        
        season = extended_data['season']
        team_name = extended_data['team_name']
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create season directory
        season_dir = f"data/raw/{season}"
        os.makedirs(season_dir, exist_ok=True)
        
        saved_files = []
        
        try:
            # Save standard stats using existing structure
            if not base_filename:
                standard_filename = f"{team_name}_{season}_standard_{timestamp}.csv"
            else:
                standard_filename = base_filename.replace('.csv', '_standard.csv')
            
            standard_path = f"{season_dir}/{standard_filename}"
            
            # Create standard DataFrame using existing logic
            standard_df = pd.DataFrame(extended_data['players'])
            standard_df.to_csv(standard_path, encoding='utf-8', index=False)
            
            saved_files.append({
                'table_type': 'standard',
                'file_path': standard_path,
                'rows': len(standard_df),
                'columns': len(standard_df.columns),
                'filename': standard_filename
            })
            
            self.logger.info(f"Saved standard stats: {len(standard_df)} rows to {standard_filename}")
            
            # Save additional tables if they exist
            for table_type, table_data in extended_data.get('additional_tables', {}).items():
                additional_filename = f"{team_name}_{season}_{table_type}_{timestamp}.csv"
                additional_path = f"{season_dir}/{additional_filename}"
                
                additional_df = pd.DataFrame(table_data['players'])
                additional_df.to_csv(additional_path, encoding='utf-8', index=False)
                
                saved_files.append({
                    'table_type': table_type,
                    'file_path': additional_path,
                    'rows': len(additional_df),
                    'columns': len(additional_df.columns),
                    'filename': additional_filename
                })
                
                self.logger.info(f"Saved {table_data['display_name']}: {len(additional_df)} rows to {additional_filename}")
            
            return {
                'success': True,
                'files_saved': len(saved_files),
                'saved_files': saved_files
            }
            
        except Exception as e:
            self.logger.error(f"Error saving extended data: {e}")
            return {'success': False, 'error': str(e)}

    def scrape_multiple_teams(self, teams: Dict, season: str, include_additional: List[str] = None, include_match_logs: bool = True):
        """
        Scrape multiple teams with optional additional tables and match logs
        Now uses improved directory structure with team folders
        """
        
        # Track results for all teams
        results = {}
        successful_teams = 0
        failed_teams = 0
        total_tables_scraped = 0
        
        # Convert teams dictionary to list for iteration
        team_items = list(teams.items())
        
        # Build info string about what we're scraping
        table_info = ""
        if include_additional:
            table_info += f" + {len(include_additional)} additional player stats"
        if include_match_logs:
            table_info += " + match logs"
        
        self.logger.info(f"Scraping {len(team_items)} teams{table_info} for season {season}")
        
        # Loop through each team
        for team_key, team_info in team_items:
            try:
                self.logger.info(f"Scraping {team_info['official_name']}")
                
                # STEP 1: Scrape player statistics
                player_result = self.parse_player_stats(
                    team_info['id'], 
                    team_info['name'], 
                    season, 
                    include_additional
                )
                
                # Track results for this team
                team_results = {
                    "success": False,
                    "player_stats": None,
                    "match_logs": None,
                }
                
                # STEP 2: Save player stats if successful
                if player_result['success']:
                    # Save player stats using new directory structure
                    if include_additional and player_result.get('additional_tables'):
                        save_result = self.save_extended_team_data(player_result)
                    else:
                        save_result = self.save_team_data(
                            player_result, 
                            data_type='player_standard_stats'
                        )
                    
                    if save_result['success']:
                        team_results["player_stats"] = {
                            "success": True,
                            "players": player_result["player_count"],
                            "tables_parsed": player_result.get('total_tables_parsed', 1),
                            "files": save_result.get('saved_files', [save_result])
                        }
                        total_tables_scraped += player_result.get('total_tables_parsed', 1)
                    else:
                        team_results["player_stats"] = {"success": False, "error": save_result["error"]}
                else:
                    team_results["player_stats"] = {"success": False, "error": player_result["error"]}
                
                # STEP 3: Scrape match logs if requested
                if include_match_logs:
                    match_result = self.parse_match_logs(
                        team_info['id'],
                        team_info['name'],
                        season,
                        premier_league_only=True  # Filter to PL only
                    )
                    
                    # Save match logs if successful
                    if match_result['success']:
                        match_save_result = self.save_team_data(
                            match_result,
                            data_type='match_logs'
                        )
                        
                        if match_save_result['success']:
                            team_results["match_logs"] = {
                                "success": True,
                                "matches": match_result["match_count"],
                                "file": match_save_result["file_path"]
                            }
                            total_tables_scraped += 1  # Count match logs as one table
                        else:
                            team_results["match_logs"] = {"success": False, "error": match_save_result["error"]}
                    else:
                        team_results["match_logs"] = {"success": False, "error": match_result["error"]}
                
                # STEP 4: Determine overall success for this team
                player_success = team_results["player_stats"] and team_results["player_stats"].get("success", False)
                match_success = not include_match_logs or (team_results["match_logs"] and team_results["match_logs"].get("success", False))
                
                if player_success and match_success:
                    team_results["success"] = True
                    successful_teams += 1
                    self.logger.info(f"Successfully scraped all data for {team_info['official_name']}")
                else:
                    failed_teams += 1
                    self.logger.warning(f"Partial or complete failure for {team_info['official_name']}")
                
                # Store results for this team
                results[team_key] = team_results
                
            except Exception as e:
                # Handle unexpected errors
                self.logger.error(f"Unexpected error scraping {team_key}: {e}")
                results[team_key] = {"success": False, "error": str(e)}
                failed_teams += 1
        
        # Return summary of all scraping
        return {
            "success": True,
            "total_teams": len(team_items),
            "successful_teams": successful_teams,
            "failed_teams": failed_teams,
            "total_tables_scraped": total_tables_scraped,
            "results": results,
        }

    def scrape_historical_data(self, seasons: List[str], max_teams_per_season: int = None):
        """
        Scrape multiple seasons using existing methods
        """
        all_results = {}
        
        for season in seasons:
            self.logger.info(f"Starting season: {season}")
            
            # Discover teams for this season
            teams_result = self.discover_all_premier_league_teams(season)
            
            if teams_result['success']:
                teams = teams_result['teams']
                
                # Limit teams for testing if specified
                if max_teams_per_season:
                    teams = dict(list(teams.items())[:max_teams_per_season])
                
                # Scrape all teams for this season
                season_result = self.scrape_multiple_teams(teams, season)
                all_results[season] = season_result
            else:
                all_results[season] = {'success': False, 'error': teams_result['error']}
        
        return all_results

    def scrape_completed_seasons(self, completed_seasons: List[str]):
        """
        Scrape historical seasons that never change
        """

        all_results = {}
        total_skipped = 0
        total_scraped = 0

        self.logger.info(f"Scraping completed seasons: {completed_seasons}")

        for season in completed_seasons:
            # Check if we've already scraped this season
            if self._season_already_scraped(season):
                self.logger.info(f"Skipping already scraped season: {season}")
                all_results[season] = {'skipped': True, 'reason': 'Already scraped'}
                total_skipped += 1
                continue

            # Scrape complete season data
            self.logger.info(f"Scraping complete season data for: {season}")

            try:
                # Discover teams for this season
                teams_result = self.discover_all_premier_league_teams(season)

                if teams_result['success']:
                    teams = teams_result['teams']
                    self.logger.info(f"Discovered {len(teams)} teams for season: {season}")

                    # Scrape all teams for this season
                    season_result = self.scrape_multiple_teams(teams, season)
                    all_results[season] = season_result
                    total_scraped += 1

                    self.logger.info(f"Completed scraping for {season}: {season_result['successful_teams']} successful")

                else:
                    self.logger.error(f"Failed to discover teams for season: {season}: {teams_result['error']}")
                    all_results[season] = {'success': False, 'error': teams_result['error']}

            except Exception as e:
                self.logger.error(f"Unexpected error scraping season: {season}: {e}")
                all_results[season] = {'success': False, 'error': str(e)}

        self.logger.info(f"Completed scraping {total_scraped} seasons, skipped {total_skipped} seasons")

        return {
            "success": True,
            "seasons_processed": len(completed_seasons),
            "seasons_skipped": total_skipped,
            "seasons_scraped": total_scraped,
            "results": all_results,
        }
    
    def update_current_season(self, current_season: str, include_additional: List[str] = None, include_match_logs: bool = True):
        """
        Update current season data by clearing old files and scraping fresh data
        """
        
        self.logger.info(f"Updating current season: {current_season}")
        
        try:
            # Discover all teams for this season
            teams_result = self.discover_all_premier_league_teams(current_season)
            
            if not teams_result['success']:
                self.logger.error(f"Failed to discover teams: {teams_result['error']}")
                return {"success": False, "error": teams_result['error']}
            
            teams = teams_result['teams']
            self.logger.info(f"Discovered {len(teams)} teams for season {current_season}")
            
            # Clear old data for each team
            for team_key, team_info in teams.items():
                clear_result = self.clear_team_season_data(current_season, team_info['name'])
                if clear_result['success']:
                    self.logger.info(f"Cleared {clear_result['files_deleted']} old files for {team_info['official_name']}")
            
            # Scrape fresh data for all teams
            season_result = self.scrape_multiple_teams(
                teams, 
                current_season, 
                include_additional=include_additional,
                include_match_logs=include_match_logs
            )
            
            # Return summary
            if season_result['success']:
                self.logger.info(f"Completed update for {current_season}: {season_result['successful_teams']} teams updated")
                return {
                    "success": True,
                    "season": current_season,
                    "teams_updated": season_result['successful_teams'],
                    "teams_failed": season_result['failed_teams'],
                    "tables_scraped": season_result['total_tables_scraped'],
                    "results": season_result['results'],
                }
            else:
                return {"success": False, "error": "Scraping failed"}
                
        except Exception as e:
            self.logger.error(f"Unexpected error updating current season {current_season}: {e}")
            return {"success": False, "error": str(e)}

    def _season_already_scraped(self, season: str) -> bool:
        """
        Private method to check if a season has already been scraped
        """

        season_dir = f"data/raw/{season}"

        # Check if the season directory exists
        if not os.path.exists(season_dir):
            return False

        # Count CSV files in the season directory
        try:
            csv_files = [f for f in os.listdir(season_dir) if f.endswith('.csv')]
            file_count = len(csv_files)

            # Expect at least 20 teams for a complete season
            if file_count >= 20:
                self.logger.info(f"Season {season} has already been scraped with {file_count} files")
                return True
            else:
                self.logger.info(f"Season {season} has not been scraped fully with {file_count} files")
                return False

        except Exception as e:
            self.logger.error(f"Error checking if season {season} has already been scraped: {e}")
            return False

    def full_historical_collection(self, start_year: int = 2021, end_year: int = 2024):
        """
        Complete historical data collection for ML training dataset
        """

        # Generate a list of completed seasons
        completed_seasons = []
        for year in range(start_year, end_year + 1):
            season = f"{year}-{year + 1}"
            completed_seasons.append(season)

        self.logger.info(f"Starting full historical collection: {completed_seasons}")

        # Scrape completed seasons
        historical_results = self.scrape_completed_seasons(completed_seasons)

        # Calculate total data collected
        total_teams = 0
        total_players = 0

        for season, result in historical_results["results"].items():
            if result.get("success"):
                total_teams += result.get("successful_teams", 0)
                # Estimate players per team based on average
                total_players += result.get("successful_teams", 0) * 25 # Average 25 players max per team

        self.logger.info(f"Completed full historical collection: {total_teams} teams, {total_players} players")

        return {
            "success": True,
            "historical_results": historical_results,
            "total_teams": total_teams,
            "total_players": total_players,
            "ready_for_ml": total_players >= 1500,
        }

    def _parse_match_logs_table(self, soup: BeautifulSoup, table_id: str = 'matchlogs_for') -> Dict:
        """
        Private method to parse match-level data (fixtures/results), different structure than player stats
        """
        
        try:
            # Find the match logs table using the specific table ID
            match_table = soup.find('table', {'id': table_id})
            
            # Check if the table exists on the page
            if not match_table:
                return {"success": False, "error": f"No match logs table found with ID {table_id}"}
            
            # Get the table headers from thead section
            thead = match_table.find('thead')
            header_row = thead.find('tr')
            
            # Extract column names from the header row
            headers = []
            for th in header_row.find_all('th'):
                # Get the data-stat attribute which contains the clean column name
                stat_name = th.get('data-stat', '')
                if stat_name:
                    headers.append(stat_name)
            
            # Log how many columns we found
            self.logger.info(f"Found {len(headers)} columns in match logs table")
            
            # Extract match data from tbody section
            matches_data = []
            tbody = match_table.find('tbody')
            
            # Loop through each row in the table body
            for row_index, row in enumerate(tbody.find_all('tr')):
                # Get all cells (th and td) in this row
                cells = row.find_all(['th', 'td'])
                
                # Skip rows with too few cells (likely summary/header rows)
                if len(cells) < 5:
                    continue
                
                # Create a dictionary to store this match's data
                match_data = {}
                
                # Map each cell value to its corresponding header
                for i, cell in enumerate(cells):
                    if i < len(headers):
                        # Get the column name from our headers list
                        column_name = headers[i]
                        # Extract the text content from the cell
                        cell_value = cell.get_text(strip=True)
                        
                        # Special handling for opponent links to extract team IDs
                        if column_name == 'opponent' and cell.find('a'):
                            link = cell.find('a')
                            opponent_url = link.get('href', '')
                            # Store the full URL for reference
                            match_data['opponent_url'] = opponent_url
                            
                            # Extract opponent team ID from URL pattern /squads/{team_id}/
                            if '/squads/' in opponent_url:
                                opponent_id = opponent_url.split('/squads/')[1].split('/')[0]
                                match_data['opponent_id'] = opponent_id
                        
                        # Special handling for match report links
                        if column_name == 'match_report' and cell.find('a'):
                            link = cell.find('a')
                            match_report_url = link.get('href', '')
                            # Only store if it's an actual match report (not head-to-head comparison)
                            if '/matches/' in match_report_url:
                                match_data['match_report_url'] = match_report_url
                                # Extract unique match ID from URL
                                match_id = match_report_url.split('/matches/')[1].split('/')[0]
                                match_data['match_id'] = match_id
                        
                        # Store the cell value under its column name
                        match_data[column_name] = cell_value
                
                # Only add matches that have essential data (date and opponent)
                if match_data.get('date') and match_data.get('opponent'):
                    matches_data.append(match_data)
            
            # Log successful parsing
            self.logger.info(f"Successfully parsed {len(matches_data)} matches from match logs")
            
            # Return structured data
            return {
                "success": True,
                "table_id": table_id,
                "headers": headers,
                "matches": matches_data,
                "match_count": len(matches_data),
            }
            
        except Exception as e:
            # Log any errors that occurred
            self.logger.error(f"Error parsing match logs table {table_id}: {e}")
            return {"success": False, "error": str(e)}


    def _filter_premier_league_matches(self, matches: List[Dict]) -> List[Dict]:
        """
        Private method to filter match logs to only include Premier League matches
        Removes FA Cup, Champions League, EFL Cup, etc.
        """
        
        # List of Premier League indicators in the 'round' column
        premier_league_indicators = [
            'Matchweek', # Regular season matches
            'Premier League', # General PL indicator
        ]
        
        # List of non-Premier League competition names to exclude
        excluded_competitions = [
            'FA Cup',
            'EFL Cup',
            'Champions Lg',
            'Europa Lg',
            'Europa Conference Lg',
            'Community Shield',
            'League phase', # Champions League new format
            'Knockout phase', # Champions League knockout
            'Round of 16', # Cup competitions
            'Quarter-finals',
            'Semi-finals',
            'Final',
        ]
        
        # Filter matches to only include Premier League
        filtered_matches = []
        
        for match in matches:
            # Get the round/competition name
            round_name = match.get('round', '')
            
            # Check if this is a Premier League match
            is_premier_league = any(indicator in round_name for indicator in premier_league_indicators)
            
            # Check if this is explicitly a non-PL competition
            is_excluded = any(excluded in round_name for excluded in excluded_competitions)
            
            # Only include if it's PL and not explicitly excluded
            if is_premier_league and not is_excluded:
                filtered_matches.append(match)
        
        # Log filtering results
        self.logger.info(f"Filtered {len(matches)} matches down to {len(filtered_matches)} Premier League matches")
        
        return filtered_matches


    def parse_match_logs(self, team_id: str, team_name: str, season: str, premier_league_only: bool = True):
        """
        Extract match-level data (fixtures, results, scores) for a team
        """
        
        # Build the URL for the team's page
        url = f"{self.base_url}/en/squads/{team_id}/{season}/c9/{team_name}-Stats-Premier-League"
        max_retries = 3
        retry_count = 0
        
        # Use retry logic for robustness
        while retry_count < max_retries:
            try:
                # Apply rate limiting to avoid being blocked
                self._rate_limit()
                
                # Log retry attempts if this isn't the first try
                if retry_count > 0:
                    self.logger.info(f"Retry attempt {retry_count} for {team_name} {season} match logs")
                else:
                    self.logger.info(f"Parsing match logs from: {url}")
                
                # Create the request with proper headers
                request = urllib.request.Request(url)
                request.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
                
                # Make the request and get the HTML content
                with urllib.request.urlopen(request, timeout=60) as response:
                    html_content = response.read().decode('utf-8')
                
                # Parse the HTML with BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Parse the match logs table using our specialized method
                match_result = self._parse_match_logs_table(soup, 'matchlogs_for')
                
                # Check if parsing was successful
                if not match_result['success']:
                    return match_result
                
                # Filter to only Premier League matches if requested
                if premier_league_only:
                    match_result['matches'] = self._filter_premier_league_matches(match_result['matches'])
                    match_result['match_count'] = len(match_result['matches'])
                
                # Add metadata to the result
                match_result.update({
                    "team_id": team_id,
                    "team_name": team_name,
                    "season": season,
                    "scraped_at": datetime.now().isoformat(),
                    "data_type": "match_logs",  # Identifier for what type of data this is
                })
                
                # Log success
                self.logger.info(f"Successfully parsed {match_result['match_count']} matches for {team_name}")
                return match_result
                
            except urllib.error.HTTPError as e:
                # Handle HTTP errors with retry logic
                if e.code in [403, 500, 502, 504]:
                    retry_count += 1
                    if retry_count < max_retries:
                        # Exponential backoff: 30s, 60s, 120s
                        wait_time = 30 * (2 ** (retry_count - 1))
                        self.logger.warning(f"HTTP {e.code} error, waiting {wait_time}s before retry {retry_count}...")
                        time.sleep(wait_time)
                        continue
                    else:
                        # All retries exhausted
                        self.logger.error(f"HTTP {e.code} error persisted after {max_retries} attempts")
                        return {"success": False, "error": f"HTTP {e.code} after {max_retries} retries"}
                else:
                    # Non-retryable HTTP error
                    return {"success": False, "error": f"HTTP Error {e.code}: {e.reason}"}
                    
            except Exception as e:
                # Handle timeout and other errors
                error_message = str(e).lower()
                
                if "timed out" in error_message or "timeout" in error_message:
                    retry_count += 1
                    if retry_count < max_retries:
                        # Linear backoff for timeouts: 20s, 40s, 60s
                        wait_time = 20 * retry_count
                        self.logger.warning(f"Timeout error, waiting {wait_time}s before retry {retry_count}...")
                        time.sleep(wait_time)
                        continue
                    else:
                        # All retries exhausted
                        self.logger.error(f"Timeout persisted after {max_retries} attempts")
                        return {"success": False, "error": f"Timeout after {max_retries} retries"}
                else:
                    # Non-retryable error
                    return {"success": False, "error": str(e)}
        
        # If we exit the while loop without returning, all retries failed
        return {"success": False, "error": f"Failed after {max_retries} retry attempts"}


    def save_team_data(self, data: Dict, data_type: str, filename: str = None):
        """
        Save data to the new directory structure: data/raw/{season}/{team}/{data_type}.csv
        Handles both player stats and match logs
        Automatically clears old files for current season updates
        """
        
        # Ensure we have valid data to save
        if not data.get('success'):
            self.logger.error("No valid data to save")
            return {"success": False, "error": "No valid data to save"}
        
        # Check what type of data we're saving (player stats or match logs)
        if 'players' not in data and 'matches' not in data:
            self.logger.error("Data must contain either 'players' or 'matches' key")
            return {"success": False, "error": "Invalid data structure"}
        
        try:
            # Extract metadata from the data dictionary
            season = data.get('season', 'unknown')
            team_name = data.get('team_name', 'unknown')
            
            # Create the directory structure: data/raw/{season}/{team}/
            team_dir = f"data/raw/{season}/{team_name}"
            os.makedirs(team_dir, exist_ok=True)
            
            # Generate descriptive filename if not provided
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                # Use data_type to make filename descriptive
                filename = f"{data_type}_{timestamp}.csv"
            
            # Create the full file path
            file_path = f"{team_dir}/{filename}"
            
            # Determine which data to save (players or matches)
            if 'matches' in data:
                # This is match logs data
                df = pd.DataFrame(data['matches'])
                self.logger.info(f"Saving {len(data['matches'])} matches to: {file_path}")
            else:
                # This is player stats data
                df = pd.DataFrame(data['players'])
                self.logger.info(f"Saving {len(data['players'])} players to: {file_path}")
            
            # Save to CSV with proper encoding
            df.to_csv(file_path, encoding='utf-8', index=False)
            
            # Log success
            self.logger.info(f"Successfully saved data to {file_path}")
            self.logger.info(f"Saved {len(df)} rows with {len(df.columns)} columns")
            
            # Return success info
            return {
                "success": True,
                "file_path": file_path,
                "rows_saved": len(df),
                "columns_saved": len(df.columns),
                "filename": filename,
                "team_dir": team_dir,
            }
            
        except Exception as e:
            # Handle any errors
            self.logger.error(f"Error saving to CSV: {e}")
            return {"success": False, "error": str(e)}


    def save_extended_team_data(self, extended_data: Dict, base_filename: str = None):
        """
        Save extended data that includes both standard and additional player stats tables
        """
        
        # Validate we have data to save
        if not extended_data.get('success'):
            return {'success': False, 'error': 'No valid extended data to save'}
        
        # Extract metadata
        season = extended_data['season']
        team_name = extended_data['team_name']
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create team-specific directory
        team_dir = f"data/raw/{season}/{team_name}"
        os.makedirs(team_dir, exist_ok=True)
        
        # Track all saved files
        saved_files = []
        
        try:
            # Save standard player stats
            standard_filename = f"player_standard_stats_{timestamp}.csv"
            standard_path = f"{team_dir}/{standard_filename}"
            
            # Create DataFrame from player data
            standard_df = pd.DataFrame(extended_data['players'])
            standard_df.to_csv(standard_path, encoding='utf-8', index=False)
            
            # Record this file
            saved_files.append({
                'table_type': 'standard',
                'file_path': standard_path,
                'rows': len(standard_df),
                'columns': len(standard_df.columns),
                'filename': standard_filename
            })
            
            self.logger.info(f"Saved player standard stats: {len(standard_df)} rows to {standard_filename}")
            
            # Save additional player stats tables if they exist
            for table_type, table_data in extended_data.get('additional_tables', {}).items():
                # Create descriptive filename based on table type
                additional_filename = f"player_{table_type}_stats_{timestamp}.csv"
                additional_path = f"{team_dir}/{additional_filename}"
                
                # Create DataFrame and save
                additional_df = pd.DataFrame(table_data['players'])
                additional_df.to_csv(additional_path, encoding='utf-8', index=False)
                
                # Record this file
                saved_files.append({
                    'table_type': table_type,
                    'file_path': additional_path,
                    'rows': len(additional_df),
                    'columns': len(additional_df.columns),
                    'filename': additional_filename
                })
                
                self.logger.info(f"Saved {table_data['display_name']}: {len(additional_df)} rows to {additional_filename}")
            
            # Return summary of all saved files
            return {
                'success': True,
                'files_saved': len(saved_files),
                'saved_files': saved_files,
                'team_dir': team_dir
            }
            
        except Exception as e:
            self.logger.error(f"Error saving extended data: {e}")
            return {'success': False, 'error': str(e)}


    def clear_team_season_data(self, season: str, team_name: str):
        """
        Clear all existing data files for a specific team and season
        Used when updating current season data to replace old with new
        """
        
        # Build the path to the team's directory
        team_dir = f"data/raw/{season}/{team_name}"
        
        # Check if the directory exists
        if not os.path.exists(team_dir):
            self.logger.info(f"No existing data directory for {team_name} in {season}")
            return {"success": True, "files_deleted": 0}
        
        # Track how many files we delete
        files_deleted = 0
        
        try:
            # Loop through all files in the team directory
            for filename in os.listdir(team_dir):
                # Only delete CSV files
                if filename.endswith('.csv'):
                    # Build full path to the file
                    file_path = os.path.join(team_dir, filename)
                    # Delete the file
                    os.remove(file_path)
                    # Increment counter
                    files_deleted += 1
                    # Log the deletion
                    self.logger.info(f"Deleted old file: {filename}")
            
            # Log summary
            self.logger.info(f"Cleared {files_deleted} files from {team_dir}")
            
            return {
                "success": True,
                "files_deleted": files_deleted,
                "team_dir": team_dir
            }
            
        except Exception as e:
            self.logger.error(f"Error clearing team season data: {e}")
            return {"success": False, "error": str(e)}

    def get_available_additional_tables(self) -> Dict[str, Dict]:
        """
        Return information about available additional table types
        """

        return self.additional_tables