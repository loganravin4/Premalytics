package com.neutralground.repository;

import com.neutralground.domain.Prediction;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.List;

public interface PredictionRepository extends JpaRepository<Prediction, Long> {

    List<Prediction> findByMatchIdIn(Collection<Long> matchIds);
}
