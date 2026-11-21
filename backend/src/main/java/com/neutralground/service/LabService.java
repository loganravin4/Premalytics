package com.neutralground.service;

import com.neutralground.config.CacheConfig;
import com.neutralground.repository.ModelRunRepository;
import com.neutralground.repository.PenaltyAggregateRepository;
import com.neutralground.repository.XgGridCellRepository;
import com.neutralground.web.dto.ReadDtos.PenaltyAggregateView;
import com.neutralground.web.dto.ReadDtos.XgCell;
import com.neutralground.web.dto.ReadDtos.XgGrid;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/** Read side of the xG lab and penalties lab: precomputed grids and aggregates. */
@Service
@Transactional(readOnly = true)
public class LabService {

    private final ModelRunRepository modelRunRepository;
    private final XgGridCellRepository xgGridCellRepository;
    private final PenaltyAggregateRepository penaltyAggregateRepository;

    public LabService(ModelRunRepository modelRunRepository, XgGridCellRepository xgGridCellRepository,
                      PenaltyAggregateRepository penaltyAggregateRepository) {
        this.modelRunRepository = modelRunRepository;
        this.xgGridCellRepository = xgGridCellRepository;
        this.penaltyAggregateRepository = penaltyAggregateRepository;
    }

    @Cacheable(CacheConfig.XG_GRID)
    public XgGrid xgGrid() {
        String runId = modelRunRepository.findLatestRunIdWithXgGrid()
                .orElseThrow(() -> new NotFoundException("No xG grid has been published yet"));
        List<XgCell> cells = xgGridCellRepository
                .findByModelRunIdOrderByBodyPartAscSituationAscDistanceMAscAngleDegAsc(runId)
                .stream()
                .map(c -> new XgCell(c.getDistanceM(), c.getAngleDeg(), c.getBodyPart(), c.getSituation(),
                        c.getPGoal()))
                .toList();
        return new XgGrid(runId, cells);
    }

    @Cacheable(CacheConfig.PENALTIES)
    public List<PenaltyAggregateView> penaltyAggregates(String dataset, String dimension) {
        return penaltyAggregateRepository.findAllByOrderByDatasetAscDimensionAscBucketAsc().stream()
                .filter(a -> dataset == null || dataset.equals(a.getDataset()))
                .filter(a -> dimension == null || dimension.equals(a.getDimension()))
                .map(a -> new PenaltyAggregateView(a.getDataset(), a.getDimension(), a.getBucket(), a.getKicks(),
                        a.getGoals(), a.getConversion()))
                .toList();
    }
}
