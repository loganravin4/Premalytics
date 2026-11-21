package com.neutralground.service;

import com.neutralground.config.CacheConfig;
import com.neutralground.domain.ModelRun;
import com.neutralground.repository.ModelRunRepository;
import com.neutralground.web.dto.ReadDtos.ModelRunView;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional(readOnly = true)
public class ModelRunService {

    private final ModelRunRepository modelRunRepository;

    public ModelRunService(ModelRunRepository modelRunRepository) {
        this.modelRunRepository = modelRunRepository;
    }

    @Cacheable(value = CacheConfig.MODEL_RUNS, key = "'latest:' + #kind")
    public ModelRunView latest(String kind) {
        return modelRunRepository.findFirstByKindOrderByPublishedAtDesc(kind)
                .map(ModelRunService::view)
                .orElseThrow(() -> new NotFoundException("No published model run of kind: " + kind));
    }

    @Cacheable(value = CacheConfig.MODEL_RUNS, key = "'id:' + #id")
    public ModelRunView get(String id) {
        return modelRunRepository.findById(id)
                .map(ModelRunService::view)
                .orElseThrow(() -> new NotFoundException("Model run not found: " + id));
    }

    static ModelRunView view(ModelRun r) {
        return new ModelRunView(r.getId(), r.getKind(), r.getTrainedThrough(), r.getPublishedAt(), r.getMetrics(),
                r.getEvaluation(), r.getNotes());
    }
}
