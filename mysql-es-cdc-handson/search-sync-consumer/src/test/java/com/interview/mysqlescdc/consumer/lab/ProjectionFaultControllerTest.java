package com.interview.mysqlescdc.consumer.lab;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.runner.WebApplicationContextRunner;

class ProjectionFaultControllerTest {
    @Test
    void controller_arms_and_clears_the_single_registry() {
        ProjectionFaultRegistry registry = new ProjectionFaultRegistry();
        ProjectionFaultController controller = new ProjectionFaultController(registry);

        assertThat(controller.arm(ProjectionFaultMode.CATEGORY_NAME_FROM_ID))
                .containsEntry("fault", "CATEGORY_NAME_FROM_ID");
        assertThat(registry.current()).isEqualTo(ProjectionFaultMode.CATEGORY_NAME_FROM_ID);
        assertThat(controller.clear()).containsEntry("fault", "NONE");
        assertThat(registry.current()).isEqualTo(ProjectionFaultMode.NONE);
    }

    @Test
    void controller_exists_only_when_lab_failpoints_are_enabled() {
        new WebApplicationContextRunner()
                .withBean(ProjectionFaultRegistry.class)
                .withUserConfiguration(ProjectionFaultController.class)
                .run(context -> assertThat(context)
                        .doesNotHaveBean(ProjectionFaultController.class));

        new WebApplicationContextRunner()
                .withPropertyValues("lab.failpoints.enabled=true")
                .withBean(ProjectionFaultRegistry.class)
                .withUserConfiguration(ProjectionFaultController.class)
                .run(context -> assertThat(context)
                        .hasSingleBean(ProjectionFaultController.class));
    }
}
