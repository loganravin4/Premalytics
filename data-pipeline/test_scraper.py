# Import our scraper class
from scraper.fbref_scraper import FBRefScraper

def test_scraper_initialization():
    """
    Test that our scraper can be created without errors
    This is the simplest possible test
    """
    print("Testing scraper initialization...")
    
    try:
        # Try to create a new scraper instance
        scraper = FBRefScraper()
        
        # Check that basic properties were set correctly
        print(f"✓ Scraper created successfully")
        print(f"✓ Base URL: {scraper.base_url}")
        print(f"✓ Min delay: {scraper.min_delay} seconds")
        print(f"✓ User-Agent: {scraper.session.headers.get('User-Agent')}")
        
        # Test the rate limiting function (should do nothing on first call)
        print("Testing rate limiter...")
        scraper._rate_limit()
        print("✓ Rate limiter works")
        
        print("\n🎉 All basic tests passed!")
        return scraper
        
    except Exception as e:
        # If anything goes wrong, print the error
        print(f"❌ Error creating scraper: {e}")
        return None

def test_web_request(scraper):
    """
    Test fetching Liverpool's actual FBRef page
    """
    print("\nTesting web request...")
    
    # Liverpool's team info from the URL you provided
    team_id = "822bd0ba"
    team_name = "Liverpool"
    
    # Try to fetch the page
    result = scraper.test_connection(team_id, team_name)
    
    # Check what we got back
    if result['success']:
        print("✓ Successfully fetched Liverpool's page!")
        print(f"✓ Status code: {result['status_code']}")
        print(f"✓ Content length: {result['content_length']} bytes")
        print(f"✓ URL: {result['url']}")
        print("\nFirst 200 characters of page:")
        print("-" * 50)
        print(result['content_preview'][:200])
        print("-" * 50)
        return True
    else:
        print(f"❌ Failed to fetch page: {result['error']}")
        return False

def test_homepage_access(scraper):
    """
    Test accessing FBRef's homepage first to see if our headers work
    """
    print("\nTesting homepage access...")
    
    # Try to access just the homepage first
    homepage_url = "https://fbref.com"
    
    try:
        # Apply rate limiting
        scraper._rate_limit()
        
        # Log what we're doing
        scraper.logger.info(f"Testing homepage access: {homepage_url}")
        
        # Make the request to homepage
        response = scraper.session.get(homepage_url, timeout=30)
        
        # Check if successful
        response.raise_for_status()
        
        print("✓ Successfully accessed FBRef homepage!")
        print(f"✓ Status code: {response.status_code}")
        print(f"✓ Content length: {len(response.text)} bytes")
        
        # Look for key elements to confirm we got the real page
        if "Premier League" in response.text:
            print("✓ Found Premier League content - looks like real FBRef page")
        else:
            print("⚠ Didn't find expected content - might be blocked")
            
        return True
        
    except Exception as e:
        print(f"❌ Failed to access homepage: {e}")
        return False

def test_simple_team_page(scraper):
    """
    Test accessing a team page without the specific season/competition path
    """
    print("\nTesting simpler team URL...")
    
    # Try a simpler URL structure first
    simple_url = "https://fbref.com/en/squads/822bd0ba/Liverpool-Stats"
    
    try:
        # Apply rate limiting
        scraper._rate_limit()
        
        # Log what we're doing
        scraper.logger.info(f"Testing simple team URL: {simple_url}")
        
        # Make the request
        response = scraper.session.get(simple_url, timeout=30)
        
        # Check if successful
        response.raise_for_status()
        
        print("✓ Successfully accessed simple Liverpool page!")
        print(f"✓ Status code: {response.status_code}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to access simple team page: {e}")
        return False

def test_urllib_approach(scraper):
    """
    Test using urllib instead of requests
    """
    print("\nTesting urllib approach...")
    
    # Liverpool's team info
    team_id = "822bd0ba"
    team_name = "Liverpool"
    
    # Try the urllib version
    result = scraper.test_connection_urllib(team_id, team_name)
    
    # Check results
    if result['success']:
        print("Success with urllib!")
        print(f"Status code: {result['status_code']}")
        print(f"Content length: {result['content_length']} bytes")
        print("\nFirst 200 characters:")
        print("-" * 50)
        print(result['content_preview'][:200])
        print("-" * 50)
        return True
    else:
        print(f"urllib also failed: {result['error']}")
        return False

def test_liverpool_scraping(scraper):
    """
    Test scraping Liverpool's stats
    """

    result = scraper.scrape_liverpool_stats()

    # Check if the result is successful
    if result['success']:
        if result.get('table_found'):
            # Print the player count
            print(f"Found {result['player_count']} player rows")
            return True
        else:
            # Print the available IDs
            print(f"No table found, available IDs: {result['available_ids']}")
            return False
    else:
        # Print the error
        print(f"Failed to scrape Liverpool's stats: {result['error']}")
        return False

def test_parse_player_data(scraper):
    """
    Turn parsed player data into structured data
    """

    team_id = "822bd0ba"
    team_name = "Liverpool"

    result = scraper.parse_player_stats(team_id, team_name)

    # Check if the result is successful
    if result['success']:
        # Print the player count
        print(f"Found {result['player_count']} players")
        print(f"Columns found: {len(result['headers'])}")
        print("First few columns: {result['headers'][:8]}")

        # Print the first player
        if result['players']:
            first_player = result['players'][0]
            print("\nFirst player data:")
            print(f"Name: {first_player.get('player', 'Unknown')}")
            print(f"Position: {first_player.get('position', 'Unknown')}")
            print(f"Goals: {first_player.get('goals', '0')}")
            print(f"Assists: {first_player.get('assists', '0')}")

        return True
    else:
        # Print the error
        print(f"Failed to parse player data: {result['error']}")
        return False

def debug_table_parsing(scraper):
    """
    Debug why we're not finding player data
    """
    print("\nDebugging table structure...")
    
    team_id = "822bd0ba"
    team_name = "Liverpool"
    
    result = scraper.debug_table_structure(team_id, team_name)
    
    if result['success']:
        print("Debug completed - check output above")
        return True
    else:
        print(f"Debug failed: {result['error']}")
        return False

def test_save_to_csv(scraper):
    """
    Test saving player data to a CSV file
    """

    print("\nTesting save to CSV...")

    # Get player data
    team_id = "822bd0ba"
    team_name = "Liverpool"

    result = scraper.parse_player_stats(team_id, team_name)

    # Check if the result is successful
    if result['success']:
        # Save to CSV
        save_result = scraper.save_to_csv(result)

        # Check if the save is successful
        if save_result['success']:
            print(f"Success! Saved {save_result['rows_saved']} players to CSV")
            print(f"File: {save_result['filename']}")
            print(f"Columns: {save_result['columns_saved']}")
            return True
        else:
            print(f"Failed to save to CSV: {save_result['error']}")
            return False

    else:
        print("Cannot save - no player data available")
        return False

if __name__ == "__main__":
    scraper = test_scraper_initialization()
    
    if scraper:
        urllib_success = test_urllib_approach(scraper)
        
        if urllib_success:
            parsing_success = test_parse_player_data(scraper)
            
            if parsing_success:
                print("\n🎉 Scraper working! Now saving to CSV...")
                csv_success = test_save_to_csv(scraper)
                
                if csv_success:
                    print("\n✅ Phase 2A Complete: Liverpool data successfully scraped and saved!")
                    print("Next steps:")
                    print("- Examine the CSV file")
                    print("- Design database schema based on real data")
                    print("- Expand to scrape all 20 Premier League teams")