package com.neutralground.repository;

import com.neutralground.domain.ModelRun;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.Optional;

public interface ModelRunRepository extends JpaRepository<ModelRun, String> {

    Optional<ModelRun> findFirstByKindOrderByPublishedAtDesc(String kind);

    @Query(value = "select r.id from ng.model_runs r "
            + "where exists (select 1 from ng.shots_xg_grid g where g.model_run_id = r.id) "
            + "order by r.published_at desc limit 1", nativeQuery = true)
    Optional<String> findLatestRunIdWithXgGrid();
}
