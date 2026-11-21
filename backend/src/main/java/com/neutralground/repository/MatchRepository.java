package com.neutralground.repository;

import com.neutralground.domain.Match;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface MatchRepository extends JpaRepository<Match, Long> {

    @EntityGraph(attributePaths = {"homeTeam", "awayTeam"})
    Page<Match> findByTournamentId(String tournamentId, Pageable pageable);

    @EntityGraph(attributePaths = {"homeTeam", "awayTeam"})
    Page<Match> findByTournamentIdAndStage(String tournamentId, String stage, Pageable pageable);

    List<Match> findByTournamentIdOrderByMatchNumber(String tournamentId);

    @EntityGraph(attributePaths = {"homeTeam", "awayTeam"})
    @Query("select m from Match m where m.id = :id")
    Optional<Match> findWithTeamsById(@Param("id") Long id);

    @EntityGraph(attributePaths = {"homeTeam", "awayTeam"})
    @Query("select m from Match m where m.homeTeam.code = :code or m.awayTeam.code = :code "
            + "order by m.matchDate desc, m.matchNumber desc")
    List<Match> findByTeam(@Param("code") String code);
}
