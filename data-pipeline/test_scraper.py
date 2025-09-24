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
        print(f" Scraper created successfully")
        print(f" Base URL: {scraper.base_url}")
        print(f" Min delay: {scraper.min_delay} seconds")
        print(f" User-Agent: {scraper.session.headers.get('User-Agent')}")
        
        # Test the rate limiting function (should do nothing on first call)
        print("Testing rate limiter...")
        scraper._rate_limit()
        print(" Rate limiter works")
        
        print("\nAll basic tests passed!")
        return scraper
        
    except Exception as e:
        # If anything goes wrong, print the error
        print(f"Error creating scraper: {e}")
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
    result = scraper.test_connection_urllib(team_id, team_name)
    
    # Check what we got back
    if result['success']:
        print(" Successfully fetched Liverpool's page!")
        print(f" Status code: {result['status_code']}")
        print(f" Content length: {result['content_length']} bytes")
        return True
    else:
        print(f"Failed to fetch page: {result['error']}")
        return False

def test_save_to_csv(scraper, team_data):
    """
    Test saving player data to a CSV file
    """

    print("\nTesting save to CSV...")

    # Get player data if no team data is provided
    if not team_data:
        team_id = "822bd0ba"
        team_name = "Liverpool"
        team_data = scraper.parse_player_stats(team_id, team_name)

    if team_data and team_data.get('success'):
        # Save to CSV
        save_result = scraper.save_to_csv(team_data)        

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

def test_team_discovery(scraper):
    """
    Test the team discovery functionality with some known teams
    """
    print("\nTesting team discovery...")

    # Test teams we want to find
    test_teams = ["Liverpool", "Arsenal", "Manchester City"]

    discovered_teams = {}

    for team_name in test_teams:
        print(f"Testing team: {team_name}")

        result = scraper.discover_team_id(team_name)

        if result['success']:
            print(f"Found {team_name}:")
            print(f"    Team ID: {result['team_id']}")
            print(f"    FBRef Name: {result['fbref_name']}")
            discovered_teams[team_name.lower().replace(" ", "_")] = {
                "id": result['team_id'],
                "name": result['fbref_name'],
                "official_name": team_name,
            }
        else:
            print(f"Failed to find {team_name}: {result['error']}")

    return discovered_teams

def test_generic_team_scraping(scraper, team_data):
    """
    Test scraping any team's data
    """

    print(f"\nTesting scraping for {team_data['official_name']}...")

    result = scraper.parse_player_stats(team_data['id'], team_data['name'])

    if result['success']:
        print(f"Successfully scraped {team_data['official_name']}")
        print(f"    Players found: {result['player_count']}")
        print(f"    Columns: {len(result['headers'])}")

        # Show sample data
        if result['players']:
            first_player = result['players'][0]
            print(f"    Sample player: {first_player.get('player', 'Unknown')}")

        # Test CSV saving with this data
        save_result = scraper.save_to_csv(result)
        if save_result['success']:
            print(f"    Saved to: {save_result['filename']}")
            return result
        else:
            print(f"Failed to save to CSV: {save_result['error']}")
            return None
    else:
        print(f"Failed to scrape {team_data['official_name']}: {result['error']}")
        return None

def test_multi_team_scraping(scraper):
    """
    Test scraping multiple teams in parallel
    """

    print(f"\nTesting scraping all Premier League teams in parallel...")

    # Discover all Premier League teams
    discovery_result = scraper.discover_all_premier_league_teams()

    if discovery_result['success']:
        teams = discovery_result['teams']
        print(f"Discovered {len(teams)} teams")

        # Scrape a limited number of teams
        scrape_result = scraper.scrape_multiple_teams(teams)

        if scrape_result['success']:
            print(f"Multi-team scraping complete:")
            print(f"    Successful: {scrape_result['successful_teams']}")
            print(f"    Failed: {scrape_result['failed_teams']}")

            # Show successful teams
            for team_key, result in scrape_result['results'].items():
                if result['success']:
                    print(f"    {team_key}: {result['players']} players -> {result['csv_file']}")

            return True
        else:
            print(f"Failed to scrape multiple teams: {scrape_result['error']}")
    else:
        print(f"Failed to discover teams: {discovery_result['error']}")
    return False

if __name__ == "__main__":
    scraper = test_scraper_initialization()
    
    if scraper:
        # Test individual team discovery (what you just ran)
        discovered_teams = test_team_discovery(scraper)
        
        if discovered_teams:
            # Test scraping first discovered team
            first_team = discovered_teams[list(discovered_teams.keys())[0]]
            scraped_data = test_generic_team_scraping(scraper, first_team)
            
            if scraped_data:
                print("\n" + "="*50)
                print("PHASE 2B: SCALING TO MULTIPLE TEAMS")
                print("="*50)
                
                # Test multi-team scraping
                multi_success = test_multi_team_scraping(scraper)
                
                if multi_success:
                    print("\n Phase 2 Complete!")
                    print("Ready for:")
                    print("- Database schema design (Phase 3)")
                    print("- Full 20-team scraping")
                    print("- ML model development")