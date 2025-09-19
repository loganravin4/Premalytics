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
                logging.FileHandler('scraper.log'), # Log to a file
                logging.StreamHandler(), # Log to the console
            ]
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

    def test_connection(self, team_id: str, team_name: str, season: str = "2025-2026"):
        """
        Test that we can connect to FBRef
        """

        # Get Liverpool's Premier League stats
        url = f"{self.base_url}/en/squads/{team_id}/{season}/c9/{team_name}-Stats-Premier-League"

        # Log the URL we're trying to access
        self.logger.info(f"Testing connection to: {url}")

        try:
            # Apply rate limit
            self._rate_limit()

            # Make the request
            response = self.session.get(url, timeout=30)

            # Check if the request was successful
            response.raise_for_status()

            # Log the response status
            self.logger.info(f"Response status: {response.status_code}")
            self.logger.info(f"Content length: {len(response.text)} bytes")
            self.logger.info(f"Successfully connected to FBRef")

            # Return the response
            return {
                "success": True,
                "url": url,
                "status_code": response.status_code,
                "content_length": len(response.text),
                "content_preview": response.text[:500],
            }
        
        except requests.exceptions.Timeout:
            # Handle timeout error
            self.logger.error(f"Timeout after 30 seconds while accessing {url}")
            return { "success": False, "error": "Timeout" }

        except requests.exceptions.ConnectionError:
            # Handle connection error
            self.logger.error(f"Connection error while accessing {url}, check your internet connection")
            return { "success": False, "error": "ConnectionError" }

        except requests.exceptions.HTTPError as e:
            # Handle HTTP error
            self.logger.error(f"HTTP error while accessing {url}: {e}")
            return { "success": False, "error": f"HTTPError: {e}" }

        except Exception as e:
            # Handle other errors
            self.logger.error(f"Unexpected error while accessing {url}: {e}")
            return { "success": False, "error": f"UnexpectedError: {e}" }

    def test_connection_with_referrer(self, team_id: str, team_name: str, season: str = "2025-2026"):
        """
        Test connection with additional headers that simulate coming from Google
        """
        # Build the URL
        url = f"{self.base_url}/en/squads/{team_id}/{season}/c9/{team_name}-Stats-Premier-League"
        
        # Add extra headers for this specific request
        extra_headers = {
            'Referer': 'https://www.google.com/',  # Pretend we came from Google
            'Sec-Fetch-User': '?1',  # Indicates user-initiated navigation
            'Sec-Ch-Ua': '"Not_A Brand";v="99", "Google Chrome";v="109", "Chromium";v="109"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
        }
        
        try:
            # Apply rate limiting
            self._rate_limit()
            
            # Log the attempt
            self.logger.info(f"Testing with referrer headers: {url}")
            
            # Make request with additional headers
            response = self.session.get(url, headers=extra_headers, timeout=30)
            response.raise_for_status()
            
            self.logger.info("Success with referrer headers!")
            return {
                'success': True,
                'url': url,
                'status_code': response.status_code,
                'content_length': len(response.text),
                'content_preview': response.text[:200]
            }
            
        except Exception as e:
            self.logger.error(f"Failed with referrer headers: {e}")
            return {'success': False, 'error': str(e)}

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

    def scrape_liverpool_stats(self):
        """
        Scrape Liverpool's player stats and parse HTML to get the data we need
        """

        # Build the URL
        team_id = "822bd0ba"
        team_name = "Liverpool"

        # Get the HTML content
        response = self.test_connection_urllib(team_id, team_name)

        # Check if the response is successful
        if not response['success']:
            # Return error
            return { "success": False, "error": response['error'] }

        try: 
            # Parse the HTML content
            soup = BeautifulSoup(response['content_preview'], 'html.parser') # First 500 characters

            # Get the full page content
            url = response['url']
            request = urllib.request.Request(url)
            request.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

            # Make the request
            with urllib.request.urlopen(request, timeout=30) as full_response:
                # Read the response content
                full_content = full_response.read().decode('utf-8')

            # Parse the full HTML content
            full_soup = BeautifulSoup(full_content, 'html.parser')

            # Find the table with the stats
            stats_table = full_soup.find('table', {'id': 'stats_standard_9'})

            if stats_table:
                # Log that we found the table
                self.logger.info("Found the stats table")

                # Count how many player rows there are
                player_rows = stats_table.find('tbody').find_all('tr')
                self.logger.info(f"Found {len(player_rows)} player rows")
                return { "success": True, "table_found": True, "player_count": len(player_rows) }

            else:
                # Log that we didn't find the table
                self.logger.warning("No stats table found with id 'stats_standard_9'")

                # Check for alternative table IDs
                all_tables = full_soup.find_all('table')
                table_ids = [table.get('id') for table in all_tables if table.get('id')]
                self.logger.info(f"Available table IDs: {table_ids}")
                return { "success": True, "table_found": False, "available_ids": table_ids }

        except Exception as e:
            # Handle any other errors
            self.logger.error(f"Unexpected error: {e}")
            return { "success": False, "error": f"Parsing error: {e}" }

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

    def debug_table_structure(self, team_id: str, team_name: str, season: str = "2025-2026"):
        """
        Debug method to examine the actual HTML table structure
        This will help us understand why we're not finding player data
        """
        # Build URL and get content (same as before)
        url = f"{self.base_url}/en/squads/{team_id}/{season}/c9/{team_name}-Stats-Premier-League"
        
        try:
            # Apply rate limiting
            self._rate_limit()

            # Log what we're doing
            self.logger.info(f"Parsing player stats from: {url}")
            
            # Make the request
            request = urllib.request.Request(url)
            request.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            
            with urllib.request.urlopen(request, timeout=30) as response:
                html_content = response.read().decode('utf-8')
            
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find the stats table
            stats_table = soup.find('table', {'id': 'stats_standard_9'})
            
            if not stats_table:
                self.logger.error("No stats table found!")
                return {'success': False, 'error': 'Table not found'}
            
            # Debug the table structure
            print("=== TABLE STRUCTURE DEBUG ===")
            
            # Check thead structure
            thead = stats_table.find('thead')
            if thead:
                print(f"Found thead with {len(thead.find_all('tr'))} rows")
                
                # Look at all header rows
                for i, row in enumerate(thead.find_all('tr')):
                    print(f"Header row {i}: {len(row.find_all(['th', 'td']))} cells")
                    # Show first few cells
                    cells = row.find_all(['th', 'td'])[:5]
                    for j, cell in enumerate(cells):
                        data_stat = cell.get('data-stat', 'NO_DATA_STAT')
                        text = cell.get_text(strip=True)
                        print(f"  Cell {j}: data-stat='{data_stat}', text='{text}'")
            
            # Check tbody structure  
            tbody = stats_table.find('tbody')
            if tbody:
                rows = tbody.find_all('tr')
                print(f"Found tbody with {len(rows)} rows")
                
                # Look at first few data rows
                for i, row in enumerate(rows[:3]):
                    data_row = row.get('data-row')
                    print(f"Row {i}: data-row='{data_row}', {len(row.find_all(['th', 'td']))} cells")
                    
                    # Show first few cells of this row
                    cells = row.find_all(['th', 'td'])[:3]
                    for j, cell in enumerate(cells):
                        text = cell.get_text(strip=True)
                        print(f"  Cell {j}: '{text}'")
            
            print("=== END DEBUG ===")
            return {'success': True}
            
        except Exception as e:
            self.logger.error(f"Debug error: {e}")
            return {'success': False, 'error': str(e)}

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