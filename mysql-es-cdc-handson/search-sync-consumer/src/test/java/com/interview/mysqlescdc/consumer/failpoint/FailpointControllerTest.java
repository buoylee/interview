package com.interview.mysqlescdc.consumer.failpoint;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.runner.WebApplicationContextRunner;
import org.springframework.web.server.ResponseStatusException;

class FailpointControllerTest {
    @Test
    void controller_arms_lists_and_clears_the_single_registry() {
        FailpointRegistry registry = new FailpointRegistry(code -> { });
        FailpointController controller = new FailpointController(registry);

        assertThat(controller.arm("AFTER_DLQ_PUBLISH", 2))
                .containsEntry("AFTER_DLQ_PUBLISH", 2);
        assertThat(controller.list()).containsEntry("AFTER_DLQ_PUBLISH", 2);
        assertThat(controller.clear().values()).allMatch(value -> value == 0);
        assertThatThrownBy(() -> controller.arm("UNKNOWN", 1))
                .isInstanceOf(ResponseStatusException.class);
        assertThatThrownBy(() -> controller.arm("AFTER_DLQ_PUBLISH", 0))
                .isInstanceOf(ResponseStatusException.class);
    }

    @Test
    void controller_exists_only_when_lab_failpoints_are_enabled() {
        new WebApplicationContextRunner()
                .withBean(CrashAction.class, () -> code -> { })
                .withBean(FailpointRegistry.class)
                .withUserConfiguration(FailpointController.class)
                .run(context -> assertThat(context).doesNotHaveBean(FailpointController.class));

        new WebApplicationContextRunner()
                .withPropertyValues("lab.failpoints.enabled=true")
                .withBean(CrashAction.class, () -> code -> { })
                .withBean(FailpointRegistry.class)
                .withUserConfiguration(FailpointController.class)
                .run(context -> assertThat(context).hasSingleBean(FailpointController.class));
    }
}
