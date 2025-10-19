# production_scrape.py
from scraper.fbref_scraper import FBRefScraper
from datetime import datetime

def scrape_historical_seasons_full():
    """
    Scrape all historical completed seasons with full data
    This will collect: player standard stats + shooting + passing + defense + match logs
    """
    
    print("="*80)
    print("PREMALYTICS - FULL HISTORICAL DATA COLLECTION")
    print("="*80)
    
    # Initialize scraper
    scraper = FBRefScraper()
    
    # Define completed seasons (won't change, scrape once)
    completed_seasons = [
        "2021-2022",
        "2022-2023", 
        "2023-2024",
        "2024-2025"
    ]
    
    # Define which additional stats to collect for ML
    additional_stats = [
        'shooting', # Attack: goals, shots, xG
        'passing',  # Distribution: completion, creativity
        'passing_types', # Pass variety: through balls, crosses, corners
        'gca', # Playmaking: goal-creating actions (key stat!)
        'defense', # Defending: tackles, blocks, interceptions  
        'possession', # Ball control: touches, carries, dribbles
        'keeper', # Goalkeeping: saves, clean sheets
        'advanced_keeper' # Advanced GK: sweeping, distribution
    ]
    
    # Track overall progress
    total_seasons = len(completed_seasons)
    all_results = {}
    
    print(f"\nScraping {total_seasons} historical seasons")
    print(f"Additional stats: {', '.join(additional_stats)}")
    print(f"Match logs: Included (Premier League only)")
    print(f"Expected total: ~{total_seasons * 20} teams")
    print()
    
    # Scrape each season
    for season_num, season in enumerate(completed_seasons, 1):
        print(f"\n{'='*80}")
        print(f"SEASON {season_num}/{total_seasons}: {season}")
        print(f"{'='*80}")
        
        # Check if already scraped (skip if exists)
        if scraper._season_already_scraped(season):
            print(f"✓ Season {season} already scraped, skipping...")
            all_results[season] = {'skipped': True, 'reason': 'Already complete'}
            continue
        
        # Discover teams for this season
        print(f"\n[1/3] Discovering teams for {season}...")
        teams_result = scraper.discover_all_premier_league_teams(season)
        
        if not teams_result['success']:
            print(f"✗ Failed to discover teams: {teams_result['error']}")
            all_results[season] = {'success': False, 'error': teams_result['error']}
            continue
        
        teams = teams_result['teams']
        print(f"✓ Found {len(teams)} teams")
        
        # Scrape all teams with all data types
        print(f"\n[2/3] Scraping player stats + match logs for {len(teams)} teams...")
        print(f"     This will take approximately {len(teams) * 7 / 60:.1f} minutes")
        
        season_result = scraper.scrape_multiple_teams(
            teams=teams,
            season=season,
            include_additional=additional_stats, # Get all additional stats
            include_match_logs=True # Get match-level data
        )
        
        # Store results
        all_results[season] = season_result
        
        # Print summary
        print(f"\n[3/3] Season {season} Summary:")
        print(f"     ✓ Successful teams: {season_result['successful_teams']}/{season_result['total_teams']}")
        print(f"     ✗ Failed teams: {season_result['failed_teams']}")
        print(f"     ✓ Total tables scraped: {season_result['total_tables_scraped']}")
        
        # Show any failures
        if season_result['failed_teams'] > 0:
            print(f"\n     Failed teams:")
            for team_key, team_result in season_result['results'].items():
                if not team_result['success']:
                    print(f"       - {team_key}: {team_result.get('error', 'Unknown error')}")
    
    # Final summary
    print(f"\n{'='*80}")
    print("FINAL SUMMARY - HISTORICAL DATA COLLECTION")
    print(f"{'='*80}")
    
    total_teams_scraped = 0
    total_teams_failed = 0
    total_tables = 0
    
    for season, result in all_results.items():
        if result.get('skipped'):
            print(f"✓ {season}: Skipped (already complete)")
        elif result.get('success'):
            total_teams_scraped += result['successful_teams']
            total_teams_failed += result['failed_teams']
            total_tables += result['total_tables_scraped']
            print(f"✓ {season}: {result['successful_teams']} teams, {result['total_tables_scraped']} tables")
        else:
            print(f"✗ {season}: Failed - {result.get('error', 'Unknown error')}")
    
    print(f"\nTotal teams scraped: {total_teams_scraped}")
    print(f"Total teams failed: {total_teams_failed}")
    print(f"Total data tables: {total_tables}")
    print(f"\nEstimated data points:")
    print(f"  - Player records: ~{total_teams_scraped * 25} players")
    print(f"  - Match records: ~{total_teams_scraped * 38} matches")
    print(f"\nData ready for ML model development!")
    
    return all_results

def scrape_current_season():
    """
    Scrape or update the current season (2025-2026)
    This should be run weekly to get latest results
    """
    
    print("="*80)
    print("PREMALYTICS - CURRENT SEASON UPDATE")
    print("="*80)
    
    # Initialize scraper
    scraper = FBRefScraper()
    
    # Current season
    current_season = "2025-2026"
    
    # Stats to collect
    additional_stats = ['shooting', 'passing', 'defense', 'possession']
    
    print(f"\nUpdating {current_season} season data...")
    print(f"This will clear old data and scrape fresh data for all teams")
    print()
    
    # Run the update
    result = scraper.update_current_season(
        current_season=current_season,
        include_additional=additional_stats,
        include_match_logs=True
    )
    
    # Print results
    if result['success']:
        print(f"\n✓ Update complete!")
        print(f"  Teams updated: {result['teams_updated']}")
        print(f"  Teams failed: {result['teams_failed']}")
        print(f"  Tables scraped: {result['tables_scraped']}")
    else:
        print(f"\n✗ Update failed: {result['error']}")
    
    return result

if __name__ == "__main__":
    import sys
    
    print("\nPREMALYTICS DATA COLLECTION")
    print("Choose an option:")
    print("  1. Scrape ALL historical seasons (2021-2025) - ONE TIME ONLY")
    print("  2. Update current season (2025-2026) - RUN WEEKLY")
    print("  3. Both (recommended for first run)")
    
    choice = input("\nEnter choice (1/2/3): ").strip()
    
    if choice == "1":
        print("\nStarting historical data collection...")
        print("This will take approximately 2-3 hours for 80+ teams")
        confirm = input("Continue? (yes/no): ").strip().lower()
        
        if confirm == 'yes':
            scrape_historical_seasons_full()
        else:
            print("Cancelled.")
    
    elif choice == "2":
        print("\nStarting current season update...")
        confirm = input("This will clear existing 2025-2026 data. Continue? (yes/no): ").strip().lower()
        
        if confirm == 'yes':
            scrape_current_season()
        else:
            print("Cancelled.")
    
    elif choice == "3":
        print("\nStarting FULL data collection...")
        print("This will take 3-4 hours total")
        confirm = input("Continue? (yes/no): ").strip().lower()
        
        if confirm == 'yes':
            # First historical
            print("\n[PHASE 1/2] Historical seasons...")
            scrape_historical_seasons_full()
            
            # Then current
            print("\n[PHASE 2/2] Current season...")
            scrape_current_season()
            
            print("\n" + "="*80)
            print("COMPLETE DATA COLLECTION FINISHED!")
            print("="*80)
        else:
            print("Cancelled.")
    
    else:
        print("Invalid choice. Exiting.")