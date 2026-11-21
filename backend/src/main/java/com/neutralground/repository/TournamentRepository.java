package com.neutralground.repository;

import com.neutralground.domain.Tournament;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TournamentRepository extends JpaRepository<Tournament, String> {
}
