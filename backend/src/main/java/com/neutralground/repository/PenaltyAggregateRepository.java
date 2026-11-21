package com.neutralground.repository;

import com.neutralground.domain.PenaltyAggregate;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface PenaltyAggregateRepository extends JpaRepository<PenaltyAggregate, Long> {

    List<PenaltyAggregate> findAllByOrderByDatasetAscDimensionAscBucketAsc();
}
