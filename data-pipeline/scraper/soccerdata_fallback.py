"""
SoccerData Fallback Adapter
Provides fallback functionality using the soccerdata library when primary scraping fails
"""

import logging
import pandas as pd
from typing import Dict, List
from datetime import datetime

try:
    import soccerdata as sd
    SOCCERDATA_AVAILABLE = True
except ImportError:
    SOCCERDATA_AVAILABLE = False
    logging.warning("soccerdata library not available. Fallback will not work.")


class SoccerDataFallback:
    """
    Fallback adapter that uses soccerdata library when primary scraping methods fail
    Converts soccerdata output to match our expected data format
    """
    
    def __init__(self):
        """
        Initialize the soccerdata fallback adapter
        """

        self.logger = logging.getLogger(__name__)
        self.fbref = None
        
        if not SOCCERDATA_AVAILABLE:
            self.logger.warning("soccerdata library not installed. Fallback disabled.")
            return
        
        try:
            # Initialize FBref scraper from soccerdata for Premier League only
            self.fbref = sd.FBref(
                leagues=['ENG-Premier League'],
                no_cache=False  # Use caching to avoid rate limits
            )
            self.logger.info("SoccerData fallback initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize soccerdata fallback: {e}")
            self.fbref = None
    
    def is_available(self) -> bool:
        """
        Check if fallback is available
        """

        return SOCCERDATA_AVAILABLE and self.fbref is not None
    
    def _convert_season_format(self, season: str) -> List[str]:
        """
        Convert season format from '2025-2026' to ['2526', '2025-2026']
        """

        formats = [season]  # Always try the original format first
        
        try:
            # Extract start year
            start_year = season.split('-')[0]

            # Get last 2 digits
            year_short = start_year[-2:]

            # Get next year's last 2 digits
            end_year_short = str(int(year_short) + 1)[-2:]
            short_format = f"{year_short}{end_year_short}"
            formats.append(short_format)

        except Exception as e:
            self.logger.warning(f"Error converting season format {season}: {e}")
        
        return formats
    
    def discover_all_premier_league_teams(self, season: str) -> Dict:
        """
        Discover Premier League teams using soccerdata
        Returns format matching our expected structure
        """

        if not self.is_available():
            return {"success": False, "error": "SoccerData fallback not available"}
        
        try:
            self.logger.info(f"Using soccerdata fallback to discover teams for {season}")
            
            # Get possible season formats
            season_formats = self._convert_season_format(season)
            
            # Get team season stats
            try:
                team_stats = self.fbref.read_team_season_stats(stat_type='standard')
            except Exception as e:
                error_msg = str(e).lower()
                if '403' in error_msg or 'forbidden' in error_msg or 'blocked' in error_msg:
                    self.logger.error("SoccerData fallback also blocked by FBRef (403 Forbidden)")
                    return {
                        "success": False, 
                        "error": "IP address blocked - both primary scraper and soccerdata fallback failed. "
                                "The IP block affects all methods accessing FBRef. Please use a VPN, proxy, "
                                "or wait 24 hours for the block to clear."
                    }
                else:
                    raise
            
            if team_stats is None or team_stats.empty:
                return {"success": False, "error": "No teams found via soccerdata"}
            
            # Try each season format until we find matches
            season_filtered = None
            for season_format in season_formats:
                season_filtered = team_stats[team_stats['season'] == season_format]
                if not season_filtered.empty:
                    self.logger.info(f"Found teams using season format: {season_format}")
                    break
            
            if season_filtered is None or season_filtered.empty:
                return {"success": False, "error": f"No teams found for season {season}"}
            
            # Extract unique teams
            teams = {}
            for _, row in season_filtered.iterrows():
                team_name = row.get('team', '')
                if not team_name:
                    continue
                
                # Create team key (lowercase, replace spaces with underscores)
                team_key = team_name.lower().replace(' ', '_').replace('-', '_')
                
                # Extract team ID from URL if available
                team_id = None
                if 'team_url' in row:
                    url = row['team_url']
                    if '/squads/' in str(url):
                        team_id = str(url).split('/squads/')[1].split('/')[0]
                
                # If no ID from URL, generate a placeholder (soccerdata doesn't always provide IDs)
                if not team_id:
                    # Use first 8 characters of team name hash as placeholder
                    import hashlib
                    team_id = hashlib.md5(team_name.encode()).hexdigest()[:8]
                
                if team_key not in teams:
                    teams[team_key] = {
                        "id": team_id,
                        "name": team_name.replace(' ', '-'),
                        "official_name": team_name,
                    }
            
            self.logger.info(f"Discovered {len(teams)} teams via soccerdata fallback")
            return {"success": True, "teams": teams}
            
        except Exception as e:
            error_msg = str(e).lower()
            if '403' in error_msg or 'forbidden' in error_msg or 'could not download' in error_msg:
                self.logger.error("SoccerData fallback also blocked by FBRef (403 Forbidden)")
                return {
                    "success": False, 
                    "error": "IP address blocked - both primary scraper and soccerdata fallback failed. "
                            "The IP block affects all methods accessing FBRef. Please use a VPN, proxy, "
                            "or wait 24 hours for the block to clear."
                }
            else:
                self.logger.error(f"Error in soccerdata fallback team discovery: {e}")
                return {"success": False, "error": str(e)}
    
    def parse_player_stats(self, team_id: str, team_name: str, season: str, include_additional: List[str] = None) -> Dict:
        """
        Parse player stats using soccerdata
        Returns format matching our expected structure
        """

        if not self.is_available():
            return {"success": False, "error": "SoccerData fallback not available"}
        
        try:
            self.logger.info(f"Using soccerdata fallback to get player stats for {team_name} ({season})")
            
            # Get possible season formats
            season_formats = self._convert_season_format(season)
            
            # Get player stats for the team
            try:
                player_stats = self.fbref.read_player_season_stats(
                    stat_type='standard',
                    league='ENG-Premier League'
                )
            except Exception as e:
                error_msg = str(e).lower()
                if '403' in error_msg or 'forbidden' in error_msg or 'blocked' in error_msg:
                    self.logger.error("SoccerData fallback also blocked by FBRef (403 Forbidden)")
                    return {
                        "success": False, 
                        "error": "IP address blocked - both primary scraper and soccerdata fallback failed. "
                                "The IP block affects all methods accessing FBRef. Please use a VPN, proxy, "
                                "or wait 24 hours for the block to clear."
                    }
                else:
                    raise
            
            if player_stats is None or player_stats.empty:
                return {"success": False, "error": "No player stats found via soccerdata"}
            
            # Filter to specific team and season
            team_filtered = player_stats[
                (player_stats['team'].str.contains(team_name, case=False, na=False)) |
                (player_stats['team'].str.contains(team_name.replace('-', ' '), case=False, na=False))
            ]
            
            if team_filtered.empty:
                return {"success": False, "error": f"No players found for team {team_name}"}
            
            # Filter to season
            season_filtered = None
            for season_format in season_formats:
                season_filtered = team_filtered[team_filtered['season'] == season_format]
                if not season_filtered.empty:
                    self.logger.info(f"Found players using season format: {season_format}")
                    break
            
            if season_filtered is None or season_filtered.empty:
                return {"success": False, "error": f"No players found for {team_name} in {season}"}
            
            # Convert DataFrame to our expected format
            players_data = []
            for _, row in season_filtered.iterrows():
                player_dict = row.to_dict()
                
                # Extract player ID from URL if available
                if 'player_url' in player_dict and pd.notna(player_dict['player_url']):
                    url = str(player_dict['player_url'])
                    if '/players/' in url:
                        player_id = url.split('/players/')[1].split('/')[0]
                        player_dict['player_id'] = player_id
                
                players_data.append(player_dict)
            
            # Get headers from DataFrame columns
            headers = list(season_filtered.columns)
            
            # Build result matching our format
            result = {
                "success": True,
                "table_id": "stats_standard_9",
                "headers": headers,
                "players": players_data,
                "player_count": len(players_data),
                "team_id": team_id,
                "team_name": team_name,
                "season": season,
                "scraped_at": datetime.now().isoformat(),
                "source": "soccerdata_fallback"
            }
            
            # Handle additional tables if requested
            if include_additional:
                additional_data = {}
                for table_type in include_additional:
                    try:
                        # Map our table types to soccerdata stat types
                        stat_type_map = {
                            'shooting': 'shooting',
                            'passing': 'passing',
                            'defense': 'defense',
                            'possession': 'possession',
                            'keeper': 'keeper',
                            'advanced_keeper': 'keeper_adv'
                        }
                        
                        if table_type in stat_type_map:
                            additional_stats = self.fbref.read_player_season_stats(
                                stat_type=stat_type_map[table_type],
                                league='ENG-Premier League'
                            )
                            
                            if additional_stats is not None and not additional_stats.empty:
                                # Filter to team
                                team_stats = additional_stats[
                                    additional_stats['team'].str.contains(team_name, case=False, na=False)
                                ]
                                
                                # Filter to season - try each format
                                team_season_stats = None
                                for season_format in season_formats:
                                    team_season_stats = team_stats[team_stats['season'] == season_format]
                                    if not team_season_stats.empty:
                                        break
                                
                                if team_season_stats is None or team_season_stats.empty:
                                    continue
                                
                                if not team_season_stats.empty:
                                    additional_players = []
                                    for _, row in team_season_stats.iterrows():
                                        additional_players.append(row.to_dict())
                                    
                                    additional_data[table_type] = {
                                        'table_type': table_type,
                                        'display_name': f'{table_type.title()} Stats',
                                        'headers': list(team_season_stats.columns),
                                        'players': additional_players,
                                        'player_count': len(additional_players)
                                    }
                    except Exception as e:
                        self.logger.warning(f"Failed to get {table_type} stats via fallback: {e}")
                
                if additional_data:
                    result['additional_tables'] = additional_data
                    result['total_tables_parsed'] = 1 + len(additional_data)
            
            self.logger.info(f"Successfully retrieved {len(players_data)} players via soccerdata fallback")
            return result
            
        except Exception as e:
            error_msg = str(e).lower()
            if '403' in error_msg or 'forbidden' in error_msg or 'could not download' in error_msg:
                self.logger.error("SoccerData fallback also blocked by FBRef (403 Forbidden)")
                return {
                    "success": False, 
                    "error": "IP address blocked - both primary scraper and soccerdata fallback failed. "
                            "The IP block affects all methods accessing FBRef. Please use a VPN, proxy, "
                            "or wait 24 hours for the block to clear."
                }
            else:
                self.logger.error(f"Error in soccerdata fallback player stats: {e}")
                return {"success": False, "error": str(e)}
    
    def parse_match_logs(self, team_id: str, team_name: str, season: str, premier_league_only: bool = True) -> Dict:
        """
        Parse match logs using soccerdata
        Returns format matching our expected structure
        """

        if not self.is_available():
            return {"success": False, "error": "SoccerData fallback not available"}
        
        try:
            self.logger.info(f"Using soccerdata fallback to get match logs for {team_name} ({season})")
            
            # Get possible season formats
            season_formats = self._convert_season_format(season)
            
            # Get schedule/fixtures
            try:
                schedule = self.fbref.read_schedule(league='ENG-Premier League')
            except Exception as e:
                error_msg = str(e).lower()
                if '403' in error_msg or 'forbidden' in error_msg or 'blocked' in error_msg:
                    self.logger.error("SoccerData fallback also blocked by FBRef (403 Forbidden)")
                    return {
                        "success": False, 
                        "error": "IP address blocked - both primary scraper and soccerdata fallback failed. "
                                "The IP block affects all methods accessing FBRef. Please use a VPN, proxy, "
                                "or wait 24 hours for the block to clear."
                    }
                else:
                    raise
            
            if schedule is None or schedule.empty:
                return {"success": False, "error": "No schedule data found via soccerdata"}
            
            # Filter to season
            season_filtered = None
            for season_format in season_formats:
                season_filtered = schedule[schedule['season'] == season_format]
                if not season_filtered.empty:
                    self.logger.info(f"Found matches using season format: {season_format}")
                    break
            
            if season_filtered is None or season_filtered.empty:
                return {"success": False, "error": f"No matches found for season {season}"}
            
            # Filter to team
            team_matches = season_filtered[
                (season_filtered['home_team'].str.contains(team_name, case=False, na=False)) |
                (season_filtered['away_team'].str.contains(team_name, case=False, na=False))
            ]
            
            if team_matches.empty:
                return {"success": False, "error": f"No matches found for team {team_name}"}
            
            # Convert to our format
            matches_data = []
            for _, row in team_matches.iterrows():
                match_dict = row.to_dict()
                
                # Determine if team was home or away
                is_home = team_name.lower() in str(row.get('home_team', '')).lower()
                match_dict['is_home'] = is_home
                match_dict['opponent'] = row.get('away_team' if is_home else 'home_team', '')
                
                matches_data.append(match_dict)
            
            result = {
                "success": True,
                "table_id": "matchlogs_for",
                "headers": list(team_matches.columns),
                "matches": matches_data,
                "match_count": len(matches_data),
                "team_id": team_id,
                "team_name": team_name,
                "season": season,
                "scraped_at": datetime.now().isoformat(),
                "data_type": "match_logs",
                "source": "soccerdata_fallback"
            }
            
            self.logger.info(f"Successfully retrieved {len(matches_data)} matches via soccerdata fallback")
            return result
            
        except Exception as e:
            error_msg = str(e).lower()
            if '403' in error_msg or 'forbidden' in error_msg or 'could not download' in error_msg:
                self.logger.error("SoccerData fallback also blocked by FBRef (403 Forbidden)")
                return {
                    "success": False, 
                    "error": "IP address blocked - both primary scraper and soccerdata fallback failed. "
                            "The IP block affects all methods accessing FBRef. Please use a VPN, proxy, "
                            "or wait 24 hours for the block to clear."
                }
            else:
                self.logger.error(f"Error in soccerdata fallback match logs: {e}")
                return {"success": False, "error": str(e)}