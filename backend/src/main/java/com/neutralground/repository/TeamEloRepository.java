package com.neutralground.repository;

import com.neutralground.domain.TeamElo;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.LocalDate;
import java.util.List;

public interface TeamEloRepository extends JpaRepository<TeamElo, TeamElo.Key> {

    List<TeamElo> findByTeamCodeAndAsOfDateGreaterThanEqualOrderByAsOfDate(String teamCode, LocalDate since);
}
