package com.neutralground.service;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class OutcomesTest {

    @Test
    void picksMostLikelyOutcome() {
        assertThat(Outcomes.pick(0.5, 0.3, 0.2)).isEqualTo("H");
        assertThat(Outcomes.pick(0.2, 0.3, 0.5)).isEqualTo("A");
        assertThat(Outcomes.pick(0.3, 0.4, 0.3)).isEqualTo("D");
        assertThat(Outcomes.pick(0.5, 0.0, 0.5)).isEqualTo("H");
    }
}
