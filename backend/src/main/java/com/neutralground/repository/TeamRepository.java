package com.neutralground.repository;

import com.neutralground.domain.Team;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TeamRepository extends JpaRepository<Team, String> {

    Page<Team> findByConfederation(String confederation, Pageable pageable);
}
