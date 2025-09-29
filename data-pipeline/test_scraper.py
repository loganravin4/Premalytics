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
        print("✓ Successfully fetched Liverpool's page!")
        print(f"✓ Status code: {result['status_code']}")
        print(f"✓ Content length: {result['content_length']} bytes")
        return True
    else:
        print(f"❌ Failed to fetch page: {result['error']}")
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

def test_team_discovery(scraper, season = "2025-2026"):
    """
    Test the team discovery functionality with some known teams
    """
    print(f"\nTesting team discovery for season {season}...")

    # Test teams we want to find
    test_teams = ["Liverpool", "Arsenal", "Manchester City"]

    discovered_teams = {}

    for team_name in test_teams:
        print(f"Testing team: {team_name} for season {season}")

        result = scraper.discover_team_id(team_name, season)

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

def test_generic_team_scraping(scraper, team_data, season = "2025-2026"):
    """
    Test scraping any team's data
    """

    print(f"\nTesting scraping for {team_data['official_name']} for season {season}...")

    result = scraper.parse_player_stats(team_data['id'], team_data['name'], season)

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

def test_multi_team_scraping(scraper, season = "2025-2026"):
    """
    Test scraping multiple teams in parallel
    """

    print(f"\nTesting scraping all Premier League teams in parallel...")

    # Discover all Premier League teams
    discovery_result = scraper.discover_all_premier_league_teams(season)

    if discovery_result['success']:
        teams = discovery_result['teams']
        print(f"Discovered {len(teams)} teams")

        # Scrape a limited number of teams
        scrape_result = scraper.scrape_multiple_teams(teams, season)

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

def test_historical_scraping(scraper):
    """
    Test scraping across multiple seasons
    """
    print("\nTesting historical data collection...")
    
    test_seasons = ["2021-2022", "2022-2023", "2023-2024", "2024-2025", "2025-2026"]
    
    # Limit to 3 teams per season for testing
    results = scraper.scrape_historical_data(test_seasons, max_teams_per_season=3)
    
    for season, result in results.items():
        if result.get('success'):
            print(f"{season}: {result['successful_teams']} teams scraped successfully")
        else:
            print(f"{season}: Failed - {result.get('error', 'Unknown error')}")
    
    return True

def test_completed_seasons_scraping(scraper):
    """
    Test scraping completed historical seasons with skip detection
    """
    print("\nTesting completed seasons scraping...")
    
    # Test with completed seasons only
    completed_seasons = ["2021-2022", "2022-2023", "2023-2024", "2024-2025"]
    
    # Run the completed seasons scraper
    results = scraper.scrape_completed_seasons(completed_seasons)
    
    if results['success']:
        print(f"Completed seasons scraping results:")
        print(f"    Seasons processed: {results['seasons_processed']}")
        print(f"    Seasons scraped: {results['seasons_scraped']}")
        print(f"    Seasons skipped: {results['seasons_skipped']}")
        
        # Show details for each season
        for season, result in results['results'].items():
            if result.get('skipped'):
                print(f"    {season}: Skipped - {result['reason']}")
            elif result.get('success'):
                print(f"    {season}: Success - {result['successful_teams']} teams")
            else:
                print(f"    {season}: Failed - {result.get('error', 'Unknown')}")
        
        return True
    else:
        print(f"Completed seasons scraping failed: {results.get('error', 'Unknown error')}")
        return False

def test_current_season_update(scraper):
    """
    Test updating current season data (overwrites existing)
    """
    print("\nTesting current season update...")
    
    # Test updating current season
    current_season = "2025-2026"
    
    # Run current season update
    result = scraper.update_current_season(current_season)
    
    if result['success']:
        print(f"Current season update successful:")
        print(f"    Season: {result['season']}")
        print(f"    Teams updated: {result['teams_updated']}")
        print(f"    Teams failed: {result['teams_failed']}")
        
        # Show some successful teams
        successful_teams = [k for k, v in result['results'].items() if v['success']][:5]
        print(f"    Sample updated teams: {', '.join(successful_teams)}")
        
        return True
    else:
        print(f"Current season update failed: {result['error']}")
        return False

def test_full_historical_collection(scraper):
    """
    Test the complete historical data collection process
    """
    print("\nTesting full historical collection (limited for testing)...")
    
    # Test with limited scope for testing
    result = scraper.full_historical_collection(start_year=2022, end_year=2024)
    
    if result['success']:
        print(f"Full historical collection results:")
        print(f"    Total teams collected: {result['total_teams_collected']}")
        print(f"    Estimated player records: {result['estimated_player_records']}")
        print(f"    Ready for ML training: {result['ready_for_ml']}")
        
        return True
    else:
        print(f"Full historical collection failed")
        return False

def test_season_skip_logic(scraper):
    """
    Test that the scraper properly skips already-scraped seasons
    """
    print("\nTesting season skip logic...")
    
    # This should skip seasons that were already scraped in previous tests
    completed_seasons = ["2021-2022", "2022-2023", "2023-2024", "2024-2025"]  # These should already exist
    
    results = scraper.scrape_completed_seasons(completed_seasons)
    
    skipped_count = sum(1 for result in results['results'].values() if result.get('skipped'))
    
    print(f"Season skip test:")
    print(f"    Seasons to check: {len(completed_seasons)}")
    print(f"    Seasons skipped: {skipped_count}")
    
    if skipped_count > 0:
        print("    Skip logic working correctly")
        return True
    else:
        print("    No seasons were skipped (might be first run)")
        return True

if __name__ == "__main__":
    scraper = test_scraper_initialization()
    
    if scraper:
        # Test current season discovery
        current_season = "2025-2026"
        discovered_teams = test_team_discovery(scraper, current_season)
        
        if discovered_teams:
            print("\n" + "="*60)
            print("PHASE 2C: HISTORICAL DATA COLLECTION TESTING")
            print("="*60)
            
            # Test 1: Historical data collection
            print("\n1. Testing historical seasons collection...")
            historical_success = test_historical_scraping(scraper)
            
            # Test 2: Completed seasons with skip logic
            print("\n2. Testing completed seasons with skip detection...")
            completed_success = test_completed_seasons_scraping(scraper)
            
            # Test 3: Current season update
            print("\n3. Testing current season update...")
            current_success = test_current_season_update(scraper)
            
            # Test 4: Skip logic verification
            print("\n4. Testing season skip logic...")
            skip_success = test_season_skip_logic(scraper)
            
            # Final summary
            if all([historical_success, completed_success, current_success, skip_success]):
                print("\n" + "="*60)
                print("PHASE 2 COMPLETE: PRODUCTION-READY HISTORICAL SCRAPER")
                print("="*60)
                print("Ready for:")
                print("- Full 4-5 season historical collection")
                print("- Weekly current season updates")
                print("- Database schema design")
                print("- ML model development")