package com.neutralground.web;

import com.neutralground.service.PredictionService;
import com.neutralground.service.TeamCatalog;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(PredictionController.class)
@TestPropertySource(properties = {
        "neutralground.rate-limit.capacity=2",
        "neutralground.rate-limit.refill-per-minute=1"
})
class RateLimitTest {

    @Autowired
    MockMvc mvc;

    @MockitoBean
    PredictionService predictionService;

    @MockitoBean
    TeamCatalog teamCatalog;

    private static MockHttpServletRequestBuilder shot(String clientIp) {
        return post("/api/predictions/shot")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"distanceM\":10,\"angleDeg\":10}")
                .with(request -> {
                    request.setRemoteAddr(clientIp);
                    return request;
                });
    }

    @Test
    void limitsPostsPerClient() throws Exception {
        mvc.perform(shot("10.0.0.1")).andExpect(status().isOk());
        mvc.perform(shot("10.0.0.1")).andExpect(status().isOk());
        mvc.perform(shot("10.0.0.1"))
                .andExpect(status().isTooManyRequests())
                .andExpect(header().exists("Retry-After"))
                .andExpect(jsonPath("$.status").value(429));

        // Another client has its own bucket.
        mvc.perform(shot("10.0.0.2")).andExpect(status().isOk());
    }
}
