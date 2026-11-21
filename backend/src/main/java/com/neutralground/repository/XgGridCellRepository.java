package com.neutralground.repository;

import com.neutralground.domain.XgGridCell;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface XgGridCellRepository extends JpaRepository<XgGridCell, Long> {

    List<XgGridCell> findByModelRunIdOrderByBodyPartAscSituationAscDistanceMAscAngleDegAsc(String modelRunId);
}
